"""Session-based authentication and server-side authorization dependencies.

Sessions are opaque random tokens; only sha256(token) is stored. The cookie is
HttpOnly + SameSite=Lax. All authorization happens here, server-side.
"""
from datetime import timedelta

from fastapi import Depends, Request, Response
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


def _session_ttl() -> timedelta:
    from app.core.config import get_settings

    return timedelta(hours=get_settings().session_ttl_hours)


def _load_session_user(db: OrmSession, token: str) -> tuple[User | None, bool]:
    """Return (user, renewed). Sliding expiry: a session in use is extended
    once less than half of its lifetime remains, so staff are not logged out
    in the middle of a working day; an idle session still expires."""
    token_hash = security.hash_token(token)
    row = db.execute(
        select(DbSession).where(DbSession.token_hash == token_hash)
    ).scalar_one_or_none()
    if row is None:
        return None, False
    now = now_tz()
    if row.expires_at <= now:
        db.execute(delete(DbSession).where(DbSession.id == row.id))
        return None, False
    if not row.user.is_active:
        return None, False
    ttl = _session_ttl()
    renewed = False
    if row.expires_at - now < ttl / 2:
        row.expires_at = now + ttl
        renewed = True
    return row.user, renewed


def get_current_user_optional(
    request: Request, response: Response, db: OrmSession = Depends(get_db, scope="function")
) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    user, renewed = _load_session_user(db, token)
    if renewed:
        set_session_cookie(response, token)
    return user


def set_session_cookie(response: Response, token: str) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )


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
