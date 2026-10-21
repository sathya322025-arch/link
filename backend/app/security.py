import hashlib
import secrets
import base64
import hmac
import struct
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import bcrypt
import jwt
from fastapi import HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

security_bearer = HTTPBearer()

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def generate_secure_token(nbytes: int = 32) -> str:
    """Generates a cryptographically strong URL-safe invitation token."""
    return secrets.token_urlsafe(nbytes)

def hash_token(raw_token: str) -> str:
    """Returns SHA-256 hash of the token for secure storage in the database."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please authenticate again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token signature.",
            headers={"WWW-Authenticate": "Bearer"},
        )

def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """RFC 6238 TOTP verification using HMAC-SHA1 with standard 30s step."""
    if not secret or not code:
        return False
    try:
        # Pad secret to valid Base32 length if necessary
        secret_clean = secret.upper().replace(" ", "")
        padding = 8 - (len(secret_clean) % 8)
        if padding != 8:
            secret_clean += "=" * padding
        key = base64.b32decode(secret_clean, casefold=True)
        
        current_step = int(time.time() // 30)
        code_str = str(code).strip()

        for step in range(current_step - window, current_step + window + 1):
            msg = struct.pack(">Q", step)
            h = hmac.new(key, msg, hashlib.sha1).digest()
            offset = h[19] & 0x0F
            otp = (struct.unpack(">I", h[offset:offset+4])[0] & 0x7FFFFFFF) % 1000000
            if f"{otp:06d}" == code_str:
                return True
        return False
    except Exception:
        return False

