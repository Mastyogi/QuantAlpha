"""
JWT session management for the web dashboard.
Uses PyJWT (available in environment) — pure stdlib crypto for signing.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

# Try PyJWT first, fallback to manual implementation
try:
    import jwt as _pyjwt
    _HAS_PYJWT = True
except ImportError:
    _HAS_PYJWT = False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    s += "=" * (padding % 4)
    return base64.urlsafe_b64decode(s)


def create_token(payload: Dict[str, Any], secret: str, expire_hours: int = 24) -> str:
    """Create a signed JWT token."""
    now = int(time.time())
    data = {
        **payload,
        "iat": now,
        "exp": now + expire_hours * 3600,
    }
    if _HAS_PYJWT:
        return _pyjwt.encode(data, secret, algorithm="HS256")

    # Manual HS256 implementation
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body   = _b64url_encode(json.dumps(data).encode())
    msg    = f"{header}.{body}".encode()
    sig    = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
    return f"{header}.{body}.{_b64url_encode(sig)}"


def decode_token(token: str, secret: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT token. Returns None if invalid/expired."""
    try:
        if _HAS_PYJWT:
            return _pyjwt.decode(token, secret, algorithms=["HS256"])

        # Manual verification
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        msg = f"{header}.{body}".encode()
        expected_sig = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def get_token_from_request(cookies: dict, headers: dict, secret: str) -> Optional[Dict]:
    """Extract and validate JWT from cookie or Authorization header."""
    # Try cookie first
    token = cookies.get("auth_token")
    if not token:
        # Try Authorization: Bearer <token>
        auth = headers.get("Authorization", headers.get("authorization", ""))
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        return None
    return decode_token(token, secret)
