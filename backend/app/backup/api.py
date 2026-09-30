"""Backup API: status, manual 'Sauvegarder maintenant'."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as OrmSession

from app.backup import service
from app.core.audit import log_action
from app.core.auth import get_client_ip, get_current_user, require_owner
from app.core.db import get_db
from app.core.errors import AppError
from app.core.models import User

router = APIRouter(prefix="/api/backup", tags=["backup"])


@router.get("/status")
def status(user: User = Depends(get_current_user), db: OrmSession = Depends(get_db)):
    return service.backup_status(db)


@router.post("/run", status_code=201)
def run_now(
    request: Request,
    user: User = Depends(require_owner),
    db: OrmSession = Depends(get_db),
):
    try:
        record = service.run_backup(db, kind="manual")
    except Exception:
        db.rollback()
        raise AppError("errors.backup_failed", status_code=500, code="backup_failed") from None
    log_action(
        db,
        actor_id=user.id,
        action="backup_manual",
        entity="backup",
        entity_id=record.id,
        detail={"size_bytes": record.size_bytes},
        ip=get_client_ip(request),
    )
    return {
        "backup": {
            "id": record.id,
            "file_path": record.file_path,
            "size_bytes": record.size_bytes,
            "status": record.status,
        }
    }
