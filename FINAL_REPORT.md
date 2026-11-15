# NEXUS — Final Transformation Report

Last updated: 2026-11-15 (after Milestone 4: hosted database + enforced RLS).
See [docs/MILESTONE4.md](docs/MILESTONE4.md) for the evidence behind each claim.

## Test results (executed, not assumed)

| Suite | Command | Result |
|---|---|---|
| Agent core + provider honesty | `python -m unittest discover -s tests` | **22/22 passed** |
| API / queue / RLS (hosted Postgres) | `python scripts/run_api_tests.py --allow-destructive` | **43/43 passed** |
| Legacy service | `cd backend && python tests.py` | **4/4 passed** |

The API suite runs against the hosted `nexus_test` database on Supabase, with the
application connecting as `nexus_app` (`NOSUPERUSER NOBYPASSRLS`).

## Component classification

| Component | Status | Notes |
|---|---|---|
| Tenant isolation (Postgres RLS) | **PRODUCTION READY** | Forced RLS on every tenant table, verified by tests + manual probes. App role cannot bypass it. |
| Task queue + retries + timeouts | **PRODUCTION READY** | `SKIP LOCKED` claim, exponential backoff, timeout reaper, dependency cancellation. Verified end-to-end. |
| Human approval gate | **PRODUCTION READY** | External-effect agents land in `WAITING_APPROVAL`; owner/admin only; decisions audited. |
| Auth (register/login/JWT/roles) | **FUNCTIONAL — NEEDS CONFIGURATION** | scrypt hashing, hashed lookups via `SECURITY DEFINER`. Missing: rate limiting, password reset, email verification, refresh tokens. |
| CRM (leads) | **PARTIALLY IMPLEMENTED** | Create + list + tenant scoping. No update/delete/import UI. |
| Discovery agent | **FUNCTIONAL — NEEDS CONFIGURATION** | Grounded Gemini search, real source URLs, dedup, honest errors. Blocked by provider quota (HTTP 429). |
| Website audit (intel) | **FUNCTIONAL — NEEDS CONFIGURATION** | Real HTTP fetch + SSRF guard + evidence capture. |
| Image generation | **FUNCTIONAL — NEEDS CONFIGURATION** | Gemini image adapter implemented; quota-blocked for the current key. |
| Video generation | **NOT IMPLEMENTED** | No Veo model enabled for the key; provider reports `NOT_CONFIGURED`. |
| Email / report delivery | **FUNCTIONAL — NEEDS CONFIGURATION** | PDF generation works; SMTP credentials absent, so reports are archived with `SMTP_CREDENTIALS_MISSING`. |
| Reporting PDF | **FUNCTIONAL — NEEDS CONFIGURATION** | Real PDF built and attached when SMTP is configured. |
| Legacy `backend/` service | **PARTIALLY IMPLEMENTED** | Auth, CRM, demo tokens, assets, memory, uploads. Uses `create_all` + SQLite by default; not the production path. |
| Static dashboards (`index.html`, `dashboard.html`) | **PARTIALLY IMPLEMENTED** | Fabricated scores removed; shows `N/A` / `NOT_CONFIGURED` / `NOT_CONNECTED`. Not wired to the new API. |
| `apps/web` (Next.js) | **NOT IMPLEMENTED** | Shell only (`page.tsx`). |
| Learning / self-healing | **PARTIALLY IMPLEMENTED** | Scaffolding with tests; no autonomous production action. |
| Staging infrastructure | **FUNCTIONAL — NEEDS CONFIGURATION** | Docker, compose, CI, health check, runbooks present; hosted staging deploy not executed. |
| Production deployment | **NOT IMPLEMENTED** | Requires explicit approval; not performed. |

## What is real now

- Hosted PostgreSQL 17.11 (Supabase, `eu-north-1`) with two databases: `postgres` (app) and
  `nexus_test` (disposable tests).
- Migrations applied by `scripts/apply_migrations.py` with checksums; roles bootstrapped by
  `scripts/bootstrap_roles.py`. No password exists in any migration or tracked file.
- Verified live flow: register → login → create lead → list leads (tenant-scoped) →
  enqueue task → approval required → approve → worker executes → `COMPLETED`.
- `/health` performs a real database round-trip and returns `503` when it fails.
- `/features` reports honest status labels; the test suite asserts the vocabulary.
- `APP_ENV=production` requires `DATABASE_URL`, `WORKER_DATABASE_URL` and `JWT_SECRET`, and
  closes self-registration unless `ALLOW_REGISTRATION=1` is set on purpose. CORS is an
  explicit allowlist from `CORS_ORIGINS`.

## Known limitations

1. **Gemini generation quota** for the current key is exhausted (HTTP 429). Discovery and
   image generation therefore return `ERROR` with the provider message, not data.
2. **No browser UI on the new API.** `apps/web` is a shell; the HTML dashboards still talk
   to the legacy backend or show `NOT_CONFIGURED`.
3. **Auth hardening gaps**: no rate limiting on `/auth/*`, no password reset, no email
   verification, no refresh/rotation of JWTs.
4. **CRM gaps**: leads cannot be updated/deleted; no pagination; no bulk import.
5. **Worker deployment**: runs as a foreground process (`python -m app.worker`); no
   supervisor/container orchestration defined for it yet.
6. **Legacy service** still defaults to SQLite and `create_all`; it should be retired or
   migrated onto the same migrations before production.
7. **No backup/restore drill** has been executed on the hosted database.

## Not done on purpose

- No production deployment, no domain/DNS changes, no billing changes.
- No messages sent, no campaigns published, no budgets spent.
- No provider keys committed; `.env` stays untracked.
