"""DSP & CNAS register API endpoints."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession

from app.core.audit import log_action
from app.core.auth import get_client_ip, get_current_user
from app.core.dates import now_tz
from app.core.db import get_db
from app.core.models import Patient, User
from app.dsp import service
from app.dsp.service import DEADLINE_DAYS

router = APIRouter(prefix="/api/dsp", tags=["dsp"])


class DspCreate(BaseModel):
    patient_id: int
    caisse: str
    insured_nin: str = ""
    affiliation_no: str = ""
    beneficiary_relation: str = "assure"
    first_act_date: str
    notes: str = ""


class DspUpdate(BaseModel):
    caisse: str | None = None
    insured_nin: str | None = None
    affiliation_no: str | None = None
    beneficiary_relation: str | None = None
    first_act_date: str | None = None
    notes: str | None = None


class ActCreate(BaseModel):
    act_date: str
    tooth: int | None = None
    act_label: str
    act_code: str = ""
    coefficient: float = 0
    fee: float = 0


class ActUpdate(BaseModel):
    act_date: str | None = None
    tooth: int | None = None
    act_label: str | None = None
    act_code: str | None = None
    coefficient: float | None = None
    fee: float | None = None
    model_config = {"extra": "forbid"}


@router.get("")
def list_dsp(
    caisse: str | None = None,
    q: str = "",
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    return {"registries": service.list_registries(db, caisse=caisse, q=q)}


@router.get("/meta")
def dsp_meta(user: User = Depends(get_current_user)):
    return {
        "caisses": list(service.CAISSES),
        "beneficiary_relations": list(service.BENEFICIARY_RELATIONS),
        "deadline_days": DEADLINE_DAYS,
    }


@router.post("", status_code=201)
def create_dsp(
    payload: DspCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    data = service.validate_registry_input(
        db,
        patient_id=payload.patient_id,
        caisse=payload.caisse,
        first_act_date=payload.first_act_date,
        beneficiary_relation=payload.beneficiary_relation,
    )
    row = service.create_registry(
        db,
        data={
            **data,
            "insured_nin": payload.insured_nin,
            "affiliation_no": payload.affiliation_no,
            "notes": payload.notes,
        },
        actor_id=user.id,
    )
    log_action(
        db,
        actor_id=user.id,
        action="dsp_create",
        entity="dsp_registry",
        entity_id=row.id,
        detail={"patient_id": row.patient_id, "caisse": row.caisse},
        ip=get_client_ip(request),
    )
    return {"registry": service.serialize_registry(row)}


@router.get("/{dsp_id}")
def get_dsp(
    dsp_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    from datetime import timedelta

    from app.core.services import get_settings_row
    from app.documents.service import clinic_template_data

    settings = get_settings_row(db)
    row = service.get_registry_or_404(db, dsp_id)
    acts = service.registry_acts(db, dsp_id)
    patient = db.get(Patient, row.patient_id)

    deadline = row.first_act_date + timedelta(days=DEADLINE_DAYS)
    registry = service.serialize_registry(row)
    if patient is not None:
        registry["patient"] = {
            "id": patient.id,
            "code": patient.code,
            "nom": patient.nom,
            "prenom": patient.prenom,
            "telephone": patient.telephone,
        }
    return {
        "registry": registry,
        "acts": [service.serialize_act(a) for a in acts],
        "deadline_date": deadline.isoformat(),
        "days_to_deadline": (deadline - now_tz().date()).days,
        "deadline_days": DEADLINE_DAYS,
        "clinic": clinic_template_data(settings),
    }


@router.put("/{dsp_id}")
def update_dsp(
    dsp_id: int,
    payload: DspUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    row = service.get_registry_or_404(db, dsp_id)
    row = service.update_registry(db, row, payload=payload.model_dump(exclude_unset=True))
    log_action(
        db,
        actor_id=user.id,
        action="dsp_update",
        entity="dsp_registry",
        entity_id=row.id,
        detail={"fields": sorted(payload.model_dump(exclude_unset=True))},
        ip=get_client_ip(request),
    )
    return {"registry": service.serialize_registry(row)}


@router.post("/{dsp_id}/acts", status_code=201)
def add_act(
    dsp_id: int,
    payload: ActCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    registry = service.get_registry_or_404(db, dsp_id)
    act = service.create_act(db, registry, payload=payload.model_dump(), actor_id=user.id)
    log_action(
        db,
        actor_id=user.id,
        action="dsp_act_create",
        entity="dsp_act",
        entity_id=act.id,
        detail={"dsp_id": registry.id, "tooth": act.tooth},
        ip=get_client_ip(request),
    )
    return {"act": service.serialize_act(act)}


@router.put("/{dsp_id}/acts/{act_id}")
def edit_act(
    dsp_id: int,
    act_id: int,
    payload: ActUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    registry = service.get_registry_or_404(db, dsp_id)
    act = service.get_act_or_404(db, registry, act_id)
    row_update = service.update_registry  # noqa: F841  (documentation of editing flow)
    data = payload.model_dump(exclude_unset=True)
    if "act_label" in data and data["act_label"] is not None:
        label = str(data["act_label"]).strip()
        if not label:
            from app.core.errors import AppError

            raise AppError(
                "errors.dsp_act_label_required", status_code=400, code="dsp_act_label_required"
            )
        act.act_label = label[:200]
    if "act_date" in data and data["act_date"] is not None:
        act.act_date = service._parse_date(data["act_date"], field_key="errors.invalid_date")
    if "tooth" in data:
        act.tooth = service._validate_tooth(data["tooth"])
    if "act_code" in data and data["act_code"] is not None:
        act.act_code = str(data["act_code"]).strip()[:20]
    if "coefficient" in data and data["coefficient"] is not None:
        act.coefficient = service._dec(data["coefficient"])
    if "fee" in data and data["fee"] is not None:
        act.fee = service._dec(data["fee"])
    registry.updated_at = now_tz()
    db.flush()
    log_action(
        db,
        actor_id=user.id,
        action="dsp_act_update",
        entity="dsp_act",
        entity_id=act.id,
        detail={"dsp_id": registry.id},
        ip=get_client_ip(request),
    )
    return {"act": service.serialize_act(act)}


@router.delete("/{dsp_id}/acts/{act_id}", status_code=204)
def delete_act_endpoint(
    dsp_id: int,
    act_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    registry = service.get_registry_or_404(db, dsp_id)
    service.delete_act(db, registry, act_id)
    log_action(
        db,
        actor_id=user.id,
        action="dsp_act_delete",
        entity="dsp_act",
        entity_id=act_id,
        detail={"dsp_id": dsp_id},
        ip=get_client_ip(request),
    )
