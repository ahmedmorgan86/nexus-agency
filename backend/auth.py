import os
import uuid
import warnings
import hashlib
import secrets
from datetime import datetime, timedelta
from jose import JWTError, jwt
from models import User

SECRET_KEY = os.environ.get("JWT_SECRET")
if not SECRET_KEY:
    SECRET_KEY = "dev-insecure-secret-change-me"
    warnings.warn("JWT_SECRET not set; using insecure dev secret.", stacklevel=2)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return f"pbkdf2_sha256${salt}${digest}"

def verify_password(plain: str, hashed: str) -> bool:
    try:
        _, salt, digest = hashed.split("$", 2)
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 100000).hex()
    return secrets.compare_digest(calc, digest)

def create_access_token(subject: str, tenant_id: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "tenant_id": tenant_id, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
