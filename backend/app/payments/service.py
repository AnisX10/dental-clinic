"""Payment ledger: balances, concurrency-safe creation, history, daily revenue.

Invariant (spec §9): Reste = Total charges - Total payments.
- Charges come from patient_treatments.price (append-only snapshots).
- Payments are append-only and never deleted.
- Creation serializes per patient with pg_advisory_xact_lock and re-checks the
  balance inside the transaction, so concurrent payments cannot overpay.
"""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.core.errors import AppError
from app.core.models import Patient, PatientTreatment, Payment
from app.core.money import serialize_amount, to_money


def compute_balances(db: OrmSession, patient_id: int) -> dict:
    """Single source of truth for patient balances (Decimal math)."""
    from decimal import Decimal

    total = db.execute(
        select(func.coalesce(func.sum(PatientTreatment.price), 0)).where(
            PatientTreatment.patient_id == patient_id
        )
    ).scalar()
    paid = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.patient_id == patient_id)
    ).scalar()
    total = total if isinstance(total, Decimal) else Decimal(str(total or 0))
    paid = paid if isinstance(paid, Decimal) else Decimal(str(paid or 0))
    return {"total": total, "paid": paid, "reste": total - paid}


def patient_ledger(db: OrmSession, patient: Patient, limit: int = 100) -> dict:
    balances = compute_balances(db, patient.id)
    payments = list(
        db.execute(
            select(Payment)
            .where(Payment.patient_id == patient.id)
            .order_by(Payment.created_at.desc(), Payment.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return {
        "total": serialize_amount(balances["total"]),
        "paye": serialize_amount(balances["paid"]),
        "reste": serialize_amount(balances["reste"]),
        "payments": [
            {
                "id": p.id,
                "amount": serialize_amount(p.amount),
                "note": p.note,
                "created_at": p.created_at.isoformat(),
                "created_by_name": _actor_name(db, p.created_by),
            }
            for p in payments
    ],
    }


def _actor_name(db: OrmSession, user_id: int | None) -> str:
    if user_id is None:
        return ""
    from app.core.models import User

    return db.execute(select(User.full_name).where(User.id == user_id)).scalar() or ""


def create_payment(
    db: OrmSession,
    *,
    patient_id: int,
    amount,
    note: str = "",
    actor_id: int | None,
) -> Payment:
    """Concurrency-safe cash payment creation.

    Serializes on the patient row via advisory lock, recomputes balance inside
    the transaction, refuses zero/negative amounts and overpayment.
    """
    try:
        amount_dec = to_money(amount)
    except ValueError:
        raise AppError("errors.invalid_amount", status_code=400, code="invalid_amount") from None
    if amount_dec <= 0:
        raise AppError("errors.invalid_amount", status_code=400, code="invalid_amount")
    patient = db.get(Patient, patient_id)
    if patient is None or not patient.is_active:
        raise AppError("errors.patient_not_found", status_code=404, code="patient_not_found")

    # Serialize concurrent payments for this patient.
    db.execute(select(func.pg_advisory_xact_lock(patient_id)))

    balances = compute_balances(db, patient_id)
    if balances["reste"] <= 0:
        raise AppError("errors.nothing_due", status_code=400, code="nothing_due")
    if amount_dec > balances["reste"]:
        raise AppError(
            "errors.overpayment",
            status_code=400,
            code="overpayment",
            values={"reste": serialize_amount(balances["reste"])},
        )

    payment = Payment(patient_id=patient_id, amount=amount_dec, note=(note or "").strip()[:200], created_by=actor_id)
    db.add(payment)
    db.flush()
    return payment


def daily_revenue(db: OrmSession, day: date) -> dict:
    import datetime as dt

    from app.core.dates import CLINIC_TZ

    start = dt.datetime.combine(day, dt.time.min, tzinfo=CLINIC_TZ)
    end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min, tzinfo=CLINIC_TZ)
    row = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0), func.count(Payment.id)).where(
            Payment.created_at >= start, Payment.created_at < end
        )
    ).one()
    return {"recettes": serialize_amount(row[0]), "nombre_paiements": int(row[1])}


def payments_for_day(db: OrmSession, day: date, limit: int = 200) -> list[Payment]:
    import datetime as dt

    from app.core.dates import CLINIC_TZ

    start = dt.datetime.combine(day, dt.time.min, tzinfo=CLINIC_TZ)
    end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min, tzinfo=CLINIC_TZ)
    return list(
        db.execute(
            select(Payment)
            .where(Payment.created_at >= start, Payment.created_at < end)
            .order_by(Payment.created_at.desc(), Payment.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
