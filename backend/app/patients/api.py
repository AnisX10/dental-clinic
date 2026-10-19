"""Patient endpoints."""

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession

from app.core.audit import log_action
from app.core.auth import get_client_ip, get_current_user
from app.core.config import get_settings
from app.core.dates import now_tz
from app.core.db import get_db
from app.core.errors import AppError
from app.core.models import Attachment, User
from app.patients import service

router = APIRouter(prefix="/api/patients", tags=["patients"])

MEDICAL_FIELDS = (
    "diabete",
    "hypertension",
    "maladie_cardiaque",
    "grossesse",
    "anticoagulants",
    "asthme",
    "epilepsie",
    "allergies",
)


class PatientCreate(BaseModel):
    nom: str
    prenom: str
    telephone: str
    telephone2: str = ""
    adresse: str = ""
    wilaya: str = ""
    notes: str = ""
    date_naissance: str = ""


class PatientUpdate(BaseModel):
    nom: str
    prenom: str
    telephone: str
    telephone2: str = ""
    adresse: str = ""
    wilaya: str = ""
    notes: str = ""
    date_naissance: str = ""


class MedicalUpdate(BaseModel):
    diabete: bool = False
    hypertension: bool = False
    maladie_cardiaque: bool = False
    grossesse: bool = False
    anticoagulants: bool = False
    asthme: bool = False
    epilepsie: bool = False
    allergies: bool = False
    autre: str = ""


