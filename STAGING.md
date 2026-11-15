# Staging & Deployment Notes

## Backend
- Set DATABASE_URL (PostgreSQL/Supabase) or SQLite for dev.
- Set JWT_SECRET (strong random).
- Set ALLOW_REGISTRATION=1 only for initial bootstrap; disable after.
- Set CORS_ORIGINS to frontend origin.

## Frontend
- Set localStorage nexus_api_base to backend URL.
- Store JWT in sessionStorage (nexus_token).

## Before Production
- Rotate any exposed secrets.
- Run root tests + backend tests.
- Run security review (SSRF, tenant isolation, XSS).
- No automatic production deployment without explicit approval.
