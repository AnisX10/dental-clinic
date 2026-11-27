"""License endpoints. /status is public (the lock screen needs it); /activate
is the cold-start path when every account is locked out, so it stays
unauthenticated but only accepts a correctly signed licence key.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.errors import AppError
from app.licensing import service

router = APIRouter(prefix="/api/license", tags=["license"])


class ActivateBody(BaseModel):
    key: str


@router.get("/status")
def status() -> dict:
    manager = service.get_manager()
    payload = manager.state.payload or {}
    installation_id = manager.state.installation_id or service.installation_getter()
    return {
        "active": manager.state.active,
        "reason": manager.state.reason,
        "clinic": payload.get("clinic"),
        "dentist": payload.get("dentist"),
        "issued_at": payload.get("iat") or payload.get("issued_at"),
        "installation_id": installation_id,
        "key_id": manager.state.key_id or None,
    }


@router.post("/activate")
def activate(body: ActivateBody) -> dict:
    state = service.get_manager().activate(body.key)
    if not state.active:
        reason = state.reason if state.reason != "missing" else "malformed"
        raise AppError(f"license.reason_{reason}", status_code=400, code="license_rejected")
    return status()

