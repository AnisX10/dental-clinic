"""Appointment workflow tests."""
import datetime as dt

from app.core.dates import today as clinic_today
from tests.conftest import BACKEND_DIR  # noqa: F401


def _today() -> str:
    """Clinic timezone date (Africa/Algiers); the API computes 'today' with it."""
    return clinic_today().isoformat()


def _patient(client):
    return client.post(
        "/api/patients",
        json={"nom": "Hamdi", "prenom": "Sara", "telephone": "0770 99 88 77"},
    ).json()["patient"]


def _create_appt(client, patient_id, day, time=None, time_note=""):
    return client.post(
        "/api/agenda/appointments",
        json={"patient_id": patient_id, "date": day, "time": time, "time_note": time_note},
    )


def test_create_appointment_optional_time(owner_client, users):
    patient = _patient(owner_client)
    day = _today()
    # Without time
    resp = _create_appt(owner_client, patient["id"], day)
    assert resp.status_code == 201
    assert resp.json()["appointment"]["time"] is None
    # With approximate note only
    resp = _create_appt(owner_client, patient["id"], day, time_note="vers 10h")
    assert resp.status_code == 201
    assert resp.json()["appointment"]["time_note"] == "vers 10h"
    # With exact time
    resp = _create_appt(owner_client, patient["id"], day, time="14:30")
    assert resp.status_code == 201
    assert resp.json()["appointment"]["time"] == "14:30"


def test_appointment_requires_patient_and_date(owner_client, users):
    resp = owner_client.post(
        "/api/agenda/appointments", json={"patient_id": None, "date": ""}
    )
    assert resp.status_code in (400, 422)


def test_status_transitions(owner_client, users):
    patient = _patient(owner_client)
    day = _today()
    appt = _create_appt(owner_client, patient["id"], day).json()["appointment"]
    appt_id = appt["id"]

    r = owner_client.post(f"/api/agenda/appointments/{appt_id}/status", json={"status": "arrive"})
    assert r.json()["appointment"]["status"] == "arrive"
    r = owner_client.post(f"/api/agenda/appointments/{appt_id}/status", json={"status": "en_cours"})
    assert r.json()["appointment"]["status"] == "en_cours"
    r = owner_client.post(f"/api/agenda/appointments/{appt_id}/status", json={"status": "termine"})
    assert r.json()["appointment"]["status"] == "termine"


def test_invalid_transition_rejected(owner_client, users):
    patient = _patient(owner_client)
    day = _today()
    appt = _create_appt(owner_client, patient["id"], day).json()["appointment"]
    # a_venir -> termine is allowed, but termine -> arrive is not.
    owner_client.post(f"/api/agenda/appointments/{appt['id']}/status", json={"status": "termine"})
    resp = owner_client.post(f"/api/agenda/appointments/{appt['id']}/status", json={"status": "arrive"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_transition"


def test_absent_is_event_not_status(owner_client, users):
    patient = _patient(owner_client)
    day = _today()
    appt = _create_appt(owner_client, patient["id"], day).json()["appointment"]
    resp = owner_client.post(f"/api/agenda/appointments/{appt['id']}/absent")
    body = resp.json()["appointment"]
    assert body["absent"] is True
    assert body["status"] in ("a_venir", "termine")  # not a fifth status


def test_cancellation_and_history(owner_client, users):
    patient = _patient(owner_client)
    day = _today()
    appt = _create_appt(owner_client, patient["id"], day).json()["appointment"]
    owner_client.post(f"/api/agenda/appointments/{appt['id']}/status", json={"status": "arrive"})
    resp = owner_client.post(
        f"/api/agenda/appointments/{appt['id']}/cancel", json={"reason": "Patient a annulé"}
    )
    assert resp.json()["appointment"]["cancelled"] is True
    # History preserved with events
    detail = owner_client.get(f"/api/agenda/appointments/{appt['id']}").json()["appointment"]
    types = [e["event_type"] for e in detail["events"]]
    assert "created" in types and "status" in types and "cancel" in types
    # Cancelled appointment cannot change status
    resp = owner_client.post(f"/api/agenda/appointments/{appt['id']}/status", json={"status": "en_cours"})
    assert resp.status_code == 400


def test_update_appointment_date(owner_client, users):
    patient = _patient(owner_client)
    day = _today()
    appt = _create_appt(owner_client, patient["id"], day).json()["appointment"]
    new_day = (clinic_today() + dt.timedelta(days=2)).isoformat()
    resp = owner_client.put(
        f"/api/agenda/appointments/{appt['id']}", json={"date": new_day, "time": "09:00"}
    )
    assert resp.status_code == 200
    updated = resp.json()["appointment"]
    assert updated["date"] == new_day
    assert updated["time"] == "09:00"


def test_today_lists_only_today(owner_client, users):
    patient = _patient(owner_client)
    today = _today()
    tomorrow = (clinic_today() + dt.timedelta(days=1)).isoformat()
    _create_appt(owner_client, patient["id"], today)
    _create_appt(owner_client, patient["id"], tomorrow)
    rows = owner_client.get("/api/agenda/today").json()["appointments"]
    assert len(rows) == 1
    assert rows[0]["date"] == today
