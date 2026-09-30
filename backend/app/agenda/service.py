"""Appointment logic: statuses, transitions, events."""
import re
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as OrmSession

from app.core.dates import now_tz
from app.core.errors import AppError
from app.core.models import Appointment, AppointmentEvent, Patient

# The four primary workflow statuses (spec: À venir, Arrivé, En cours, Terminé).
STATUSES = ("a_venir", "arrive", "en_cours", "termine")

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "a_venir": ("arrive", "en_cours", "termine"),
    "arrive": ("en_cours", "termine", "a_venir"),
    "en_cours": ("termine", "arrive"),
    "termine": (),
}


def validate_appointment_input(
    *, patient_id: int | None, date_str: str | None, time_str: str | None, time_note: str | None
) -> dict:
    if not patient_id:
        raise AppError("errors.patient_required", status_code=400, code="patient_required")
    if not date_str:
        raise AppError("errors.date_required", status_code=400, code="date_required")
    try:
        day = date.fromisoformat(date_str)
    except ValueError:
        raise AppError("errors.invalid_date", status_code=400, code="invalid_date") from None
    appt_time = None
    if time_str:
        parsed = time_str.strip()
        m = _TIME_RE.match(parsed)
        if not m:
            raise AppError("errors.invalid_time", status_code=400, code="invalid_time")
        hh, mm = int(m.group("hh")), int(m.group("mm") or 0)
        if hh > 23 or mm > 59:
            raise AppError("errors.invalid_time", status_code=400, code="invalid_time")
        from datetime import time

        appt_time = time(hh, mm)
    return {
        "patient_id": int(patient_id),
        "date": day,
        "time": appt_time,
        "time_note": (time_note or "").strip()[:60],
    }


_TIME_RE = re.compile(r"^(?P<hh>\d{1,2})[:hH.](?P<mm>\d{1,2})?$")


def get_appointment_or_404(db: OrmSession, appointment_id: int) -> Appointment:
    row = db.get(Appointment, appointment_id)
    if row is None:
        raise AppError("errors.appointment_not_found", status_code=404, code="not_found")
    return row


def patient_exists(db: OrmSession, patient_id: int) -> bool:
    return db.get(Patient, patient_id) is not None


def list_day(db: OrmSession, day: date, *, include_cancelled: bool = False):
    query = select(Appointment).where(Appointment.date == day)
    if not include_cancelled:
        query = query.where(Appointment.cancelled_at.is_(None))
    return list(
        db.execute(
            query.order_by(Appointment.time.asc().nulls_last(), Appointment.id.asc())
        )
        .scalars()
        .all()
    )


def upcoming_count(db: OrmSession, patient_id: int) -> int:
    today = now_tz().date()
    return int(
        db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.patient_id == patient_id,
                Appointment.cancelled_at.is_(None),
                or_(Appointment.date >= today, Appointment.status.in_(("a_venir", "arrive", "en_cours"))),
            )
        ).scalar()
        or 0
    )


def add_event(
    db: OrmSession,
    appointment: Appointment,
    *,
    event_type: str,
    actor_id: int | None,
    from_status: str | None = None,
    to_status: str | None = None,
    detail: str = "",
) -> None:
    db.add(
        AppointmentEvent(
            appointment_id=appointment.id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            detail=detail,
            actor_id=actor_id,
        )
    )


def set_status(db: OrmSession, appointment: Appointment, new_status: str, *, actor_id: int | None) -> None:
    if new_status not in STATUSES:
        raise AppError("errors.invalid_status", status_code=400, code="invalid_status")
    if appointment.cancelled_at is not None:
        raise AppError("errors.appointment_cancelled", status_code=400, code="appointment_cancelled")
    if appointment.absent_at is not None:
        raise AppError("errors.appointment_absent", status_code=400, code="appointment_absent")
    if new_status == appointment.status:
        return
    if new_status not in TRANSITIONS.get(appointment.status, ()):
        raise AppError(
            "errors.invalid_transition",
            status_code=400,
            code="invalid_transition",
            values={"from": appointment.status, "to": new_status},
        )
    old = appointment.status
    appointment.status = new_status
    appointment.updated_at = now_tz()
    add_event(db, appointment, event_type="status", actor_id=actor_id, from_status=old, to_status=new_status)


def mark_absent(db: OrmSession, appointment: Appointment, *, actor_id: int | None) -> None:
    if appointment.cancelled_at is not None:
        raise AppError("errors.appointment_cancelled", status_code=400, code="appointment_cancelled")
    if appointment.absent_at is not None:
        return
    old = appointment.status
    appointment.absent_at = now_tz()
    appointment.status = "termine" if old != "termine" else old
    appointment.updated_at = now_tz()
    add_event(db, appointment, event_type="absent", actor_id=actor_id, from_status=old, to_status=None)


def cancel(db: OrmSession, appointment: Appointment, *, actor_id: int | None, reason: str = "") -> None:
    if appointment.cancelled_at is not None:
        return
    old = appointment.status
    appointment.cancelled_at = now_tz()
    appointment.updated_at = now_tz()
    add_event(db, appointment, event_type="cancel", actor_id=actor_id, from_status=old, detail=reason[:200])


def serialize_appointment(a: Appointment, patient: Patient | None = None) -> dict:
    patient = patient or a.patient
    return {
        "id": a.id,
        "patient": {
            "id": patient.id,
            "code": patient.code,
            "nom": patient.nom,
            "prenom": patient.prenom,
            "telephone": patient.telephone,
        },
        "date": a.date.isoformat(),
        "time": a.time.isoformat(timespec="minutes") if a.time else None,
        "time_note": a.time_note,
        "motif": a.motif,
        "status": a.status,
        "cancelled": a.cancelled_at is not None,
        "absent": a.absent_at is not None,
        "created_at": a.created_at.isoformat(),
        "updated_at": a.updated_at.isoformat(),
    }


def serialize_event(e: AppointmentEvent) -> dict:
    return {
        "id": e.id,
        "event_type": e.event_type,
        "from_status": e.from_status,
        "to_status": e.to_status,
        "detail": e.detail,
        "created_at": e.created_at.isoformat(),
    }
