from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class LeadCreate(BaseModel):
    name: str
    sector: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    source_url: Optional[str] = None
    verification_status: str = "DISCOVERED"

class LeadRead(LeadCreate):
    id: str
    tenant_id: str
    confidence_score: int = 0
    lead_score: int = 0
    crm_status: str = "DISCOVERED"
    class Config:
        from_attributes = True

class HealthResponse(BaseModel):
    status: str
    database: str
    version: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class DemoTokenCreate(BaseModel):
    lead_id: Optional[str] = None
    expires_in_hours: int = 72

class DemoTokenRead(BaseModel):
    token: str
    lead_id: Optional[str] = None
    expires_at: datetime
    class Config:
        from_attributes = True

class AssetCreate(BaseModel):
    lead_id: Optional[str] = None
    asset_type: str
    provider: Optional[str] = None
    url: Optional[str] = None
    status: str = "NOT_CONFIGURED"

class AssetRead(AssetCreate):
    id: str
    tenant_id: str
    created_at: datetime
    class Config:
        from_attributes = True

class MemoryCreate(BaseModel):
    task_id: Optional[str] = None
    agent_name: Optional[str] = None
    result_summary: Optional[str] = None
    lesson: Optional[str] = None

class MemoryRead(MemoryCreate):
    id: int
    tenant_id: str
    created_at: datetime
    class Config:
        from_attributes = True
