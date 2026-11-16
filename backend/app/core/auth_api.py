"""Auth API: login, logout, session info."""
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as OrmSession

from app.core.audit import log_action
from app.core.auth import (
    COOKIE_NAME,
    get_client_ip,
    get_current_user,
    get_current_user_allow_pending,
    get_current_user_optional,
    purge_expired_sessions,
    require_owner,
)
from app.core.config import get_settings
from app.core.dates import now_tz
from app.core.db import get_db
from app.core.errors import AppError
from app.core.models import Session as DbSession
from app.core.models import User
from app.core.rate_limit import RateLimiter
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_token,
    password_problem,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_login_limiter = RateLimiter(
    get_settings().login_max_attempts, get_settings().login_window_seconds
)


class LoginIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


def _public_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "is_owner": user.is_owner,
        "must_change_password": user.must_change_password,
    }


@router.post("/login")
def login(payload: LoginIn, request: Request, response: Response, db: OrmSession = Depends(get_db)):
    settings = get_settings()
    ip = get_client_ip(request)
    username = payload.username.strip().lower()
    key = f"{username}|{ip}"

    if _login_limiter.is_blocked(key):
        raise AppError("errors.too_many_attempts", status_code=429, code="rate_limited")

    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        _login_limiter.record(key)
        log_action(db, actor_id=user.id if user else None, action="login_failed", entity="user", ip=ip)
        raise AppError("errors.bad_credentials", status_code=401, code="bad_credentials")
    if not user.is_active:
        raise AppError("errors.account_disabled", status_code=403, code="account_disabled")

    _login_limiter.reset(key)
    purge_expired_sessions(db)

    settings_obj = get_settings()
    token = generate_session_token()
    expires = now_tz() + timedelta(hours=settings_obj.session_ttl_hours)
    db.add(
        DbSession(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=expires,
            ip=ip,
        )
    )
    log_action(db, actor_id=user.id, action="login", entity="user", entity_id=user.id, ip=ip)

    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings_obj.session_ttl_hours * 3600,
        path="/",
    )
    return {"user": _public_user(user)}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: OrmSession = Depends(get_db),
    user: User = Depends(get_current_user_allow_pending),
):
    token = request.cookies.get(COOKIE_NAME, "")
    if token:
        db.execute(delete(DbSession).where(DbSession.token_hash == hash_token(token)))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/session")
def session_info(user: User | None = Depends(get_current_user_optional)):
    """Who is logged in, or null. Always 200: the SPA calls this on every cold
    load, and a 401 here only filled the console and server log with noise."""
    return {"user": _public_user(user) if user else None}


@router.get("/me")
def me(user: User = Depends(get_current_user_allow_pending)):
    return {"user": _public_user(user)}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordIn,
    request: Request,
    db: OrmSession = Depends(get_db),
    user: User = Depends(get_current_user_allow_pending),
):
    """Replace the caller's own password. Other sessions of this user are revoked."""
    ip = get_client_ip(request)
    key = f"pwchange:{user.id}|{ip}"
    if _login_limiter.is_blocked(key):
        raise AppError("errors.too_many_attempts", status_code=429, code="rate_limited")
    if not verify_password(payload.current_password, user.password_hash):
        _login_limiter.record(key)
        raise AppError("errors.bad_current_password", status_code=400, code="bad_current_password")
    if payload.new_password == payload.current_password:
        raise AppError("errors.password_same", status_code=400, code="password_same")
    problem = password_problem(payload.new_password)
    if problem:
        raise AppError(f"errors.password_policy_{problem}", status_code=400, code="weak_password")

    _login_limiter.reset(key)
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    current_hash = hash_token(request.cookies.get(COOKIE_NAME, ""))
    db.execute(
        delete(DbSession).where(DbSession.user_id == user.id, DbSession.token_hash != current_hash)
    )
    log_action(db, actor_id=user.id, action="password_changed", entity="user", entity_id=user.id, ip=ip)
    return {"user": _public_user(user)}


@router.get("/users")
def list_users(user: User = Depends(get_current_user), db: OrmSession = Depends(get_db)):
    """User list (for settings page). Any authenticated user may view names/roles."""
    rows = db.execute(select(User).order_by(User.username)).scalars().all()
    return {"users": [_public_user(u) | {"is_active": u.is_active} for u in rows]}


@router.get("/users/count")
def users_count(user: User = Depends(require_owner), db: OrmSession = Depends(get_db)):
    return {"count": db.execute(select(func.count(User.id))).scalar() or 0}
