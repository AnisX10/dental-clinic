"""Agenda endpoints: today, day list, appointment CRUD + workflow."""
import datetime as dt

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.agenda import service
from app.core.audit import log_action
from app.core.auth import get_client_ip, get_current_user
from app.core.dates import CLINIC_TZ, now_tz, today
from app.core.db import get_db
from app.core.errors import AppError
from app.core.models import Appointment, Payment, User
from app.core.money import serialize_amount
from app.patients.service import get_patient_or_404

router = APIRouter(prefix="/api/agenda", tags=["agenda"])


class AppointmentCreate(BaseModel):
    patient_id: int
    date: str
    time: str | None = None
    time_note: str = ""
    motif: str = ""


class AppointmentUpdate(BaseModel):
    date: str | None = None
    time: str | None = None
    time_note: str | None = None
    motif: str | None = None


class StatusIn(BaseModel):
    status: str


class ReasonIn(BaseModel):
    reason: str = ""


def _today_summary(db: OrmSession) -> dict:
    day_start = dt.datetime.combine(today(), dt.time.min, tzinfo=CLINIC_TZ)
    day_end = dt.datetime.combine(today() + dt.timedelta(days=1), dt.time.min, tzinfo=CLINIC_TZ)
    row = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0), func.count(Payment.id)).where(
            Payment.created_at >= day_start, Payment.created_at < day_end
        )
    ).one()
    return {"recettes_du_jour": serialize_amount(row[0]), "nombre_paiements": int(row[1])}


@router.get("/today")
def get_today(
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    rows = service.list_day(db, today())
    return {
        "date": today().isoformat(),
        "appointments": [service.serialize_appointment(a) for a in rows],
        "summary": _today_summary(db),
    }


@router.get("/day/{day}")
def get_day(
    day: str,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    try:
        parsed = dt.date.fromisoformat(day)
    except ValueError:
        raise AppError("errors.invalid_date", status_code=400, code="invalid_date") from None
    rows = service.list_day(db, parsed)
    return {"date": parsed.isoformat(), "appointments": [service.serialize_appointment(a) for a in rows]}


@router.get("/appointments/{appointment_id}")
def get_appointment(
    appointment_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    appt = service.get_appointment_or_404(db, appointment_id)
    data = service.serialize_appointment(appt)
    data["events"] = [service.serialize_event(e) for e in appt.events]
    return {"appointment": data}


@router.post("/appointments", status_code=201)
def create_appointment(
    payload: AppointmentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    if not service.patient_exists(db, payload.patient_id):
        raise AppError("errors.patient_not_found", status_code=404, code="patient_not_found")
    fields = service.validate_appointment_input(
        patient_id=payload.patient_id,
        date_str=payload.date,
        time_str=payload.time,
        time_note=payload.time_note,
    )
    appt = Appointment(
        patient_id=fields["patient_id"],
        date=fields["date"],
        time=fields["time"],
        time_note=fields["time_note"],
        motif=payload.motif.strip()[:160],
        status="a_venir",
        created_by=user.id,
    )
    db.add(appt)
    db.flush()
    service.add_event(db, appt, event_type="created", actor_id=user.id, to_status="a_venir")
    log_action(
        db,
        actor_id=user.id,
        action="appointment_create",
        entity="appointment",
        entity_id=appt.id,
        ip=get_client_ip(request),
    )
    return {"appointment": service.serialize_appointment(appt)}


@router.put("/appointments/{appointment_id}")
def update_appointment(
    appointment_id: int,
    payload: AppointmentUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    appt = service.get_appointment_or_404(db, appointment_id)
    if appt.cancelled_at is not None:
        raise AppError("errors.appointment_cancelled", status_code=400, code="appointment_cancelled")
    changes = []
    if payload.date is not None and payload.date != appt.date.isoformat():
        fields = service.validate_appointment_input(
            patient_id=appt.patient_id, date_str=payload.date, time_str=None, time_note=None
        )
        appt.date = fields["date"]
        changes.append("date")
    if payload.time is not None:
        if payload.time == "":
            appt.time = None
            changes.append("time")
        else:
            fields = service.validate_appointment_input(
                patient_id=appt.patient_id, date_str=appt.date.isoformat(), time_str=payload.time, time_note=None
            )
            appt.time = fields["time"]
            changes.append("time")
    if payload.time_note is not None and payload.time_note.strip() != appt.time_note:
        appt.time_note = payload.time_note.strip()[:60]
        changes.append("time_note")
    if payload.motif is not None and payload.motif.strip() != appt.motif:
        appt.motif = payload.motif.strip()[:160]
        changes.append("motif")
    if changes:
        appt.updated_at = now_tz()
        service.add_event(db, appt, event_type="edit", actor_id=user.id, detail=",".join(changes))
        log_action(
            db,
            actor_id=user.id,
            action="appointment_update",
            entity="appointment",
            entity_id=appt.id,
            detail={"fields": changes},
            ip=get_client_ip(request),
        )
    return {"appointment": service.serialize_appointment(appt)}


@router.post("/appointments/{appointment_id}/status")
def set_status(
    appointment_id: int,
    payload: StatusIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    appt = service.get_appointment_or_404(db, appointment_id)
    service.set_status(db, appt, payload.status, actor_id=user.id)
    log_action(
        db,
        actor_id=user.id,
        action="appointment_status",
        entity="appointment",
        entity_id=appt.id,
        detail={"status": payload.status},
        ip=get_client_ip(request),
    )
    return {"appointment": service.serialize_appointment(appt)}


@router.post("/appointments/{appointment_id}/absent")
def mark_absent(
    appointment_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    appt = service.get_appointment_or_404(db, appointment_id)
    service.mark_absent(db, appt, actor_id=user.id)
    log_action(
        db,
        actor_id=user.id,
        action="appointment_absent",
        entity="appointment",
        entity_id=appt.id,
        ip=get_client_ip(request),
    )
    return {"appointment": service.serialize_appointment(appt)}


@router.post("/appointments/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: int,
    payload: ReasonIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    appt = service.get_appointment_or_404(db, appointment_id)
    service.cancel(db, appt, actor_id=user.id, reason=payload.reason)
    log_action(
        db,
        actor_id=user.id,
        action="appointment_cancel",
        entity="appointment",
        entity_id=appt.id,
        ip=get_client_ip(request),
    )
    return {"appointment": service.serialize_appointment(appt)}


@router.get("/patients/{patient_id}/appointments")
def patient_appointments(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    get_patient_or_404(db, patient_id)
    rows = list(
        db.execute(
            select(Appointment)
            .where(Appointment.patient_id == patient_id)
            .order_by(Appointment.date.desc(), Appointment.id.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    return {"appointments": [service.serialize_appointment(a) for a in rows]}


@router.get("/patients/{patient_id}/upcoming-count")
def patient_upcoming_count(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    get_patient_or_404(db, patient_id)
    return {"count": service.upcoming_count(db, patient_id)}
