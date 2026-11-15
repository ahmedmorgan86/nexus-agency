# Milestone 2 report

## Implemented
- Migrations: 0001_core_tenancy.sql (tenants, users, memberships, leads, audit_logs, forced RLS, unprivileged nexus_app role), 0002_login_helper.sql (one narrow SECURITY DEFINER function for login).
- API: register, login, create/list leads, scrypt password hashing, HS256 JWT (1h), roles owner/admin/operator/client_viewer, tenant taken only from the token, audit log entries.
- Tests (real Postgres 16, app connects as non-superuser, no BYPASSRLS): 20 passed (cross-tenant read/insert/update/delete/move blocked, no-context sees nothing, API-level isolation, RBAC, expired/tampered tokens).

## Run
scripts/start_test_pg.sh, then in services/api: pip install -r requirements.txt && pytest

## Known limitations (not yet done)
- Role is read from the JWT; a demoted user keeps old rights until the token expires (max 1h). Fix: check membership per request or shorten TTL + refresh.
- No rate limiting, CSRF, lockout, email verification, password reset, or refresh tokens yet.
- users table is not under RLS (needed for login); email enumeration is possible via registration 409.
- Supabase Auth not wired; this uses its own JWT auth on plain Postgres. Migrating later means mapping users to auth.users.
- Only leads/audit tables exist; CRM, tasks, budgets, etc. come in later milestones.
- Web app not built or tested; no staging deployment.

## Rollback
Migrations are forward-only on a fresh DB: drop schema public cascade and re-run, or git revert this milestone.
