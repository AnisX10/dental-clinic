"""Documents: Ordonnance, Certificat médical, Attestation.

Each document stores a validated content snapshot at creation time, so printed
output stays faithful even if patient/settings data changes later. Rendering
happens in the frontend from the snapshot + clinic template data.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core.errors import AppError
from app.core.models import ClinicSettings, Document
from app.patients.service import get_patient_or_404

DOC_TYPES = ("ordonnance", "certificat", "attestation")


def validate_content(doc_type: str, content: dict) -> dict:
    content = content or {}
    if doc_type == "ordonnance":
        lines = content.get("lines", [])
        if not isinstance(lines, list):
            raise AppError("errors.invalid_document_content", status_code=400, code="invalid_content")
        clean = []
        for line in lines[:20]:
            text = str(line.get("text", "")).strip() if isinstance(line, dict) else str(line).strip()
            if text:
                clean.append(text[:300])
        return {"lines": clean, "note": str(content.get("note", "")).strip()[:500]}
    if doc_type == "certificat":
        duration_days = content.get("duration_days", 0)
        try:
            duration_days = max(0, min(90, int(duration_days)))
        except (TypeError, ValueError):
            duration_days = 0
        return {
            "text": str(content.get("text", "")).strip()[:2000],
            "duration_days": duration_days,
        }
    if doc_type == "attestation":
        return {"text": str(content.get("text", "")).strip()[:2000]}
    raise AppError("errors.invalid_document_type", status_code=400, code="invalid_type")


def create_document(
    db: OrmSession,
    *,
    patient_id: int,
    doc_type: str,
    title: str,
    content: dict,
    actor_id: int | None,
) -> Document:
    get_patient_or_404(db, patient_id)
    if doc_type not in DOC_TYPES:
        raise AppError("errors.invalid_document_type", status_code=400, code="invalid_type")
    clean = validate_content(doc_type, content)
    doc = Document(
        patient_id=patient_id,
        doc_type=doc_type,
        title=(title or "").strip()[:160],
        content=clean,
        created_by=actor_id,
    )
    db.add(doc)
    db.flush()
    return doc


def get_document_or_404(db: OrmSession, document_id: int) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError("errors.document_not_found", status_code=404, code="not_found")
    return doc


def patient_documents(db: OrmSession, patient_id: int, limit: int = 50) -> list[Document]:
    return list(
        db.execute(
            select(Document)
            .where(Document.patient_id == patient_id)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def serialize_document(doc: Document, *, include_content: bool = False) -> dict:
    data = {
        "id": doc.id,
        "patient_id": doc.patient_id,
        "doc_type": doc.doc_type,
        "title": doc.title,
        "created_at": doc.created_at.isoformat(),
    }
    if include_content:
        data["content"] = doc.content
    return data


def clinic_template_data(settings: ClinicSettings) -> dict:
    """Clinic branding block used on every printed document."""
    return {
        "clinic_name": settings.clinic_name,
        "doctor_name": settings.doctor_name,
        "address": settings.address,
        "phone": settings.phone,
        "logo_path": settings.logo_path,
        "header_note": settings.header_note,
        "footer_note": settings.footer_note,
    }
