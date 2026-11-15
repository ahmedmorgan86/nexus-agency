# Staging Runbook

## 1. Configure
1. Copy `.env.example` to `.env` and fill the values.
2. Set `NEXUS_OWNER_DATABASE_URL` (owner/DDL), `DATABASE_URL` (`nexus_app`), and
   `WORKER_DATABASE_URL` (`nexus_worker`). The runtime roles must never be superuser or
   `BYPASSRLS`, otherwise RLS is not enforced.
3. Set `NEXUS_APP_PASSWORD` / `NEXUS_WORKER_PASSWORD` (>= 24 chars, different values).

## 2. Apply schema
```bash
python scripts/apply_migrations.py --dry-run   # list pending
python scripts/apply_migrations.py             # apply (checksum-tracked, idempotent)
python scripts/bootstrap_roles.py              # grant LOGIN + passwords
python scripts/bootstrap_roles.py --check      # verify roles are not superuser/BYPASSRLS
```

## 3. Run services
```bash
# API
cd services/api && python dev_server.py --port 8000
# Worker (separate process)
cd services/api && python -m app.worker
```
Or the containerised path: `docker compose up --build`.

## 4. Verify
```bash
python scripts/health_check.py
curl http://localhost:8000/health      # expects {"status":"ok","database":"connected"}
curl http://localhost:8000/features    # honest feature labels
```

## 5. Test
```bash
python -m unittest discover -s tests                 # agent core (offline)
python scripts/run_api_tests.py --allow-destructive  # API/queue/RLS on a disposable DB
cd backend && python tests.py                        # legacy service
```

## 6. Frontend
- Set `localStorage.nexus_api_base` to the API URL.
- Store the JWT in `sessionStorage.nexus_token`.
- Unconfigured capabilities must render `N/A` / `NOT_CONFIGURED`, never a number.

# Production Approval Checklist
- [ ] `APP_ENV=production` set (makes `JWT_SECRET`, `DATABASE_URL`, `WORKER_DATABASE_URL` mandatory)
- [ ] `JWT_SECRET` and `NEXUS_SECURITY_SALT` rotated and stored only in the secret manager
- [ ] `DATABASE_URL` / `WORKER_DATABASE_URL` use `nexus_app` / `nexus_worker` (verified with `bootstrap_roles.py --check`)
- [ ] `ALLOW_REGISTRATION=0`
- [ ] `CORS_ORIGINS` restricted to the real frontend origin
- [ ] Provider keys configured; `/providers/status` returns the expected `CONFIGURED` values
- [ ] All three test suites passing against the target database
- [ ] Backup/restore drill executed on the hosted database
- [ ] Worker supervised (systemd/container) and restart policy defined
- [ ] Explicit written approval to deploy
