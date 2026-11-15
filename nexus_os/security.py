"""
NEXUS OS — Security, Tenant Isolation & Data Protection Module
Enforces strict PII masking, cryptographic hashing, and authorization controls.
"""

import re
import hashlib
import hmac
import os
import html
from typing import Optional

# Internal Master Salt for PII hashing (if not set in env)
SECRET_SALT = os.environ.get("NEXUS_SECURITY_SALT", "nexus_sovereign_salt_2026_secure")

def mask_phone(phone: Optional[str]) -> str:
    """
    Masks a telephone number for safe display in logs and public UI.
    Example: +201210237652 -> +2012****7652
    """
    if not phone:
        return "غير متوفر"
    clean = re.sub(r'[^0-9+]', '', str(phone))
    if len(clean) <= 6:
        return "****"
    # Keep country code/first 5 chars and last 3 chars
    prefix = clean[:5]
    suffix = clean[-3:]
    return f"{prefix}****{suffix}"

def mask_email(email: Optional[str]) -> str:
    """
    Masks email address for logs and non-privileged displays.
    Example: ahmed.morgan2009@gmail.com -> ah***09@gmail.com
    """
    if not email or '@' not in email:
        return "غير متوفر"
    parts = email.split('@')
    name, domain = parts[0], parts[1]
    if len(name) <= 3:
        masked_name = name[0] + "***"
    else:
        masked_name = name[:2] + "***" + name[-2:]
    return f"{masked_name}@{domain}"

def sanitize_input(text: Optional[str]) -> str:
    """
    Sanitizes user and API string inputs against XSS and injection attacks.
    """
    if not text:
        return ""
    return html.escape(str(text).strip())

def hash_identifier(val: str) -> str:
    """
    Produces a non-reversible cryptographic HMAC token for deduplication without storing raw identifiers.
    """
    return hmac.new(SECRET_SALT.encode('utf-8'), val.encode('utf-8'), hashlib.sha256).hexdigest()

def check_tenant_access(requested_tenant_id: str, authenticated_tenant_id: str) -> bool:
    """
    Strict tenant boundary verification. Prevents cross-tenant data leaks.
    """
    if not requested_tenant_id or not authenticated_tenant_id:
        return False
    return requested_tenant_id == authenticated_tenant_id

def is_authorized_operation(action: str, requires_approval: bool = True) -> bool:
    """
    Gates risky operations (such as live ad spend or external broadcast) requiring explicit human approval.
    """
    high_risk_actions = {
        "OUTREACH_SEND_WHATSAPP",
        "OUTREACH_SEND_EMAIL",
        "PUBLISH_CAMPAIGN_PAID",
        "SIGN_CLIENT_CONTRACT",
        "MODIFY_PRODUCTION_SECURITY"
    }
    if action in high_risk_actions:
        return not requires_approval
    return True
