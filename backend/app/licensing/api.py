"""License endpoints. /status is public (the lock screen needs it); /install
is the cold-start path when every account is locked out, so it stays
unauthenticated but only accepts a correctly signed file.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.errors import AppError
from app.licensing import service

router = APIRouter(prefix="/api/license", tags=["license"])


class InstallBody(BaseModel):
    content: str


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
        "issued_at": payload.get("issued_at"),
        "installation_id": installation_id,
    }


@router.post("/install")
def install(body: InstallBody) -> dict:
    state = service.get_manager().install(body.content)
    if not state.active:
        raise AppError("license.error_rejected", status_code=400, code="license_rejected")
    return status()

