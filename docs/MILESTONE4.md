# NEXUS 2.0 — Milestone 4: hosted database, enforced RLS, verified end-to-end

Milestone 3 shipped the greenfield API, migrations and worker against a local-only Postgres.
Milestone 4 makes that real on a hosted database and removes the remaining hardcoded
credentials from the repository.

## 1. Hosted Postgres (Supabase)

| Item | Value |
|---|---|
| Project | `nexus-agency` |
| Ref | `holbftzkeajpsnuzjoju` |
| Region | `eu-north-1` (Stockholm) |
| Postgres | 17.11 |
| RLS trigger | "Enable automatic RLS" on, "Automatically expose new tables" off |

Two databases:

- `postgres` — the application database.
- `nexus_test` — disposable database for the API test suite.

## 2. No credentials in migrations

Migrations previously created `nexus_app` / `nexus_worker` with the literal passwords
`nexus_app` / `nexus_worker`. That is now impossible:

- `0001` / `0003` create the roles `NOLOGIN`, `NOSUPERUSER`, `NOBYPASSRLS`.
- `scripts/bootstrap_roles.py` grants `LOGIN` and sets the password from
  `NEXUS_APP_PASSWORD` / `NEXUS_WORKER_PASSWORD`, enforcing >= 24 chars, distinct values,
  and refusing roles that are superuser or `BYPASSRLS`.

`scripts/apply_migrations.py` replaces ad-hoc `psql` runs: it records each file with a
SHA-256 checksum in `_migrations`, refuses to re-run changed files, and supports `--dry-run`.

## 3. Users table policy (0004)

The hosted project's automatic-RLS trigger exposed a real gap: `users` had no policy, so
registration failed with `new row violates row-level security policy`. Migration `0004`:

- enables and forces RLS on `users`;
- adds an insert-only signup policy;
- moves password-hash reads into `login_lookup(email)` (`SECURITY DEFINER`, `search_path`
  pinned, executable only by `nexus_app`);
- revokes `SELECT` on `users` from `nexus_app`, so hashes are never directly readable by
  the application role.

`/auth/login` now calls `login_lookup` instead of selecting from `users`.

## 4. Enforced isolation, proven

`DATABASE_URL` now authenticates as `nexus_app` (`rolsuper=false`, `rolbypassrls=false`) via
the Supabase session pooler. Verified manually and by tests:

- insert in tenant A is invisible to tenant B;
- no tenant context sees zero rows;
- cross-tenant insert/update/delete raises `InsufficientPrivilege`;
- `audit_logs` are isolated;
- `nexus_app` cannot execute the worker's cross-tenant functions.

## 5. Test evidence

```
python scripts/run_api_tests.py --allow-destructive
43 passed  (services/api: auth, queue, retries, timeouts, approvals, RLS, registration guard)

python -m unittest discover -s tests
22 passed  (agent core, providers, discovery honesty)

cd backend && python tests.py
4 passed
```

The API suite runs against the hosted `nexus_test` database, not a mock.

## 6. Live smoke test

Against `postgres` with the real pooler:

```
GET  /health            -> {"status":"ok","database":"connected","version":"0.3.0"}
POST /auth/register     -> 201, tenant created
POST /auth/login        -> 200, same tenant
GET  /leads (no token)  -> 401
POST /leads             -> 201, visible only inside that tenant
GET  /agents            -> 18 agents, 3 runnable
POST /tasks system.echo -> QUEUED
POST /tasks system.external_demo -> WAITING_APPROVAL
POST /approvals/{id}/approve -> approved, task QUEUED
worker run_once() x2    -> both tasks COMPLETED, external effect {"simulated": true, "sent": false}
```

## 7. Providers

- `GEMINI_API_KEY` verified read-only against `v1beta/models`: 50 models visible.
- Text model default moved to the `gemini-flash-latest` alias (`gemini-2.5-flash` now
  returns 404 "no longer available to new users").
- Image: `gemini-3.1-flash-image` via `generateContent` + `responseModalities: ["IMAGE"]`.
- Video: no Veo model is enabled for this key, so `GeminiVideoProvider` reports
  `NOT_CONFIGURED` until `GEMINI_VIDEO_MODEL` is set.
- Discovery returns `ERROR` with the provider's real message when quota is exhausted
  (observed HTTP 429 on generation), never fake leads.

## 8. Container stack

`docker-compose.yml` defines `db` (Postgres 16), `migrate` (one-shot: migrations + role
passwords), `api` and `worker`. `api`/`worker` wait for `migrate` to complete and connect as
`nexus_app` / `nexus_worker`, never as the owner. The image is built from the repository root
(`services/api/Dockerfile`) and `.dockerignore` excludes `.env`. Not executed here: Docker is
not installed on this machine, so the stack is written but unverified.

## 9. Known gaps after this milestone

1. Gemini generation quota for this key is exhausted (HTTP 429); discovery/image calls need
   quota or billing before they can return data.
2. `apps/web` is still a shell; the API has no browser UI wired to it yet.
3. No rate limiting / password reset / email verification in the API.
4. `backend/` (legacy service) still uses `Base.metadata.create_all` and SQLite by default;
   it is not the production path.
5. `docker compose` stack is untested locally (Docker not installed here).
