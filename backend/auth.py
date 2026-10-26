"""Password hashing and signed login tokens (FR1, NFR6). Standard library only."""

import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend import config
from backend.db import get_db

_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}
_bearer = HTTPBearer(auto_error=False)


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        scheme, salt, digest = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    check = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
    return hmac.compare_digest(check.hex(), digest)


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_token(user_id, role, hours=None):
    payload = {"uid": user_id, "role": role,
               "exp": int(time.time() + 3600 * (hours or config.TOKEN_HOURS))}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(config.SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_token(token):
    try:
        body, sig = token.split(".")
    except ValueError:
        return None
    expected = _b64(hmac.new(config.SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    payload = json.loads(_unb64(body))
    return payload if payload.get("exp", 0) > time.time() else None


def current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer), db=Depends(get_db)):
    payload = read_token(creds.credentials) if creds else None
    if payload is None:
        raise HTTPException(401, "Not logged in or session expired")
    row = db.execute("SELECT user_id, username, role FROM users WHERE user_id = ?",
                     (payload["uid"],)).fetchone()
    if row is None:
        raise HTTPException(401, "User no longer exists")
    return dict(row)


def require_role(*roles):
    def check(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, f"Requires role: {', '.join(roles)}")
        return user
    return check
