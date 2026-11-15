"""Security helpers for password hashing and lightweight HMAC tokens."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict, Optional

from app.config import settings


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Create a salted PBKDF2-HMAC-SHA256 password hash."""
    salt_val = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_val.encode("utf-8"), 100_000)
    return f"{salt_val}${base64.b64encode(dk).decode('ascii')}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored salted PBKDF2 hash."""
    if "$" not in stored_hash:
        return False
    salt_val, _ = stored_hash.split("$", 1)
    return hmac.compare_digest(hash_password(password, salt_val), stored_hash)


def create_access_token(subject: str, role: str = "counsel", expires_seconds: int = 86400) -> str:
    """Create a signed URL-safe token."""
    payload = {"sub": subject, "role": role, "exp": int(time.time()) + expires_seconds}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a signed token."""
    if "." not in token:
        return None
    raw, sig = token.split(".", 1)
    expected = hmac.new(settings.SECRET_KEY.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    padding = "=" * (-len(raw) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw + padding).decode("utf-8"))
    except Exception:
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload
