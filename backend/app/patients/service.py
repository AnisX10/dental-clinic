"""Patient business logic: validation, creation, search, medical profile."""
import re
from datetime import date
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession

from app.core.api_utils import serialize_medical, serialize_patient  # noqa: F401 (re-exported)
from app.core.dates import now_tz
from app.core.errors import AppError
from app.core.models import Attachment, MedicalProfile, Patient, PatientTreatment, Payment
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


def validate_patient_input(*, nom: str, prenom: str, telephone: str, date_naissance: str | None = None) -> dict:
    nom = (nom or "").strip()
    prenom = (prenom or "").strip()
    if not nom or not prenom:
        raise AppError("errors.name_required", status_code=400, code="name_required")
    phone = validate_phone(telephone)
    out = {"nom": nom, "prenom": prenom, "telephone": phone}
    bday = (date_naissance or "").strip()
    if bday:
        try:
            parsed = date.fromisoformat(bday)
        except ValueError:
            raise AppError("errors.invalid_date", status_code=400, code="invalid_date") from None
        if parsed > date.today():
            raise AppError("errors.invalid_date", status_code=400, code="invalid_date")
        out["date_naissance"] = parsed
    return out


def create_patient(db: OrmSession, *, data: dict, extra: dict | None = None) -> Patient:
    fields = validate_patient_input(
        nom=data.get("nom", ""), prenom=data.get("prenom", ""), telephone=data.get("telephone", ""),
        date_naissance=data.get("date_naissance"),
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
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(
            "errors.patient_exists", status_code=400, code="patient_exists"
        ) from None
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


def dormant_patients(db: OrmSession, *, days: int = 180, limit: int = 20) -> list[dict]:
    """Active patients whose last visit (treatment or payment) is older than
    `days` — the call-back list (relance). Registration date counts as a visit
    floor, so brand-new patients never appear here."""
    rows = list(
        db.execute(
            select(Patient)
            .where(Patient.is_active.is_(True))
            .order_by(Patient.nom.asc(), Patient.prenom.asc())
        )
        .scalars()
        .all()
    )
    if not rows:
        return []
    ids = [p.id for p in rows]
    last_treatment = dict(
        db.execute(
            select(PatientTreatment.patient_id, func.max(PatientTreatment.created_at))
            .where(PatientTreatment.patient_id.in_(ids))
            .group_by(PatientTreatment.patient_id)
        ).all()
    )
    last_payment = dict(
        db.execute(
            select(Payment.patient_id, func.max(Payment.created_at))
            .where(Payment.patient_id.in_(ids))
            .group_by(Payment.patient_id)
        ).all()
    )
    today = now_tz().date()
    out: list[dict] = []
    for p in rows:
        last = max(
            (
                v
                for v in (last_treatment.get(p.id), last_payment.get(p.id))
                if v is not None
            ),
            default=None,
        )
        if last is None:
            # Never visited: fall back to registration date, so imported
            # back-catalogue patients can surface but new ones don't.
            last = p.created_at
        visit_days = (today - last.date()).days if last else -1
        if visit_days >= days:
            out.append(
                {
                    "id": p.id,
                    "code": p.code,
                    "nom": p.nom,
                    "prenom": p.prenom,
                    "telephone": p.telephone,
                    "days_since_visit": visit_days,
                    "last_visit": last.isoformat(),
                }
            )
    out.sort(key=lambda r: r["days_since_visit"], reverse=True)
    return out[:limit]


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
