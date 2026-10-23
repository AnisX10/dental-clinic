"""Payments API: patient ledger, cash payments, daily revenue, payment page data."""
import datetime as dt

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession

from app.core.audit import log_action
from app.core.auth import get_client_ip, get_current_user
from app.core.db import get_db
from app.core.errors import AppError
from app.core.models import User
from app.core.money import serialize_amount
from app.patients.service import get_patient_or_404, patient_brief
from app.payments import service

router = APIRouter(prefix="/api/payments", tags=["payments"])


class PaymentCreate(BaseModel):
    patient_id: int
    amount: str | int | float
    note: str = ""


@router.get("/patients/{patient_id}/ledger")
def patient_ledger(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    patient = get_patient_or_404(db, patient_id)
    ledger = service.patient_ledger(db, patient)
    return {
        "patient": patient_brief(patient),
        "total": ledger["total"],
        "paye": ledger["paye"],
        "reste": ledger["reste"],
        "payments": ledger["payments"],
    }


@router.post("", status_code=201)
def create_payment(
    payload: PaymentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    payment = service.create_payment(
        db,
        patient_id=payload.patient_id,
        amount=payload.amount,
        note=payload.note,
        actor_id=user.id,
    )
    log_action(
        db,
        actor_id=user.id,
        action="payment_create",
        entity="payment",
        entity_id=payment.id,
        detail={"patient_id": payment.patient_id, "amount": serialize_amount(payment.amount)},
        ip=get_client_ip(request),
    )
    db.commit()
    return {"payment": {"id": payment.id, "amount": serialize_amount(payment.amount)}}


@router.get("/day/{day}")
def payments_day(
    day: str,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    try:
        parsed = dt.date.fromisoformat(day)
    except ValueError:
        raise AppError("errors.invalid_date", status_code=400, code="invalid_date") from None
    rows = service.payments_for_day(db, parsed)
    return {
        "date": parsed.isoformat(),
        "summary": service.daily_revenue(db, parsed),
        "payments": [_serialize_payment(db, p) for p in rows],
    }


def _serialize_payment(db: OrmSession, p) -> dict:
    from app.core.models import Patient

    patient = db.get(Patient, p.patient_id)
    return {
        "id": p.id,
        "amount": serialize_amount(p.amount),
        "note": p.note,
        "created_at": p.created_at.isoformat(),
        "created_by_name": service._actor_name(db, p.created_by),
        "patient": patient_brief(patient) if patient else None,
    }
