"""Devis API endpoints."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession

from app.core.audit import log_action
from app.core.auth import get_client_ip, get_current_user
from app.core.db import get_db
from app.core.models import User
from app.devis import service

router = APIRouter(prefix="/api/devis", tags=["devis"])


class DevisItemIn(BaseModel):
    catalog_item_id: int | None = None
    label: str
    tooth: int | None = None
    quantity: int = 1
    unit_price: str | int | float = "0"


class DevisCreate(BaseModel):
    patient_id: int
    items: list[DevisItemIn]
    issue_date: str
    due_date: str | None = None
    notes: str = ""


class DevisUpdate(BaseModel):
    items: list[DevisItemIn]
    notes: str | None = None
    due_date: str | None = None


class StatusChange(BaseModel):
    status: str


@router.get("")
def list_devis(
    patient_id: int | None = None,
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    rows = service.list_devis(db, patient_id=patient_id, status=status)
    from sqlalchemy import select

    from app.core.models import Patient

    patient_ids = {r.patient_id for r in rows}
    names: dict[int, str] = {}
    if patient_ids:
        patients = db.execute(select(Patient).where(Patient.id.in_(patient_ids))).scalars().all()
        names = {p.id: f"{p.nom} {p.prenom}" for p in patients}
    out = [service.serialize_devis(d) for d in rows]
    for row, data in zip(rows, out, strict=True):
        data["patient_name"] = names.get(row.patient_id)
    return {"devis": out}


@router.post("", status_code=201)
def create_devis(
    payload: DevisCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    row = service.create_devis(
        db,
        patient_id=payload.patient_id,
        items=[i.model_dump() for i in payload.items],
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        notes=payload.notes,
        actor_id=user.id,
    )
    log_action(
        db,
        actor_id=user.id,
        action="devis_create",
        entity="devis",
        entity_id=row.id,
        detail={"patient_id": row.patient_id, "items": len(row.items)},
        ip=get_client_ip(request),
    )
    return {"devis": service.serialize_devis(row)}


@router.get("/{devis_id}")
def get_devis(
    devis_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    from app.core.services import get_settings_row
    from app.documents.service import clinic_template_data

    row = service.get_devis_or_404(db, devis_id)
    settings = get_settings_row(db)
    return {
        "devis": service.serialize_devis(row),
        "clinic": clinic_template_data(settings),
    }


@router.put("/{devis_id}")
def update_devis(
    devis_id: int,
    payload: DevisUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    row = service.get_devis_or_404(db, devis_id)
    row = service.update_devis(
        db,
        row,
        items=[i.model_dump() for i in payload.items],
        notes=payload.notes,
        due_date=payload.due_date,
        actor_id=user.id,
    )
    log_action(
        db,
        actor_id=user.id,
        action="devis_update",
        entity="devis",
        entity_id=row.id,
        detail={"items": len(row.items)},
        ip=get_client_ip(request),
    )
    return {"devis": service.serialize_devis(row)}


@router.post("/{devis_id}/status")
def change_status(
    devis_id: int,
    payload: StatusChange,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    row = service.get_devis_or_404(db, devis_id)
    row = service.set_status(db, row, new_status=payload.status)
    log_action(
        db,
        actor_id=user.id,
        action="devis_status",
        entity="devis",
        entity_id=row.id,
        detail={"status": row.status},
        ip=get_client_ip(request),
    )
    return {"devis": service.serialize_devis(row)}
