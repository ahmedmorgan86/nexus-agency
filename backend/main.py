import os
import uuid
import time
import secrets
import shutil
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Header, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import Base, engine, get_db
from models import Tenant, User, Lead, Task, AuditLog, DemoToken, CreativeAsset, OperationalMemory
from schemas import LeadCreate, LeadRead, HealthResponse, DemoTokenCreate, AssetCreate, AssetRead, MemoryCreate, MemoryRead
from auth import hash_password, verify_password, create_access_token, decode_token

Base.metadata.create_all(bind=engine)

app = FastAPI(title="NEXUS Backend", version="0.2.0")

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/files", StaticFiles(directory=UPLOAD_DIR), name="files")

allowed_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Simple in-memory rate limiter (per process)
_rate: dict = {}
def rate_limit(request: Request, limit: int = 60, window: int = 60):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _rate.setdefault(ip, [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_role(*roles):
    def dep(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return dep

@app.get("/health", response_model=HealthResponse)
def health(request: Request, db: Session = Depends(get_db)):
    rate_limit(request)
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"
    return HealthResponse(status="ok", database=db_status, version="0.2.0")

@app.post("/auth/register")
def register(email: str, password: str, tenant_name: str = "NEXUS Tenant", db: Session = Depends(get_db)):
    if os.environ.get("ALLOW_REGISTRATION", "0") != "1":
        raise HTTPException(status_code=403, detail="Registration disabled")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    tenant = Tenant(id=f"tenant_{uuid.uuid4().hex[:8]}", name=tenant_name)
    db.add(tenant)
    db.flush()
    user = User(
        id=f"user_{uuid.uuid4().hex[:8]}",
        tenant_id=tenant.id,
        email=email,
        hashed_password=hash_password(password),
        role="admin",
    )
    db.add(user)
    db.commit()
    return {"registered": True, "tenant_id": tenant.id}

@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user.id, user.tenant_id, user.role)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "tenant_id": user.tenant_id, "role": user.role}

@app.get("/leads", response_model=list[LeadRead])
def list_leads(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Lead).filter(Lead.tenant_id == user.tenant_id).order_by(Lead.lead_score.desc()).all()

@app.post("/leads", response_model=LeadRead)
def create_lead(payload: LeadCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = Lead(id=f"lead_{uuid.uuid4().hex[:10]}", tenant_id=user.tenant_id, **payload.model_dump())
    db.add(lead)
    db.add(AuditLog(tenant_id=user.tenant_id, actor=user.id, action="CREATE_LEAD", details=lead.id))
    db.commit()
    db.refresh(lead)
    return lead

@app.delete("/leads/{lead_id}")
def delete_lead(lead_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == user.tenant_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.add(AuditLog(tenant_id=user.tenant_id, actor=user.id, action="DELETE_LEAD", details=lead_id))
    db.commit()
    return {"deleted": True}

# Demo tokens
@app.post("/demo-tokens")
def create_demo_token(payload: DemoTokenCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=payload.expires_in_hours)
    dt = DemoToken(token=token, tenant_id=user.tenant_id, lead_id=payload.lead_id, expires_at=expires_at)
    db.add(dt)
    db.add(AuditLog(tenant_id=user.tenant_id, actor=user.id, action="CREATE_DEMO_TOKEN", details=token))
    db.commit()
    return {"token": token, "expires_at": expires_at.isoformat(), "lead_id": payload.lead_id}

@app.get("/demo/{token}")
def get_demo(token: str, db: Session = Depends(get_db)):
    dt = db.query(DemoToken).filter(DemoToken.token == token).first()
    if not dt or dt.revoked or dt.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail="Invalid or expired demo token")
    lead = db.query(Lead).filter(Lead.id == dt.lead_id, Lead.tenant_id == dt.tenant_id).first() if dt.lead_id else None
    return {
        "tenant_id": dt.tenant_id,
        "lead": {
            "name": lead.name if lead else None,
            "sector": lead.sector if lead else None,
            "website": lead.website if lead else None,
        } if lead else None,
        "expires_at": dt.expires_at.isoformat(),
    }

@app.post("/demo/{token}/revoke")
def revoke_demo(token: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dt = db.query(DemoToken).filter(DemoToken.token == token, DemoToken.tenant_id == user.tenant_id).first()
    if not dt:
        raise HTTPException(status_code=404, detail="Token not found")
    dt.revoked = True
    db.commit()
    return {"revoked": True}

@app.get("/providers/status")
def providers_status(user: User = Depends(get_current_user)):
    """Honest provider inventory: derived from configuration only, never from a network probe."""
    gemini = bool(os.environ.get("GEMINI_API_KEY"))
    image_http = bool(os.environ.get("IMAGE_PROVIDER_URL") and os.environ.get("IMAGE_PROVIDER_API_KEY"))
    video_http = bool(os.environ.get("VIDEO_PROVIDER_URL") and os.environ.get("VIDEO_PROVIDER_API_KEY"))
    video_model = os.environ.get("GEMINI_VIDEO_MODEL", "")
    image_ok = gemini or image_http
    video_ok = video_http or bool(gemini and video_model)
    return {
        "image": {
            "configured": image_ok,
            "status": "CONFIGURED" if image_ok else "NOT_CONFIGURED",
            "generic_http": image_http,
            "gemini": gemini,
            "model": os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image") if gemini else None,
        },
        "video": {
            "configured": video_ok,
            "status": "CONFIGURED" if video_ok else "NOT_CONFIGURED",
            "generic_http": video_http,
            "gemini": bool(gemini and video_model),
            "model": video_model or None,
            "message": None if video_ok else "No video model enabled (set GEMINI_VIDEO_MODEL or VIDEO_PROVIDER_*)",
        },
        "discovery": {
            "configured": gemini,
            "status": "CONFIGURED" if gemini else "NOT_CONFIGURED",
            "model": os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-latest"),
        },
        "email": {
            "configured": bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER")),
            "status": "CONFIGURED" if os.environ.get("SMTP_HOST") else "NOT_CONFIGURED",
        },
    }

@app.get("/assets", response_model=list[AssetRead])
def list_assets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(CreativeAsset).filter(CreativeAsset.tenant_id == user.tenant_id).order_by(CreativeAsset.created_at.desc()).all()

@app.post("/assets", response_model=AssetRead)
def create_asset(payload: AssetCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    asset = CreativeAsset(id=f"asset_{uuid.uuid4().hex[:10]}", tenant_id=user.tenant_id, **payload.model_dump())
    db.add(asset)
    db.add(AuditLog(tenant_id=user.tenant_id, actor=user.id, action="CREATE_ASSET", details=asset.id))
    db.commit()
    db.refresh(asset)
    return asset

@app.post("/assets/upload", response_model=AssetRead)
def upload_asset(file: UploadFile = File(...), lead_id: Optional[str] = Form(None), asset_type: str = Form("image"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tenant_dir = os.path.join(UPLOAD_DIR, user.tenant_id)
    os.makedirs(tenant_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    path = os.path.join(tenant_dir, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    url = f"/files/{user.tenant_id}/{filename}"
    asset = CreativeAsset(id=f"asset_{uuid.uuid4().hex[:10]}", tenant_id=user.tenant_id, lead_id=lead_id, asset_type=asset_type, provider="local_upload", url=url, status="UPLOADED")
    db.add(asset)
    db.add(AuditLog(tenant_id=user.tenant_id, actor=user.id, action="UPLOAD_ASSET", details=asset.id))
    db.commit()
    db.refresh(asset)
    return asset

@app.get("/memory", response_model=list[MemoryRead])
def list_memory(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(OperationalMemory).filter(OperationalMemory.tenant_id == user.tenant_id).order_by(OperationalMemory.created_at.desc()).all()

@app.post("/memory", response_model=MemoryRead)
def create_memory(payload: MemoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mem = OperationalMemory(tenant_id=user.tenant_id, **payload.model_dump())
    db.add(mem)
    db.add(AuditLog(tenant_id=user.tenant_id, actor=user.id, action="CREATE_MEMORY", details=str(mem.id)))
    db.commit()
    db.refresh(mem)
    return mem

@app.get("/workspace/summary")
def workspace_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "tenant_id": user.tenant_id,
        "leads": db.query(Lead).filter(Lead.tenant_id == user.tenant_id).count(),
        "assets": db.query(CreativeAsset).filter(CreativeAsset.tenant_id == user.tenant_id).count(),
        "memory_entries": db.query(OperationalMemory).filter(OperationalMemory.tenant_id == user.tenant_id).count(),
        "role": user.role,
    }
