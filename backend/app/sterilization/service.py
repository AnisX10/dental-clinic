"""Sterilization cycle traceability service."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.core.dates import now_tz
from app.core.errors import AppError
from app.core.models import SterilizationCycle, SterilizationCycleItem

STATUSES = ("in_progress", "done", "failed")
ITEM_STATUSES = ("sterile", "failed")


def next_cycle_no(db: OrmSession, started_at: datetime) -> str:
    """Human cycle number S-YYYYMMDD-###, per calendar day; sequential + zero-pad."""
    day = started_at.strftime("%Y%m%d")
    prefix = f"S-{day}-"
    count = (
        db.execute(
            select(func.count())
            .select_from(SterilizationCycle)
            .where(SterilizationCycle.cycle_no.like(f"{prefix}%"))
        ).scalar()
        or 0
    )
    return f"{prefix}{count + 1:03d}"


def _validate_items(items: list[dict]) -> list[dict]:
    clean = []
    for raw in items[:60]:
        if not isinstance(raw, dict):
            raise AppError("errors.invalid_sterilization_item", status_code=400, code="invalid_item")
        name = str(raw.get("item_name", "")).strip()
        if not name:
            raise AppError("errors.invalid_sterilization_item", status_code=400, code="invalid_item")
        qty = raw.get("quantity", 1)
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1 or qty > 999:
            raise AppError("errors.invalid_sterilization_item", status_code=400, code="invalid_item")
        instrument_status = raw.get("instrument_status", "sterile")
        if instrument_status not in ITEM_STATUSES:
            raise AppError("errors.invalid_sterilization_item", status_code=400, code="invalid_item")
        clean.append({"item_name": name[:160], "quantity": qty, "instrument_status": instrument_status})
    return clean


def create_cycle(db: OrmSession, *, items: list[dict], autoclave_name: str = "", program: str = "", notes: str = "", operator_id: int | None) -> SterilizationCycle:
    clean = _validate_items(items)
    started_at = now_tz()
    cycle = SterilizationCycle(
        cycle_no=next_cycle_no(db, started_at),
        status="in_progress",
        started_at=started_at,
        operator_id=operator_id,
        autoclave_name=str(autoclave_name).strip()[:80],
        program=str(program).strip()[:80],
        notes=str(notes).strip()[:2000],
    )
    db.add(cycle)
    db.flush()
    for item in clean:
        db.add(
            SterilizationCycleItem(
                cycle_id=cycle.id,
                item_name=item["item_name"],
                quantity=item["quantity"],
                instrument_status=item["instrument_status"],
            )
        )
    db.flush()
    return cycle


def get_cycle_or_404(db: OrmSession, cycle_id: int) -> SterilizationCycle:
    row = db.get(SterilizationCycle, cycle_id)
    if row is None:
        raise AppError("errors.sterilization_not_found", status_code=404, code="sterilization_not_found")
    return row


def finish_cycle(db: OrmSession, row: SterilizationCycle, *, result: str = "done") -> SterilizationCycle:
    if row.status != "in_progress":
        raise AppError("errors.sterilization_already_finished", status_code=400, code="sterilization_finished")
    if result not in ("done", "failed"):
        raise AppError("errors.invalid_status", status_code=400, code="invalid_status")
    # If any instrument in the cycle failed but the operator tries to close as
    # done, require an explicit re-check (guard against data-entry mistakes).
    failed_items = db.execute(
        select(func.count())
        .select_from(SterilizationCycleItem)
        .where(SterilizationCycleItem.cycle_id == row.id, SterilizationCycleItem.instrument_status == "failed")
    ).scalar() or 0
    if result == "done" and failed_items:
        raise AppError(
            "errors.sterilization_failed_items",
            status_code=400,
            code="sterilization_failed_items",
            values={"failed": int(failed_items)},
        )
    row.status = result
    row.finished_at = now_tz()
    db.flush()
    return row


def list_cycles(db: OrmSession, *, status: str | None = None, limit: int = 60) -> list[SterilizationCycle]:
    query = select(SterilizationCycle).order_by(SterilizationCycle.started_at.desc(), SterilizationCycle.id.desc()).limit(limit)
    if status in STATUSES:
        query = query.where(SterilizationCycle.status == status)
    return list(db.execute(query).scalars().all())


def serialize_cycle(row: SterilizationCycle, *, include_items: bool = True) -> dict:
    data = {
        "id": row.id,
        "cycle_no": row.cycle_no,
        "status": row.status,
        "started_at": row.started_at.isoformat(),
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "autoclave_name": row.autoclave_name,
        "program": row.program,
        "notes": row.notes,
        "operator_id": row.operator_id,
    }
    if include_items:
        data["items"] = [
            {
                "id": item.id,
                "item_name": item.item_name,
                "quantity": item.quantity,
                "instrument_status": item.instrument_status,
            }
            for item in row.items
        ]
    return data
