"""Session-based authentication and server-side authorization dependencies.

Sessions are opaque random tokens; only sha256(token) is stored. The cookie is
HttpOnly + SameSite=Lax. All authorization happens here, server-side.
"""
from fastapi import Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as OrmSession

from app.core import security
from app.core.dates import now_tz
from app.core.db import get_db
from app.core.errors import AppError
from app.core.models import Session as DbSession
from app.core.models import User

COOKIE_NAME = "clinic_session"


def get_client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return ""


def _load_session_user(db: OrmSession, token: str) -> User | None:
    token_hash = security.hash_token(token)
    row = db.execute(
        select(DbSession).where(DbSession.token_hash == token_hash)
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.expires_at <= now_tz():
        db.execute(delete(DbSession).where(DbSession.id == row.id))
        return None
    return row.user if row.user.is_active else None


def get_current_user_optional(request: Request, db: OrmSession = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return _load_session_user(db, token)


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    if user is None:
        raise AppError("errors.unauthorized", status_code=401, code="unauthorized")
    return user


def require_active_user(user: User = Depends(get_current_user)) -> User:
    return user


def require_dentist(user: User = Depends(get_current_user)) -> User:
    """Dentist-only endpoints (clinical content management)."""
    if user.role != "dentiste":
        raise AppError("errors.forbidden", status_code=403, code="forbidden")
    return user


def require_owner(user: User = Depends(get_current_user)) -> User:
    """Owner-level actions: price edits, critical settings."""
    if not user.is_owner:
        raise AppError("errors.forbidden_owner", status_code=403, code="forbidden_owner")
    return user


def purge_expired_sessions(db: OrmSession) -> None:
    db.execute(delete(DbSession).where(DbSession.expires_at <= now_tz()))
