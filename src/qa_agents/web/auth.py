"""Password hashing and session-based auth for the web app.

A session is a signed cookie (Starlette's ``SessionMiddleware``) holding a
user id — no server-side session store needed for a single local deployment.
"""

from __future__ import annotations

import hashlib
import os
import secrets

from fastapi import Depends, HTTPException, Request

from . import store

_PBKDF2_ITERATIONS = 200_000


def session_secret() -> str:
    """The key that signs session cookies.

    With no ``SESSION_SECRET`` set, generate a random one per process rather
    than falling back to a constant: a constant committed to a public repo
    lets anyone forge a session cookie for any user. The cost of the random
    default is that sessions don't survive a restart.
    """
    return os.environ.get("SESSION_SECRET") or secrets.token_hex(32)

DEFAULT_ADMIN_USERNAME = "admin"


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Return ``(hash, salt)``, generating a random salt if one isn't given."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS
    )
    return digest.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return secrets.compare_digest(candidate, password_hash)


def ensure_default_admin() -> str | None:
    """Seed the admin user the first time the app runs with an empty DB.

    Returns the generated password so the caller can show it once, or None
    when users already exist. The password is random rather than a published
    default, so an exposed instance can't be taken over with a known
    credential before anyone gets round to changing it.
    """
    if store.user_count() > 0:
        return None
    password = secrets.token_urlsafe(12)
    password_hash, salt = hash_password(password)
    store.create_user(DEFAULT_ADMIN_USERNAME, password_hash, salt, "admin")
    return password


def get_current_user(request: Request) -> dict:
    """FastAPI dependency: the logged-in user, or 401."""
    user_id = request.session.get("user_id")
    user = store.get_user(user_id) if user_id is not None else None
    if user is None:
        request.session.clear()  # covers a deleted user with a stale session
        raise HTTPException(status_code=401, detail="נדרשת התחברות")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency: the logged-in user, or 403 if not an admin."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="פעולה זו מיועדת לאדמין בלבד")
    return user


def allowed_agent_names(user: dict) -> list[str] | None:
    """Agent names ``user`` may use, or ``None`` meaning "all agents"."""
    if user["role"] == "admin":
        return None
    return store.get_user_agent_access(user["id"]) or None
