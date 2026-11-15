from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="operator")  # admin, operator, client
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Lead(Base):
    __tablename__ = "leads"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    sector = Column(String)
    country = Column(String)
    city = Column(String)
    website = Column(String)
    phone = Column(String)
    source_url = Column(String)
    verification_status = Column(String, default="DISCOVERED")
    confidence_score = Column(Integer, default=0)
    lead_score = Column(Integer, default=0)
    crm_status = Column(String, default="DISCOVERED")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    state = Column(String, default="PENDING")
    owner_agent = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, index=True)
    actor = Column(String)
    action = Column(String)
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class OperationalMemory(Base):
    __tablename__ = "operational_memory"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    task_id = Column(String, nullable=True)
    agent_name = Column(String)
    result_summary = Column(Text)
    lesson = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class CreativeAsset(Base):
    __tablename__ = "creative_assets"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True)
    asset_type = Column(String, nullable=False)
    provider = Column(String)
    url = Column(String)
    status = Column(String, default="NOT_CONFIGURED")
    created_at = Column(DateTime, default=datetime.utcnow)

class DemoToken(Base):
    __tablename__ = "demo_tokens"
    token = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
