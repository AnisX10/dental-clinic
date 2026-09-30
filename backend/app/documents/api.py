"""Document endpoints."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession

from app.core.audit import log_action
from app.core.auth import get_client_ip, get_current_user
from app.core.db import get_db
from app.core.models import User
from app.documents import service
from app.patients.service import get_patient_or_404

router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentCreate(BaseModel):
    patient_id: int
    doc_type: str
    title: str = ""
    content: dict = {}


@router.post("", status_code=201)
def create_document(
    payload: DocumentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    doc = service.create_document(
        db,
        patient_id=payload.patient_id,
        doc_type=payload.doc_type,
        title=payload.title,
        content=payload.content,
        actor_id=user.id,
    )
    log_action(
        db,
        actor_id=user.id,
        action="document_create",
        entity="document",
        entity_id=doc.id,
        detail={"patient_id": doc.patient_id, "doc_type": doc.doc_type},
        ip=get_client_ip(request),
    )
    return {"document": service.serialize_document(doc, include_content=True)}


@router.get("/patients/{patient_id}")
def list_patient_documents(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    get_patient_or_404(db, patient_id)
    rows = service.patient_documents(db, patient_id)
    return {"documents": [service.serialize_document(d) for d in rows]}


@router.get("/{document_id}")
def get_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    doc = service.get_document_or_404(db, document_id)
    from app.core.services import get_settings_row

    settings = get_settings_row(db)
    return {
        "document": service.serialize_document(doc, include_content=True),
        "clinic": service.clinic_template_data(settings),
    }
