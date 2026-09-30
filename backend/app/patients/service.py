"""Patient business logic: validation, creation, search, medical profile."""
import re
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as OrmSession

from app.core.errors import AppError
from app.core.models import Attachment, MedicalProfile, Patient
from app.core.services import next_patient_code

PHONE_RE = re.compile(r"^\+?[0-9][0-9 ]{7,19}$")
# Stored attachment names are generated UUID hex + whitelisted extension.
STORED_NAME_RE = re.compile(r"^[a-f0-9]{32}\.(jpg|jpeg|png|webp|pdf)$")

ALLOWED_MIME = {
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
    "image/webp": (".webp",),
    "application/pdf": (".pdf",),
}


def validate_phone(value: str) -> str:
    phone = re.sub(r"\s+", " ", (value or "").strip())
    if not PHONE_RE.match(phone):
        raise AppError("errors.invalid_phone", status_code=400, code="invalid_phone")
    return phone


def validate_patient_input(*, nom: str, prenom: str, telephone: str) -> dict:
    nom = (nom or "").strip()
    prenom = (prenom or "").strip()
    if not nom or not prenom:
        raise AppError("errors.name_required", status_code=400, code="name_required")
    phone = validate_phone(telephone)
    return {"nom": nom, "prenom": prenom, "telephone": phone}


def create_patient(db: OrmSession, *, data: dict, extra: dict | None = None) -> Patient:
    fields = validate_patient_input(
        nom=data.get("nom", ""), prenom=data.get("prenom", ""), telephone=data.get("telephone", "")
    )
    patient = Patient(
        code=next_patient_code(db),
        **fields,
        telephone2=(extra or {}).get("telephone2", ""),
        adresse=(extra or {}).get("adresse", ""),
        wilaya=(extra or {}).get("wilaya", ""),
        notes=(extra or {}).get("notes", ""),
    )
    db.add(patient)
    db.flush()
    # Medical profile exists from day one (all-negative) for simple editing.
    db.add(MedicalProfile(patient_id=patient.id))
    db.flush()
    return patient


def search_patients(
    db: OrmSession, *, q: str = "", page: int = 1, per_page: int = 30
) -> tuple[list[Patient], int]:
    query = select(Patient).where(Patient.is_active.is_(True))
    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        query = query.where(
            or_(
                Patient.nom.ilike(like),
                Patient.prenom.ilike(like),
                Patient.telephone.ilike(like),
                Patient.code.ilike(like),
            )
        )
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    rows = (
        query.order_by(Patient.nom.asc(), Patient.prenom.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return list(db.execute(rows).scalars().all()), total


def get_patient_or_404(db: OrmSession, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None or not patient.is_active:
        raise AppError("errors.patient_not_found", status_code=404, code="patient_not_found")
    return patient


def get_or_create_medical(db: OrmSession, patient: Patient) -> MedicalProfile:
    if patient.medical is None:
        row = MedicalProfile(patient_id=patient.id)
        db.add(row)
        db.flush()
        return row
    return patient.medical


def save_attachment_file(patient_id: int, stored_name: str, content: bytes) -> Path:
    from app.core.config import get_settings

    if not STORED_NAME_RE.match(stored_name):
        raise AppError("errors.invalid_file", status_code=400, code="invalid_file")
    directory = Path(get_settings().attachments_dir) / str(patient_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / stored_name
    path.write_bytes(content)
    return path


def delete_attachment_file(patient_id: int, stored_name: str) -> None:
    from app.core.config import get_settings

    path = Path(get_settings().attachments_dir) / str(patient_id) / stored_name
    if STORED_NAME_RE.match(stored_name) and path.is_file():
        path.unlink()


def serialize_attachment(a: Attachment) -> dict:
    return {
        "id": a.id,
        "patient_id": a.patient_id,
        "original_name": a.original_name,
        "mime_type": a.mime_type,
        "size_bytes": a.size_bytes,
        "created_at": a.created_at.isoformat(),
    }


def patient_brief(p: Patient) -> dict:
    """Lightweight patient info used in appointments/payments responses."""
    return {
        "id": p.id,
        "code": p.code,
        "nom": p.nom,
        "prenom": p.prenom,
        "telephone": p.telephone,
    }
