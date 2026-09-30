"""Audit trail for sensitive actions.

Records who did what to which entity, when. Never store clinical note content
or other medical text in the audit log - only entity references and metadata.
"""
from sqlalchemy.orm import Session

from app.core.dates import now_tz
from app.core.models import AuditLog


def log_action(
    db: Session,
    *,
    actor_id: int | None,
    action: str,
    entity: str,
    entity_id: int | None = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            detail=detail,
            ip=ip,
            created_at=now_tz(),
        )
    )
