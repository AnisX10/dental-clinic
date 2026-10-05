"""Labs API: registry, work orders (state machine), invoices + payments."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.core.audit import log_action
from app.core.auth import get_client_ip, get_current_user
from app.core.db import get_db
from app.core.models import LabOrder, User
from app.core.money import serialize_amount
from app.labs import service

router = APIRouter(prefix="/api", tags=["labs"])


# --------------------------------------------------------------------------- #
# Labs registry
# --------------------------------------------------------------------------- #


class LabCreate(BaseModel):
    name: str
    phone: str = ""
    address: str = ""
    notes: str = ""


class LabUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    is_active: bool | None = None


@router.get("/labs")
def list_labs(
    include_inactive: bool = True,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    rows = service.list_labs(db, include_inactive=include_inactive)
    return {"labs": [service.serialize_lab(lab) for lab in rows]}


@router.post("/labs", status_code=201)
def create_lab(
    payload: LabCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    lab = service.create_lab(
        db, name=payload.name, phone=payload.phone, address=payload.address, notes=payload.notes
    )
    log_action(
        db, actor_id=user.id, action="lab_create", entity="lab", entity_id=lab.id,
        detail={"name": lab.name}, ip=get_client_ip(request),
    )
    return {"lab": service.serialize_lab(lab)}


@router.put("/labs/{lab_id}")
def update_lab(
    lab_id: int,
    payload: LabUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    lab = service.get_lab_or_404(db, lab_id)
    service.update_lab(
        db, lab, name=payload.name, phone=payload.phone, address=payload.address, notes=payload.notes
    )
    if payload.is_active is not None and payload.is_active != lab.is_active:
        service.set_lab_active(db, lab, is_active=payload.is_active)
    log_action(
        db, actor_id=user.id, action="lab_update", entity="lab", entity_id=lab.id,
        detail={"fields": [k for k, v in payload.model_dump().items() if v is not None]},
        ip=get_client_ip(request),
    )
    return {"lab": service.serialize_lab(lab)}


# --------------------------------------------------------------------------- #
# Lab orders
# --------------------------------------------------------------------------- #


class OrderCreate(BaseModel):
    patient_id: int
    lab_id: int
    work_type: str
    teeth: str = ""
    shade: str = ""
    price: str | int | float = "0"
    sent_date: str | None = None
    due_date: str | None = None
    notes: str = ""


class OrderUpdate(BaseModel):
    lab_id: int | None = None
    teeth: str | None = None
    shade: str | None = None
    price: str | int | float | None = None
    due_date: str | None = None
    notes: str | None = None


class OrderStatusIn(BaseModel):
    status: str


@router.get("/lab-orders")
def list_orders(
    status: str | None = None,
    patient_id: int | None = None,
    lab_id: int | None = None,
    limit: int = 200,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    if status is not None and status not in service.ORDER_STATUSES:
        from app.core.errors import AppError

        raise AppError("errors.invalid_lab_status", status_code=400, code="invalid_status")
    query = select(LabOrder).order_by(LabOrder.sent_date.desc(), LabOrder.id.desc()).limit(max(1, min(limit, 500)))
    if status:
        query = query.where(LabOrder.status == status)
    if patient_id:
        query = query.where(LabOrder.patient_id == patient_id)
    if lab_id:
        query = query.where(LabOrder.lab_id == lab_id)
    rows = list(db.execute(query).scalars().all())
    counts = {s: 0 for s in service.ORDER_STATUSES}
    for s, n in db.execute(
        select(LabOrder.status, func.count(LabOrder.id)).group_by(LabOrder.status)
    ).all():
        counts[s] = int(n)
    return {"orders": [service.serialize_order(o) for o in rows], "counts": counts}


@router.post("/lab-orders", status_code=201)
def create_order(
    payload: OrderCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    order = service.create_order(
        db,
        patient_id=payload.patient_id,
        lab_id=payload.lab_id,
        work_type=payload.work_type,
        teeth=payload.teeth,
        shade=payload.shade,
        price=payload.price,
        sent_date=payload.sent_date,
        due_date=payload.due_date,
        notes=payload.notes,
        actor_id=user.id,
    )
    log_action(
        db, actor_id=user.id, action="lab_order_create", entity="lab_order", entity_id=order.id,
        detail={"patient_id": order.patient_id, "lab_id": order.lab_id, "work_type": order.work_type},
        ip=get_client_ip(request),
    )
    return {"order": service.serialize_order(order)}


@router.put("/lab-orders/{order_id}")
def update_order(
    order_id: int,
    payload: OrderUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    order = service.get_order_or_404(db, order_id)
    service.update_order(
        db, order, lab_id=payload.lab_id, teeth=payload.teeth, shade=payload.shade,
        price=payload.price, due_date=payload.due_date, notes=payload.notes,
    )
    log_action(
        db, actor_id=user.id, action="lab_order_update", entity="lab_order", entity_id=order.id,
        detail={"fields": [k for k, v in payload.model_dump().items() if v is not None]},
        ip=get_client_ip(request),
    )
    return {"order": service.serialize_order(order)}


@router.post("/lab-orders/{order_id}/status")
def set_order_status(
    order_id: int,
    payload: OrderStatusIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    order = service.get_order_or_404(db, order_id)
    service.set_order_status(db, order, status=payload.status, actor_id=user.id)
    log_action(
        db, actor_id=user.id, action="lab_order_status", entity="lab_order", entity_id=order.id,
        detail={"status": order.status}, ip=get_client_ip(request),
    )
    return {"order": service.serialize_order(order)}


@router.get("/patients/{patient_id}/lab-orders")
def patient_orders(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    from app.patients.service import get_patient_or_404

    get_patient_or_404(db, patient_id)
    rows = list(
        db.execute(
            select(LabOrder)
            .where(LabOrder.patient_id == patient_id)
            .order_by(LabOrder.sent_date.desc(), LabOrder.id.desc())
        ).scalars().all()
    )
    return {"orders": [service.serialize_order(o) for o in rows]}


# --------------------------------------------------------------------------- #
# Lab invoices + payments
# --------------------------------------------------------------------------- #


class InvoiceCreate(BaseModel):
    lab_id: int
    number: str
    label: str = ""
    amount: str | int | float
    issued_date: str | None = None
    notes: str = ""


class InvoicePaymentCreate(BaseModel):
    amount: str | int | float
    note: str = ""


@router.get("/lab-invoices")
def list_invoices(
    lab_id: int | None = None,
    limit: int = 200,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    from app.core.models import LabInvoice

    query = select(LabInvoice).order_by(LabInvoice.issued_date.desc(), LabInvoice.id.desc()).limit(max(1, min(limit, 500)))
    if lab_id:
        query = query.where(LabInvoice.lab_id == lab_id)
    rows = list(db.execute(query).scalars().all())
    invoices = [service.serialize_invoice(db, inv) for inv in rows]
    total = sum(float(i["amount"]) for i in invoices)
    paye = sum(float(i["paye"]) for i in invoices)
    return {"invoices": invoices, "totaux": {"total": round(total, 2), "paye": round(paye, 2)}}


@router.get("/lab-invoices/{invoice_id}")
def get_invoice(
    invoice_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    invoice = service.get_invoice_or_404(db, invoice_id)
    return {"invoice": service.serialize_invoice(db, invoice, include_payments=True)}


@router.post("/lab-invoices", status_code=201)
def create_invoice(
    payload: InvoiceCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    invoice = service.create_invoice(
        db, lab_id=payload.lab_id, number=payload.number, label=payload.label,
        amount=payload.amount, issued_date=payload.issued_date, notes=payload.notes,
        actor_id=user.id,
    )
    log_action(
        db, actor_id=user.id, action="lab_invoice_create", entity="lab_invoice", entity_id=invoice.id,
        detail={"lab_id": invoice.lab_id, "number": invoice.number, "amount": serialize_amount(invoice.amount)},
        ip=get_client_ip(request),
    )
    return {"invoice": service.serialize_invoice(db, invoice)}


@router.post("/lab-invoices/{invoice_id}/payments", status_code=201)
def pay_invoice(
    invoice_id: int,
    payload: InvoicePaymentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    payment = service.create_invoice_payment(
        db, invoice_id=invoice_id, amount=payload.amount, note=payload.note, actor_id=user.id
    )
    log_action(
        db, actor_id=user.id, action="lab_invoice_payment", entity="lab_invoice", entity_id=invoice_id,
        detail={"amount": serialize_amount(payment.amount)}, ip=get_client_ip(request),
    )
    invoice = service.get_invoice_or_404(db, invoice_id)
    return {
        "payment": {"id": payment.id, "amount": serialize_amount(payment.amount)},
        "invoice": service.serialize_invoice(db, invoice),
    }
