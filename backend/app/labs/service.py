"""Lab module logic: labs registry, work orders (state machine), invoices + payments.

Status workflow: envoye -> en_fabrication -> pret -> recu, with `annule` reachable
from any non-terminal status. Records are never hard-deleted; edits are locked
once an order is recu or annule. Invoice payments are append-only and
concurrency-safe (pg_advisory_xact_lock + in-transaction reste recheck, same
invariant as patient payments: reste = amount - sum(payments)).
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.core.dates import now_tz
from app.core.errors import AppError
from app.core.models import Lab, LabInvoice, LabInvoicePayment, LabOrder
from app.core.money import serialize_amount, to_money

WORK_TYPES = ("couronne", "bridge", "prothese", "gouttiere", "autre")

# Allowed forward transitions + cancellation from any active status.
ORDER_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "envoye": ("en_fabrication", "pret", "recu", "annule"),
    "en_fabrication": ("pret", "recu", "annule"),
    "pret": ("recu", "annule"),
    "recu": (),
    "annule": (),
}
ORDER_STATUSES = ("envoye", "en_fabrication", "pret", "recu", "annule")
TERMINAL_STATUSES = ("recu", "annule")


# --------------------------------------------------------------------------- #
# Labs registry
# --------------------------------------------------------------------------- #


def list_labs(db: OrmSession, *, include_inactive: bool = False) -> list[Lab]:
    query = select(Lab).order_by(Lab.name)
    if not include_inactive:
        query = query.where(Lab.is_active.is_(True))
    return list(db.execute(query).scalars().all())


def get_lab_or_404(db: OrmSession, lab_id: int) -> Lab:
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise AppError("errors.lab_not_found", status_code=404, code="lab_not_found")
    return lab


def create_lab(db: OrmSession, *, name: str, phone: str, address: str, notes: str) -> Lab:
    name = (name or "").strip()
    if not name:
        raise AppError("errors.lab_name_required", status_code=400, code="invalid_input")
    if len(name) > 120:
        raise AppError("errors.lab_name_too_long", status_code=400, code="name_too_long")
    exists = db.execute(
        select(Lab.id).where(func.lower(Lab.name) == name.lower())
    ).scalar_one_or_none()
    if exists:
        raise AppError("errors.lab_name_taken", status_code=400, code="duplicate_name")
    lab = Lab(name=name, phone=(phone or "").strip()[:30], address=(address or "").strip()[:255], notes=(notes or "").strip())
    db.add(lab)
    db.flush()
    return lab


def update_lab(db: OrmSession, lab: Lab, *, name: str | None, phone: str | None, address: str | None, notes: str | None) -> None:
    if name is not None:
        clean = name.strip()
        if not clean:
            raise AppError("errors.lab_name_required", status_code=400, code="invalid_input")
        if clean.lower() != lab.name.lower():
            exists = db.execute(
                select(Lab.id).where(func.lower(Lab.name) == clean.lower(), Lab.id != lab.id)
            ).scalar_one_or_none()
            if exists:
                raise AppError("errors.lab_name_taken", status_code=400, code="duplicate_name")
        lab.name = clean[:120]
    if phone is not None:
        lab.phone = phone.strip()[:30]
    if address is not None:
        lab.address = address.strip()[:255]
    if notes is not None:
        lab.notes = notes.strip()
    db.flush()


def set_lab_active(db: OrmSession, lab: Lab, *, is_active: bool) -> None:
    lab.is_active = bool(is_active)
    db.flush()


def serialize_lab(lab: Lab) -> dict:
    return {
        "id": lab.id,
        "name": lab.name,
        "phone": lab.phone,
        "address": lab.address,
        "notes": lab.notes,
        "is_active": lab.is_active,
    }


# --------------------------------------------------------------------------- #
# Lab orders
# --------------------------------------------------------------------------- #


def get_order_or_404(db: OrmSession, order_id: int) -> LabOrder:
    order = db.get(LabOrder, order_id)
    if order is None:
        raise AppError("errors.lab_order_not_found", status_code=404, code="lab_order_not_found")
    return order


def _parse_date(value, field_key: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise AppError(f"errors.{field_key}", status_code=400, code="invalid_date") from None


def validate_teeth(teeth: str) -> str:
    clean = (teeth or "").strip()
    if not clean:
        return ""
    if len(clean) > 60:
        raise AppError("errors.invalid_teeth", status_code=400, code="invalid_input")
    import re

    if not re.fullmatch(r"[0-9]{1,2}([ ,.;/]+[0-9]{1,2})*", clean):
        raise AppError("errors.invalid_teeth", status_code=400, code="invalid_input")
    return clean


def create_order(
    db: OrmSession,
    *,
    patient_id: int,
    lab_id: int,
    work_type: str,
    teeth: str,
    shade: str,
    price,
    sent_date,
    due_date,
    notes: str,
    actor_id: int | None,
) -> LabOrder:
    from app.patients.service import get_patient_or_404

    get_patient_or_404(db, patient_id)
    lab = get_lab_or_404(db, lab_id)
    if not lab.is_active:
        raise AppError("errors.lab_inactive", status_code=400, code="lab_inactive")
    if work_type not in WORK_TYPES:
        raise AppError("errors.invalid_work_type", status_code=400, code="invalid_work_type")
    try:
        price_dec = to_money(price) if price not in (None, "") else Decimal("0")
    except ValueError:
        raise AppError("errors.invalid_price", status_code=400, code="invalid_price") from None
    if price_dec < 0:
        raise AppError("errors.invalid_price", status_code=400, code="invalid_price")
    sent = _parse_date(sent_date, "invalid_date")
    if sent is None:
        sent = now_tz().date()
    if sent > now_tz().date():
        raise AppError("errors.invalid_date", status_code=400, code="invalid_date")
    order = LabOrder(
        patient_id=patient_id,
        lab_id=lab_id,
        work_type=work_type,
        teeth=validate_teeth(teeth),
        shade=(shade or "").strip()[:20],
        price=price_dec,
        status="envoye",
        sent_date=sent,
        due_date=_parse_date(due_date, "invalid_date"),
        notes=(notes or "").strip(),
        created_by=actor_id,
    )
    db.add(order)
    db.flush()
    return order


def update_order(
    db: OrmSession, order: LabOrder, *, lab_id: int | None, teeth: str | None, shade: str | None,
    price, due_date, notes: str | None,
) -> None:
    if order.status in TERMINAL_STATUSES:
        raise AppError("errors.lab_order_locked", status_code=400, code="lab_order_locked")
    if lab_id is not None and lab_id != order.lab_id:
        lab = get_lab_or_404(db, lab_id)
        if not lab.is_active:
            raise AppError("errors.lab_inactive", status_code=400, code="lab_inactive")
        order.lab_id = lab_id
    if teeth is not None:
        order.teeth = validate_teeth(teeth)
    if shade is not None:
        order.shade = shade.strip()[:20]
    if price is not None:
        try:
            price_dec = to_money(price)
        except ValueError:
            raise AppError("errors.invalid_price", status_code=400, code="invalid_price") from None
        if price_dec < 0:
            raise AppError("errors.invalid_price", status_code=400, code="invalid_price")
        order.price = price_dec
    if due_date is not None:
        order.due_date = _parse_date(due_date, "invalid_date")
    if notes is not None:
        order.notes = notes.strip()
    order.updated_at = now_tz()
    db.flush()


def set_order_status(db: OrmSession, order: LabOrder, *, status: str, actor_id: int | None) -> LabOrder:
    if status not in ORDER_STATUSES:
        raise AppError("errors.invalid_lab_status", status_code=400, code="invalid_status")
    if status == order.status:
        return order
    if status not in ORDER_TRANSITIONS[order.status]:
        raise AppError("errors.invalid_lab_transition", status_code=400, code="invalid_transition")
    order.status = status
    if status == "recu":
        order.received_date = now_tz().date()
    elif status in ("envoye", "en_fabrication", "pret"):
        order.received_date = None
    order.updated_at = now_tz()
    db.flush()
    return order


def serialize_order(order: LabOrder) -> dict:
    patient = order.patient
    return {
        "id": order.id,
        "patient": {
            "id": patient.id,
            "code": patient.code,
            "nom": patient.nom,
            "prenom": patient.prenom,
        },
        "lab": {"id": order.lab.id, "name": order.lab.name},
        "work_type": order.work_type,
        "teeth": order.teeth,
        "shade": order.shade,
        "price": serialize_amount(order.price),
        "status": order.status,
        "sent_date": order.sent_date.isoformat(),
        "due_date": order.due_date.isoformat() if order.due_date else None,
        "received_date": order.received_date.isoformat() if order.received_date else None,
        "notes": order.notes,
        "created_at": order.created_at.isoformat(),
    }


# --------------------------------------------------------------------------- #
# Lab invoices + payments
# --------------------------------------------------------------------------- #


def get_invoice_or_404(db: OrmSession, invoice_id: int) -> LabInvoice:
    invoice = db.get(LabInvoice, invoice_id)
    if invoice is None:
        raise AppError("errors.lab_invoice_not_found", status_code=404, code="lab_invoice_not_found")
    return invoice


def invoice_totals(db: OrmSession, invoice: LabInvoice) -> dict:
    paid = db.execute(
        select(func.coalesce(func.sum(LabInvoicePayment.amount), 0)).where(
            LabInvoicePayment.invoice_id == invoice.id
        )
    ).scalar()
    from decimal import Decimal

    paid = paid if isinstance(paid, Decimal) else Decimal(str(paid or 0))
    return {"amount": invoice.amount, "paid": paid, "reste": invoice.amount - paid}


def create_invoice(
    db: OrmSession, *, lab_id: int, number: str, label: str, amount, issued_date, notes: str, actor_id: int | None
) -> LabInvoice:
    get_lab_or_404(db, lab_id)  # validate existence
    number = (number or "").strip()
    if not number:
        raise AppError("errors.invoice_number_required", status_code=400, code="invalid_input")
    if len(number) > 60:
        raise AppError("errors.invoice_number_too_long", status_code=400, code="name_too_long")
    exists = db.execute(
        select(LabInvoice.id).where(
            LabInvoice.lab_id == lab_id, func.lower(LabInvoice.number) == number.lower()
        )
    ).scalar_one_or_none()
    if exists:
        raise AppError("errors.invoice_number_taken", status_code=400, code="duplicate_number")
    try:
        amount_dec = to_money(amount)
    except ValueError:
        raise AppError("errors.invalid_amount", status_code=400, code="invalid_amount") from None
    if amount_dec <= 0:
        raise AppError("errors.invalid_amount", status_code=400, code="invalid_amount")
    issued = _parse_date(issued_date, "invalid_date") or now_tz().date()
    invoice = LabInvoice(
        lab_id=lab_id,
        number=number,
        label=(label or "").strip()[:200],
        amount=amount_dec,
        issued_date=issued,
        notes=(notes or "").strip(),
        created_by=actor_id,
    )
    db.add(invoice)
    db.flush()
    return invoice


def create_invoice_payment(
    db: OrmSession,
    *,
    invoice_id: int,
    amount,
    note: str,
    actor_id: int | None,
) -> LabInvoicePayment:
    """Concurrency-safe invoice payment: row-lock via advisory lock, recheck reste."""
    try:
        amount_dec = to_money(amount)
    except ValueError:
        raise AppError("errors.invalid_amount", status_code=400, code="invalid_amount") from None
    if amount_dec <= 0:
        raise AppError("errors.invalid_amount", status_code=400, code="invalid_amount")
    invoice = get_invoice_or_404(db, invoice_id)

    db.execute(select(func.pg_advisory_xact_lock(invoice_id)))
    totals = invoice_totals(db, invoice)
    if totals["reste"] <= 0:
        raise AppError("errors.lab_invoice_settled", status_code=400, code="nothing_due")
    if amount_dec > totals["reste"]:
        raise AppError(
            "errors.lab_invoice_overpay",
            status_code=400,
            code="overpayment",
            values={"reste": serialize_amount(totals["reste"])},
        )
    payment = LabInvoicePayment(
        invoice_id=invoice_id, amount=amount_dec, note=(note or "").strip()[:200], created_by=actor_id
    )
    db.add(payment)
    db.flush()
    return payment


def serialize_invoice(db: OrmSession, invoice: LabInvoice, *, include_payments: bool = False) -> dict:
    totals = invoice_totals(db, invoice)
    data = {
        "id": invoice.id,
        "lab": {"id": invoice.lab.id, "name": invoice.lab.name},
        "number": invoice.number,
        "label": invoice.label,
        "amount": serialize_amount(invoice.amount),
        "paye": serialize_amount(totals["paid"]),
        "reste": serialize_amount(totals["reste"]),
        "issued_date": invoice.issued_date.isoformat(),
        "notes": invoice.notes,
        "created_at": invoice.created_at.isoformat(),
    }
    if include_payments:
        payments = list(
            db.execute(
                select(LabInvoicePayment)
                .where(LabInvoicePayment.invoice_id == invoice.id)
                .order_by(LabInvoicePayment.created_at.desc(), LabInvoicePayment.id.desc())
            )
            .scalars()
            .all()
        )
        data["payments"] = [
            {
                "id": p.id,
                "amount": serialize_amount(p.amount),
                "note": p.note,
                "created_at": p.created_at.isoformat(),
                "created_by_name": _actor_name(db, p.created_by),
            }
            for p in payments
        ]
    return data


def _actor_name(db: OrmSession, user_id: int | None) -> str:
    if user_id is None:
        return ""
    from app.core.models import User

    return db.execute(select(User.full_name).where(User.id == user_id)).scalar() or ""
