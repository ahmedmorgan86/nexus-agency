# Staging Runbook

1. Copy `.env.example` to `.env` and fill values.
2. Start backend:
   - `docker compose up --build`
   - or `scripts/stage.ps1`
3. Verify health:
   - `python scripts/health_check.py`
4. Run tests:
   - `python -m unittest discover -s tests`
   - `cd backend && python tests.py`
5. Frontend:
   - Set `localStorage.nexus_api_base` to backend URL.
   - Store JWT in `sessionStorage.nexus_token`.

# Production Approval Checklist
- [ ] Secrets rotated and stored in env
- [ ] JWT_SECRET set
- [ ] DATABASE_URL set to managed Postgres/Supabase
- [ ] ALLOW_REGISTRATION disabled
- [ ] CORS_ORIGINS restricted
- [ ] Provider API keys configured
- [ ] All tests passing
- [ ] Explicit approval granted
