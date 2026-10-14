"""Sterilization cycle API endpoints."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession

from app.core.audit import log_action
from app.core.auth import get_client_ip, get_current_user
from app.core.db import get_db
from app.core.models import User
from app.sterilization import service

router = APIRouter(prefix="/api/sterilization", tags=["sterilization"])


class CycleItemIn(BaseModel):
    item_name: str
    quantity: int = 1
    instrument_status: str = "sterile"


class CycleCreate(BaseModel):
    items: list[CycleItemIn]
    autoclave_name: str = ""
    program: str = ""
    notes: str = ""


class CycleFinish(BaseModel):
    result: str = "done"


@router.get("/cycles")
def list_cycles(
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    rows = service.list_cycles(db, status=status)
    return {"cycles": [service.serialize_cycle(c, include_items=False) for c in rows]}


@router.post("/cycles", status_code=201)
def create_cycle(
    payload: CycleCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    row = service.create_cycle(
        db,
        items=[i.model_dump() for i in payload.items],
        autoclave_name=payload.autoclave_name,
        program=payload.program,
        notes=payload.notes,
        operator_id=user.id,
    )
    log_action(
        db,
        actor_id=user.id,
        action="sterilization_create",
        entity="sterilization_cycle",
        entity_id=row.id,
        detail={"cycle_no": row.cycle_no, "items": len(row.items)},
        ip=get_client_ip(request),
    )
    return {"cycle": service.serialize_cycle(row)}


@router.get("/cycles/{cycle_id}")
def get_cycle(
    cycle_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    row = service.get_cycle_or_404(db, cycle_id)
    return {"cycle": service.serialize_cycle(row)}


@router.post("/cycles/{cycle_id}/finish")
def finish_cycle(
    cycle_id: int,
    payload: CycleFinish,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    row = service.get_cycle_or_404(db, cycle_id)
    row = service.finish_cycle(db, row, result=payload.result)
    log_action(
        db,
        actor_id=user.id,
        action="sterilization_finish",
        entity="sterilization_cycle",
        entity_id=row.id,
        detail={"result": row.status},
        ip=get_client_ip(request),
    )
    return {"cycle": service.serialize_cycle(row)}
