"""Clinical endpoints: notes, catalog, patient treatments, odontogram."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.clinical import service
from app.core.audit import log_action
from app.core.auth import get_client_ip, get_current_user, require_dentist, require_owner
from app.core.db import get_db
from app.core.errors import AppError
from app.core.models import TreatmentCatalogItem, User
from app.core.money import serialize_amount, to_money

router = APIRouter(prefix="/api/clinical", tags=["clinical"])


# --------------------------------------------------------------------------- #
# Clinical notes
# --------------------------------------------------------------------------- #


class NoteCreate(BaseModel):
    patient_id: int
    motif: str = ""
    diagnostic: str = ""
    traitement: str = ""
    remarques: str = ""


class NoteUpdate(BaseModel):
    motif: str = ""
    diagnostic: str = ""
    traitement: str = ""
    remarques: str = ""


@router.get("/patients/{patient_id}/notes")
def list_notes(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    service.get_patient_or_404(db, patient_id)
    rows = service.notes_history(db, patient_id)
    return {"notes": [service.serialize_note(n) for n in rows]}


@router.get("/patients/{patient_id}/notes/latest")
def latest_note(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    service.get_patient_or_404(db, patient_id)
    note = service.latest_note(db, patient_id)
    return {"note": service.serialize_note(note) if note else None}


@router.post("/notes", status_code=201)
def create_note(
    payload: NoteCreate,
    request: Request,
    user: User = Depends(require_dentist),
    db: OrmSession = Depends(get_db),
):
    data = service.validate_note_input(
        motif=payload.motif,
        diagnostic=payload.diagnostic,
        traitement=payload.traitement,
        remarques=payload.remarques,
    )
    note = service.create_note(db, patient_id=payload.patient_id, data=data, actor_id=user.id)
    log_action(
        db,
        actor_id=user.id,
        action="note_create",
        entity="clinical_note",
        entity_id=note.id,
        detail={"patient_id": note.patient_id},
        ip=get_client_ip(request),
    )
    return {"note": service.serialize_note(note)}


@router.put("/notes/{note_id}")
def update_note(
    note_id: int,
    payload: NoteUpdate,
    request: Request,
    user: User = Depends(require_dentist),
    db: OrmSession = Depends(get_db),
):
    note = service.get_note_or_404(db, note_id)
    data = service.validate_note_input(
        motif=payload.motif,
        diagnostic=payload.diagnostic,
        traitement=payload.traitement,
        remarques=payload.remarques,
    )
    service.update_note(db, note, data=data, actor_id=user.id)
    log_action(
        db,
        actor_id=user.id,
        action="note_update",
        entity="clinical_note",
        entity_id=note.id,
        detail={"patient_id": note.patient_id},
        ip=get_client_ip(request),
    )
    return {"note": service.serialize_note(note)}


# --------------------------------------------------------------------------- #
# Treatment catalog
# --------------------------------------------------------------------------- #


class CatalogItemCreate(BaseModel):
    name: str
    category: str
    default_price: str | int | float = "0"


class CatalogItemUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    default_price: str | int | float | None = None
    is_active: bool | None = None


@router.get("/catalog")
def list_catalog(
    include_inactive: bool = True,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    query = select(TreatmentCatalogItem).order_by(TreatmentCatalogItem.category, TreatmentCatalogItem.name)
    if not include_inactive:
        query = query.where(TreatmentCatalogItem.is_active.is_(True))
    rows = db.execute(query).scalars().all()
    return {"items": [service.serialize_catalog_item(i) for i in rows]}


@router.post("/catalog", status_code=201)
def create_catalog_item(
    payload: CatalogItemCreate,
    request: Request,
    user: User = Depends(require_owner),
    db: OrmSession = Depends(get_db),
):
    item = service.create_catalog_item(
        db, name=payload.name, category=payload.category, default_price=payload.default_price
    )
    log_action(
        db,
        actor_id=user.id,
        action="catalog_create",
        entity="treatment_catalog",
        entity_id=item.id,
        detail={"name": item.name},
        ip=get_client_ip(request),
    )
    return {"item": service.serialize_catalog_item(item)}


@router.put("/catalog/{item_id}")
def update_catalog_item(
    item_id: int,
    payload: CatalogItemUpdate,
    request: Request,
    user: User = Depends(require_owner),
    db: OrmSession = Depends(get_db),
):
    item = service.get_catalog_item_or_404(db, item_id)
    changes = []
    if payload.name is not None and payload.name.strip() and payload.name.strip() != item.name:
        duplicate = db.execute(
            select(TreatmentCatalogItem.id).where(
                func.lower(TreatmentCatalogItem.name) == payload.name.strip().lower(),
                TreatmentCatalogItem.id != item.id,
            )
        ).scalar_one_or_none()
        if duplicate:
            raise AppError("errors.catalog_name_taken", status_code=400, code="duplicate_name")
        item.name = payload.name.strip()
        changes.append("name")
    if payload.category is not None and payload.category != item.category:
        if payload.category not in service.CATALOG_CATEGORIES:
            raise AppError("errors.invalid_category", status_code=400, code="invalid_category")
        item.category = payload.category
        changes.append("category")
    if payload.default_price is not None:
        try:
            new_price = to_money(payload.default_price)
        except ValueError:
            raise AppError("errors.invalid_price", status_code=400, code="invalid_price") from None
        if new_price < 0:
            raise AppError("errors.invalid_price", status_code=400, code="invalid_price")
        if new_price != item.default_price:
            log_action(
                db,
                actor_id=user.id,
                action="price_change",
                entity="treatment_catalog",
                entity_id=item.id,
                detail={"old": serialize_amount(item.default_price), "new": serialize_amount(new_price)},
                ip=get_client_ip(request),
            )
            item.default_price = new_price
            changes.append("default_price")
    if payload.is_active is not None and payload.is_active != item.is_active:
        item.is_active = payload.is_active
        changes.append("is_active")
    db.flush()
    if changes:
        log_action(
            db,
            actor_id=user.id,
            action="catalog_update",
            entity="treatment_catalog",
            entity_id=item.id,
            detail={"fields": changes},
            ip=get_client_ip(request),
        )
    return {"item": service.serialize_catalog_item(item)}


# --------------------------------------------------------------------------- #
# Patient treatments
# --------------------------------------------------------------------------- #


class TreatmentCreate(BaseModel):
    patient_id: int
    catalog_item_id: int | None = None
    name: str | None = None
    category: str | None = None
    price: str | int | float = "0"
    tooth: int | None = None
    note: str = ""


@router.get("/patients/{patient_id}/treatments")
def list_patient_treatments(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    service.get_patient_or_404(db, patient_id)
    return {"treatments": [service.serialize_treatment(t) for t in service.patient_treatments(db, patient_id)]}


@router.post("/treatments", status_code=201)
def add_treatment(
    payload: TreatmentCreate,
    request: Request,
    user: User = Depends(require_dentist),
    db: OrmSession = Depends(get_db),
):
    treatment = service.add_patient_treatment(
        db,
        patient_id=payload.patient_id,
        catalog_item_id=payload.catalog_item_id,
        name=payload.name,
        category=payload.category,
        price=payload.price,
        tooth=payload.tooth,
        note=payload.note,
        actor_id=user.id,
    )
    log_action(
        db,
        actor_id=user.id,
        action="treatment_add",
        entity="patient_treatment",
        entity_id=treatment.id,
        detail={"patient_id": treatment.patient_id, "tooth": treatment.tooth},
        ip=get_client_ip(request),
    )
    return {"treatment": service.serialize_treatment(treatment)}


# --------------------------------------------------------------------------- #
# Odontogram
# --------------------------------------------------------------------------- #


@router.get("/patients/{patient_id}/odontogram")
def get_odontogram(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    service.get_patient_or_404(db, patient_id)
    return {
        "conditions": service.tooth_conditions(db, patient_id),
        "treatments_by_tooth": service.treatments_by_tooth(db, patient_id),
    }


class ToothConditionIn(BaseModel):
    tooth: int
    condition: str
    surface: str = ""


@router.get("/patients/{patient_id}/odontogram/history")
def get_tooth_history(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    service.get_patient_or_404(db, patient_id)
    rows = service.tooth_history(db, patient_id)
    actor_ids = [r.changed_by for r in rows if r.changed_by]
    actors = (
        db.execute(select(User).where(User.id.in_(actor_ids))).scalars().all() if actor_ids else []
    )
    names = {u.id: u.full_name or u.username for u in actors}
    return {
        "history": [
            service.serialize_tooth_history(h, actor_name=names.get(h.changed_by)) for h in rows
        ]
    }


@router.put("/patients/{patient_id}/odontogram")
def set_tooth_condition(
    patient_id: int,
    payload: ToothConditionIn,
    request: Request,
    user: User = Depends(require_dentist),
    db: OrmSession = Depends(get_db),
):
    result = service.set_tooth_condition(
        db,
        patient_id=patient_id,
        tooth=payload.tooth,
        condition=payload.condition,
        surface=payload.surface,
        actor_id=user.id,
    )
    log_action(
        db,
        actor_id=user.id,
        action="tooth_condition_set",
        entity="patient",
        entity_id=patient_id,
        detail={
            "tooth": payload.tooth,
            "condition": payload.condition,
            "surface": payload.surface,
        },
        ip=get_client_ip(request),
    )
    return result
