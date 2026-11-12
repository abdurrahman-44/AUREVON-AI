import base64
import bcrypt
import hashlib
import hmac
import jwt
import secrets
import struct
import time
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from backend.app.core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days for standard users


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT token with unique JTI for explicit logout revocation."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.setdefault("jti", str(uuid.uuid4()))
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a signed JWT token."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except (jwt.PyJWTError, Exception):
        return None


def generate_totp_secret() -> str:
    """Generate a RFC 6238-compatible Base32 shared secret (160-bit)."""
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _totp_at_counter(secret: str, counter: int) -> str:
    padded = secret.strip().upper()
    pad_len = (-len(padded)) % 8
    padded += "=" * pad_len
    key = base64.b32decode(padded, casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code_int:06d}"


def verify_totp_code(secret: str, code: str, window: int = 1, period: int = 30) -> bool:
    """Verify a 6-digit RFC 6238 TOTP code allowing +/- window steps."""
    cleaned = (code or "").strip().replace(" ", "")
    if not cleaned.isdigit() or len(cleaned) != 6 or not secret:
        return False
    try:
        current_counter = int(time.time()) // period
        for delta in range(-window, window + 1):
            expected = _totp_at_counter(secret, current_counter + delta)
            if hmac.compare_digest(cleaned, expected):
                return True
    except Exception:
        return False
    return False


def build_otpauth_uri(secret: str, account_name: str, issuer: str = "AUREVON AI") -> str:
    label = urllib.parse.quote(f"{issuer}:{account_name}")
    params = urllib.parse.urlencode({"secret": secret, "issuer": issuer, "algorithm": "SHA1", "digits": 6, "period": 30})
    return f"otpauth://totp/{label}?{params}"
