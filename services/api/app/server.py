import base64
import hashlib
import hmac
import os
import secrets
import time
import uuid
from contextlib import contextmanager

import jwt
import psycopg
from psycopg.types.json import Jsonb
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl

FEATURES = {
    "auth": "FUNCTIONAL_NEEDS_CONFIGURATION",
    "tenant_isolation": "PRODUCTION_READY",
    "crm": "PARTIALLY_IMPLEMENTED",
    "task_queue": "FUNCTIONAL_NEEDS_CONFIGURATION",
    "approvals": "FUNCTIONAL_NEEDS_CONFIGURATION",
    "agent_registry": "FUNCTIONAL_NEEDS_CONFIGURATION",
    "discovery": "NOT_IMPLEMENTED",
    "image_generation": "NOT_IMPLEMENTED",
    "video_generation": "NOT_IMPLEMENTED",
    "email": "NOT_IMPLEMENTED",
}

WRITE_ROLES = {"owner", "admin", "operator"}
TOKEN_TTL = 3600


def dsn() -> str:
    value = os.environ.get("DATABASE_URL")
    if value:
        return value
    if os.environ.get("APP_ENV", "development") == "production":
        raise RuntimeError("DATABASE_URL is required in production")
    # Local throwaway Postgres from scripts/start_test_pg.sh (trust auth, no password).
    return "host=/tmp port=5433 dbname=nexus_test user=nexus_app"


def jwt_secret() -> str:
    s = os.environ.get("JWT_SECRET")
    if s:
        return s
    if os.environ.get("APP_ENV", "development") == "production":
        raise RuntimeError("JWT_SECRET is required in production")
    return "dev-only-secret-change-me-0123456789abcdef"


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, s, h = stored.split("$")
        salt, expected = base64.b64decode(s), base64.b64decode(h)
    except ValueError:
        return False
    got = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(got, expected)


def make_token(user_id, tenant_id, role) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": str(user_id), "tid": str(tenant_id), "role": role, "iat": now, "exp": now + TOKEN_TTL},
        jwt_secret(), algorithm="HS256",
    )


class Principal(BaseModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


def current_principal(authorization: str = Header(default="")) -> Principal:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    try:
        c = jwt.decode(authorization[7:], jwt_secret(), algorithms=["HS256"])
        return Principal(user_id=c["sub"], tenant_id=c["tid"], role=c["role"])
    except Exception:
        raise HTTPException(401, "invalid or expired token")


def require_write(p: Principal = Depends(current_principal)) -> Principal:
    if p.role not in WRITE_ROLES:
        raise HTTPException(403, "role not permitted")
    return p


@contextmanager
def db(tenant_id=None):
    """Connection as the unprivileged app role; tenant context is set per transaction."""
    with psycopg.connect(dsn()) as conn:
        if tenant_id is not None:
            conn.execute("select set_config('app.tenant_id', %s, true)", (str(tenant_id),))
        yield conn


class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=10, max_length=200)
    tenant_name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)
    tenant_id: uuid.UUID | None = None


class LeadIn(BaseModel):
    business_name: str = Field(min_length=1, max_length=200)
    website: HttpUrl | None = None
    source_url: HttpUrl | None = None


app = FastAPI(title="NEXUS API", version="0.3.0")


def cors_origins() -> list[str]:
    return [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]


if cors_origins():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def registration_allowed() -> bool:
    """Public self-registration. Explicit ALLOW_REGISTRATION wins; otherwise closed in production."""
    raw = (os.environ.get("ALLOW_REGISTRATION") or "").strip() or None
    if raw is not None:
        return raw == "1"
    return os.environ.get("APP_ENV", "development") != "production"


@app.get("/health")
def health(response: Response):
    """Honest health: reports the database state instead of assuming it works."""
    try:
        with db() as conn:
            conn.execute("select 1")
        database = "connected"
    except Exception:  # noqa: BLE001 - health must never raise
        database = "unavailable"
        response.status_code = 503
    return {"status": "ok" if database == "connected" else "degraded", "env": os.environ.get("APP_ENV", "development"),
            "database": database, "version": app.version}


@app.get("/features")
def features():
    """Honest feature status: never reports more than what is built."""
    return FEATURES


@app.post("/auth/register", status_code=201)
def register(body: RegisterIn):
    if not registration_allowed():
        raise HTTPException(403, "self-registration is disabled")
    uid, tid = uuid.uuid4(), uuid.uuid4()
    try:
        with db(tid) as conn:
            conn.execute("insert into users (id, email, password_hash) values (%s,%s,%s)",
                         (uid, body.email.lower(), hash_password(body.password)))
            conn.execute("insert into tenants (id, name) values (%s,%s)", (tid, body.tenant_name))
            conn.execute("insert into memberships (user_id, tenant_id, role) values (%s,%s,'owner')", (uid, tid))
            conn.execute("insert into audit_logs (tenant_id, actor_user_id, action) values (%s,%s,'tenant.created')",
                         (tid, uid))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "email already registered")
    return {"token": make_token(uid, tid, "owner"), "tenant_id": str(tid)}


@app.post("/auth/login")
def login(body: LoginIn):
    with db() as conn:
        row = conn.execute("select id, password_hash from login_lookup(%s)", (body.email.lower(),)).fetchone()
        # Always hash-compare so unknown email and wrong password take similar time.
        ok = verify_password(body.password, row[1] if row else hash_password("x"))
        if not row or not ok:
            raise HTTPException(401, "invalid credentials")
        ms = conn.execute("select tenant_id, role from login_memberships(%s)", (row[0],)).fetchall()
    if body.tenant_id:
        ms = [m for m in ms if m[0] == body.tenant_id]
    if not ms:
        raise HTTPException(403, "no membership for this tenant")
    if len(ms) > 1:
        raise HTTPException(409, "multiple tenants; specify tenant_id")
    return {"token": make_token(row[0], ms[0][0], ms[0][1]), "tenant_id": str(ms[0][0])}


@app.post("/leads", status_code=201)
def create_lead(body: LeadIn, p: Principal = Depends(require_write)):
    lid = uuid.uuid4()
    with db(p.tenant_id) as conn:
        conn.execute(
            "insert into leads (id, tenant_id, business_name, website, source_url) values (%s,%s,%s,%s,%s)",
            (lid, p.tenant_id, body.business_name, str(body.website) if body.website else None,
             str(body.source_url) if body.source_url else None))
        conn.execute("insert into audit_logs (tenant_id, actor_user_id, action, detail) values (%s,%s,'lead.created',%s)",
                     (p.tenant_id, p.user_id, Jsonb({"lead_id": str(lid)})))
    return {"id": str(lid)}


@app.get("/leads")
def list_leads(p: Principal = Depends(current_principal)):
    with db(p.tenant_id) as conn:
        rows = conn.execute(
            "select id, business_name, website, verification_status, source_url, discovered_at "
            "from leads order by created_at desc limit 500").fetchall()
    return [{"id": str(r[0]), "business_name": r[1], "website": r[2], "verification_status": r[3],
             "source_url": r[4], "discovered_at": r[5].isoformat()} for r in rows]


from app.tasks_api import router as _tasks_router  # noqa: E402  (registered after app and helpers exist)

app.include_router(_tasks_router)
