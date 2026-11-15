# NEXUS 2.0 — AI Marketing & Autonomous Business Growth Platform

Real backend, real database, real tenant isolation. No fabricated audits, leads or scores:
anything that is not configured reports `NOT_CONFIGURED` instead of inventing a result.

- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)
- Milestones: [docs/MILESTONE2.md](docs/MILESTONE2.md), [docs/MILESTONE3.md](docs/MILESTONE3.md), [docs/MILESTONE4.md](docs/MILESTONE4.md)
- Current status / classification: [FINAL_REPORT.md](FINAL_REPORT.md)

## Layout

| Path | What it is |
|---|---|
| `services/api` | FastAPI API + durable Postgres task queue + worker (current backend) |
| `supabase/migrations` | SQL migrations (tenancy, RLS, queue, users) |
| `scripts` | Migrations runner, role bootstrap, test runner, health check |
| `backend` | Earlier standalone FastAPI service (auth, CRM, demo tokens, assets) |
| `nexus_os` | Agent core reused as libraries (discovery, intel, scoring, security, reporting, providers) |
| `apps/web` | Next.js shell (UI not built yet) |
| `*.html` | Legacy static dashboards kept for visual identity |

## Setup

```bash
cp .env.example .env          # fill in real values, never commit .env
pip install -r services/api/requirements.txt

# 1. schema + unprivileged roles (owner connection)
python scripts/apply_migrations.py
python scripts/bootstrap_roles.py

# 2. run the API
cd services/api && python dev_server.py --port 8000

# 3. run the worker (separate process)
cd services/api && python -m app.worker
```

`DATABASE_URL` and `WORKER_DATABASE_URL` must use the `nexus_app` / `nexus_worker` roles.
Those roles are `NOSUPERUSER NOBYPASSRLS`, so row-level security is enforced by Postgres,
not only by application code.

### Containerised stack

```bash
docker compose up --build      # db + migrate + api + worker
```

`migrate` is a one-shot service: it applies the migrations and grants the two roles LOGIN
with `NEXUS_APP_PASSWORD` / `NEXUS_WORKER_PASSWORD`. `api` and `worker` start only after it
succeeds. The image is built from the repository root (`services/api/Dockerfile`) and
`.dockerignore` keeps `.env` out of it.

## Tests

```bash
python -m unittest discover -s tests        # agent core + providers (offline)
python scripts/run_api_tests.py             # API/queue/RLS against a disposable Postgres
cd backend && python tests.py               # legacy service tests
```

`scripts/run_api_tests.py --allow-destructive` drops and rebuilds `public` schema on the
database named by `NEXUS_TEST_*_URL` (default: local throwaway cluster on port 5433).

## Safety rules encoded in the system

- External-effect agents (`system.external_demo`, sales, reporting) always land in
  `WAITING_APPROVAL`; only owner/admin can approve, and approval is audited.
- Discovery refuses to run without a provider and returns the grounding source URLs.
- Media providers return `NOT_CONFIGURED` / `ERROR`; they never emit placeholder files.
- `APP_ENV=production` makes `JWT_SECRET`, `DATABASE_URL` and `WORKER_DATABASE_URL` mandatory,
  and closes public self-registration unless `ALLOW_REGISTRATION=1` is set explicitly.
- CORS is only enabled for the origins listed in `CORS_ORIGINS`.
