"""
NEXUS OS — Security, Tenant Isolation & Data Protection Module
Enforces strict PII masking, cryptographic hashing, and authorization controls.
"""

import re
import hashlib
import hmac
import os
import html
import secrets
import warnings
from typing import Optional

# Internal Master Salt for PII hashing. Must be provided via environment in production.
SECRET_SALT = os.environ.get("NEXUS_SECURITY_SALT")
if not SECRET_SALT:
    SECRET_SALT = secrets.token_hex(32)
    warnings.warn(
        "NEXUS_SECURITY_SALT is not set; using an ephemeral random salt. "
        "Set NEXUS_SECURITY_SALT in production for stable hashing.",
        stacklevel=2,
    )

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

def hash_identifier(val) -> str:
    """
    Produces a non-reversible cryptographic HMAC token for deduplication without storing raw identifiers.
    """
    return hmac.new(SECRET_SALT.encode('utf-8'), str(val).encode('utf-8'), hashlib.sha256).hexdigest()

import ipaddress
import socket

def is_safe_url(url: str) -> bool:
    """
    Basic SSRF guard: allow only http/https URLs targeting public hosts.
    """
    if not url:
        return False
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False
    if host.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True

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