@router.get("")
def list_patients(
    q: str = "",
    page: int = 1,
    per_page: int = 30,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    page = max(1, page)
    per_page = min(max(1, per_page), 100)
    rows, total = service.search_patients(db, q=q, page=page, per_page=per_page)
    return {
        "patients": [service.serialize_patient(p) for p in rows],
        "pagination": {"total": total, "page": page, "per_page": per_page},
    }


@router.post("", status_code=201)
def create_patient(
    payload: PatientCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    patient = service.create_patient(db, data=payload.model_dump())
    log_action(
        db,
        actor_id=user.id,
        action="patient_create",
        entity="patient",
        entity_id=patient.id,
        ip=get_client_ip(request),
    )
    return {"patient": service.serialize_patient(patient, include_medical=True)}


@router.get("/dormant")
def list_dormant_patients(
    days: int = 180,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    """Call-back list (relance): active patients not seen for `days`+ days."""
    days = min(max(1, days), 3650)
    limit = min(max(1, limit), 100)
    return {"patients": service.dormant_patients(db, days=days, limit=limit)}


@router.get("/{patient_id}")
def get_patient(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    patient = service.get_patient_or_404(db, patient_id)
    return {"patient": service.serialize_patient(patient, include_medical=True)}


@router.put("/{patient_id}")
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    patient = service.get_patient_or_404(db, patient_id)
    fields = service.validate_patient_input(
        nom=payload.nom, prenom=payload.prenom, telephone=payload.telephone,
        date_naissance=payload.date_naissance,
    )
    changed = []
    for key, value in {
        **fields,
        "telephone2": payload.telephone2.strip(),
        "adresse": payload.adresse.strip(),
        "wilaya": payload.wilaya.strip(),
        "notes": payload.notes.strip(),
    }.items():
        if getattr(patient, key) != value:
            setattr(patient, key, value)
            changed.append(key)
    patient.updated_at = now_tz()
    if changed:
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise AppError("errors.patient_exists", status_code=400, code="patient_exists") from None
        log_action(
            db,
            actor_id=user.id,
            action="patient_update",
            entity="patient",
            entity_id=patient.id,
            detail={"fields": changed},
            ip=get_client_ip(request),
        )
    return {"patient": service.serialize_patient(patient, include_medical=True)}


@router.get("/{patient_id}/medical")
def get_medical(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    patient = service.get_patient_or_404(db, patient_id)
    medical = service.get_or_create_medical(db, patient)
    return {"medical": service.serialize_medical(medical)}


@router.put("/{patient_id}/medical")
def update_medical(
    patient_id: int,
    payload: MedicalUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    patient = service.get_patient_or_404(db, patient_id)
    medical = service.get_or_create_medical(db, patient)
    for field in MEDICAL_FIELDS:
        setattr(medical, field, bool(getattr(payload, field)))
    medical.autre = payload.autre.strip()
    medical.updated_at = now_tz()
    log_action(
        db,
        actor_id=user.id,
        action="medical_update",
        entity="patient",
        entity_id=patient.id,
        ip=get_client_ip(request),
    )
    return {"medical": service.serialize_medical(medical)}


@router.post("/{patient_id}/attachments", status_code=201)
def upload_attachment(
    patient_id: int,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    patient = service.get_patient_or_404(db, patient_id)

    mime = (file.content_type or "").lower()
    if mime not in service.ALLOWED_MIME:
        raise AppError("errors.unsupported_file_type", status_code=400, code="unsupported_type")
    max_mb = get_settings().max_attachment_mb
    max_bytes = max(1, max_mb) * 1024 * 1024
    content = file.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise AppError("errors.file_too_large", status_code=400, code="file_too_large", values={"max_mb": max_mb})
    if not content:
        raise AppError("errors.empty_file", status_code=400, code="empty_file")

    import uuid

    ext = service.ALLOWED_MIME[mime][0]
    stored_name = uuid.uuid4().hex + ext
    original = (file.filename or "fichier").strip()[:200] or "fichier"
    service.save_attachment_file(patient.id, stored_name, content)
    attachment = Attachment(
        patient_id=patient.id,
        stored_name=stored_name,
        original_name=original,
        mime_type=mime,
        size_bytes=len(content),
        uploaded_by=user.id,
    )
    db.add(attachment)
    db.flush()
    log_action(
        db,
        actor_id=user.id,
        action="attachment_upload",
        entity="patient",
        entity_id=patient.id,
        detail={"attachment_id": attachment.id, "mime": mime},
        ip=get_client_ip(request),
    )
    return {"attachment": service.serialize_attachment(attachment)}


@router.get("/{patient_id}/attachments")
def list_attachments(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    service.get_patient_or_404(db, patient_id)
    rows = (
        db.execute(
            select(Attachment)
            .where(Attachment.patient_id == patient_id)
            .order_by(Attachment.created_at.desc())
        )
        .scalars()
        .all()
    )
    return {"attachments": [service.serialize_attachment(a) for a in rows]}


@router.get("/{patient_id}/attachments/{attachment_id}/file")
def download_attachment(
    patient_id: int,
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    service.get_patient_or_404(db, patient_id)
    row = db.get(Attachment, attachment_id)
    if row is None or row.patient_id != patient_id:
        raise AppError("errors.attachment_not_found", status_code=404, code="not_found")
    from pathlib import Path

    from app.core.config import get_settings

    path = Path(get_settings().attachments_dir) / str(patient_id) / row.stored_name
    if not path.is_file():
        raise AppError("errors.attachment_file_missing", status_code=404, code="file_missing")
    from fastapi.responses import FileResponse

    return FileResponse(path, media_type=row.mime_type, filename=row.original_name)


@router.delete("/{patient_id}/attachments/{attachment_id}", status_code=204)
def delete_attachment(
    patient_id: int,
    attachment_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    service.get_patient_or_404(db, patient_id)
    row = db.get(Attachment, attachment_id)
    if row is None or row.patient_id != patient_id:
        raise AppError("errors.attachment_not_found", status_code=404, code="not_found")
    service.delete_attachment_file(patient_id, row.stored_name)
    db.delete(row)
    log_action(
        db,
        actor_id=user.id,
        action="attachment_delete",
        entity="patient",
        entity_id=patient_id,
        detail={"attachment_id": attachment_id},
        ip=get_client_ip(request),
    )
    return None
