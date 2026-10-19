"""DSP & CNAS register service (CNAS AS 2 — Feuille de soins dentaires)."""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core.dates import now_tz
from app.core.errors import AppError
from app.core.models import DspAct, DspRegistry, Patient

CAISSES = ("CNAS", "CASNOS")
BENEFICIARY_RELATIONS = ("assure", "conjoint", "enfant", "autre")
# Official AS 2 rule: dossier presented within 3 months after the first act.
DEADLINE_DAYS = 90

TOOTH_MAX_PERMANENT = 48  # FDI permanent range is 11..48


def _validate_tooth(tooth: int | None) -> int | None:
    if tooth is None:
        return None
    try:
        tooth = int(tooth)
    except (TypeError, ValueError):
        raise AppError("errors.invalid_tooth", status_code=400, code="invalid_tooth") from None
    permanent = 11 <= tooth <= 48
    deciduous = tooth in range(51, 86) and (tooth % 10) in range(1, 6)
    if not (permanent or deciduous):
        raise AppError("errors.invalid_tooth", status_code=400, code="invalid_tooth")
    return tooth


def _parse_date(value, *, field_key: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise AppError(field_key, status_code=400, code="invalid_date") from None


def _dec(value) -> Decimal:
    try:
        from app.core.money import to_money

        val = to_money(value if value not in (None, "") else 0)
        return max(Decimal("0.00"), val)
    except (TypeError, ValueError):
        raise AppError("errors.invalid_amount", status_code=400, code="invalid_amount") from None


def validate_registry_input(db: OrmSession, *, patient_id: int, caisse: str, first_act_date, beneficiary_relation: str = "assure") -> dict:
    patient = db.get(Patient, patient_id)
    if patient is None or not patient.is_active:
        raise AppError("errors.patient_not_found", status_code=404, code="patient_not_found")
    if caisse not in CAISSES:
        raise AppError("errors.invalid_caisse", status_code=400, code="invalid_caisse")
    if beneficiary_relation not in BENEFICIARY_RELATIONS:
        raise AppError("errors.invalid_beneficiary", status_code=400, code="invalid_beneficiary")
    first_act_date = _parse_date(first_act_date, field_key="errors.invalid_date")
    return {"patient_id": patient_id, "caisse": caisse, "first_act_date": first_act_date, "beneficiary_relation": beneficiary_relation}


def create_registry(db: OrmSession, *, data: dict, actor_id: int | None) -> DspRegistry:
    row = DspRegistry(
        patient_id=data["patient_id"],
        caisse=data["caisse"],
        insured_nin=str(data.get("insured_nin", "")).strip()[:18],
        affiliation_no=str(data.get("affiliation_no", "")).strip()[:40],
        beneficiary_relation=data["beneficiary_relation"],
        first_act_date=data["first_act_date"],
        notes=str(data.get("notes", "")).strip()[:2000],
        created_by=actor_id,
    )
    db.add(row)
    db.flush()
    return row


def get_registry_or_404(db: OrmSession, dsp_id: int) -> DspRegistry:
    row = db.get(DspRegistry, dsp_id)
    if row is None:
        raise AppError("errors.dsp_not_found", status_code=404, code="dsp_not_found")
    return row


def update_registry(db: OrmSession, row: DspRegistry, *, payload: dict) -> DspRegistry:
    if "caisse" in payload and payload["caisse"] is not None:
        if payload["caisse"] not in CAISSES:
            raise AppError("errors.invalid_caisse", status_code=400, code="invalid_caisse")
        row.caisse = payload["caisse"]
    if "insured_nin" in payload and payload["insured_nin"] is not None:
        row.insured_nin = str(payload["insured_nin"]).strip()[:18]
    if "affiliation_no" in payload and payload["affiliation_no"] is not None:
        row.affiliation_no = str(payload["affiliation_no"]).strip()[:40]
    if "beneficiary_relation" in payload and payload["beneficiary_relation"] is not None:
        if payload["beneficiary_relation"] not in BENEFICIARY_RELATIONS:
            raise AppError("errors.invalid_beneficiary", status_code=400, code="invalid_beneficiary")
        row.beneficiary_relation = payload["beneficiary_relation"]
    if "first_act_date" in payload and payload["first_act_date"] is not None:
        row.first_act_date = _parse_date(payload["first_act_date"], field_key="errors.invalid_date")
    if "notes" in payload and payload["notes"] is not None:
        row.notes = str(payload["notes"]).strip()[:2000]
    row.updated_at = now_tz()
    db.flush()
    return row


def create_act(db: OrmSession, registry: DspRegistry, *, payload: dict, actor_id: int | None) -> DspAct:
    label = str(payload.get("act_label", "")).strip()
    if not label:
        raise AppError("errors.dsp_act_label_required", status_code=400, code="dsp_act_label_required")
    act_date = _parse_date(payload.get("act_date"), field_key="errors.invalid_date")
    if registry.first_act_date and act_date < registry.first_act_date:
        raise AppError("errors.dsp_act_before_first", status_code=400, code="dsp_act_before_first")
    act = DspAct(
        dsp_id=registry.id,
        act_date=act_date,
        tooth=_validate_tooth(payload.get("tooth")),
        act_label=label[:200],
        act_code=str(payload.get("act_code", "")).strip()[:20],
        coefficient=Decimal(str(_dec(payload.get("coefficient")))),
        fee=Decimal(str(_dec(payload.get("fee")))),
        created_by=actor_id,
    )
    db.add(act)
    registry.updated_at = now_tz()
    db.flush()
    return act


def delete_act(db: OrmSession, registry: DspRegistry, act_id: int) -> None:
    act = db.get(DspAct, act_id)
    if act is None or act.dsp_id != registry.id:
        raise AppError("errors.dsp_act_not_found", status_code=404, code="dsp_act_not_found")
    db.delete(act)
    registry.updated_at = now_tz()
    db.flush()


def get_act_or_404(db: OrmSession, registry: DspRegistry, act_id: int) -> DspAct:
    act = db.get(DspAct, act_id)
    if act is None or act.dsp_id != registry.id:
        raise AppError("errors.dsp_act_not_found", status_code=404, code="dsp_act_not_found")
    return act


def list_registries(
    db: OrmSession, *, caisse: str | None = None, q: str = "", limit: int = 100
) -> list[dict]:
    query = (
        select(DspRegistry, Patient)
        .join(Patient, DspRegistry.patient_id == Patient.id)
        .order_by(DspRegistry.first_act_date.desc(), DspRegistry.id.desc())
        .limit(limit)
    )
    if caisse in CAISSES:
        query = query.where(DspRegistry.caisse == caisse)
    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        query = query.where(
            DspRegistry.insured_nin.ilike(like)
            | DspRegistry.affiliation_no.ilike(like)
            | Patient.nom.ilike(like)
            | Patient.prenom.ilike(like)
        )
    rows = db.execute(query).all()
    today = now_tz().date()
    out = []
    for registry, patient in rows:
        deadline = registry.first_act_date + timedelta(days=DEADLINE_DAYS)
        days_left = (deadline - today).days
        out.append(
            {
                **serialize_registry(registry),
                "patient": {
                    "id": patient.id,
                    "code": patient.code,
                    "nom": patient.nom,
                    "prenom": patient.prenom,
                    "telephone": patient.telephone,
                },
                "deadline_date": deadline.isoformat(),
                "days_to_deadline": days_left,
                "act_count": 0,
            }
        )
    return out


def serialize_registry(r: DspRegistry) -> dict:
    return {
        "id": r.id,
        "patient_id": r.patient_id,
        "caisse": r.caisse,
        "insured_nin": r.insured_nin,
        "affiliation_no": r.affiliation_no,
        "beneficiary_relation": r.beneficiary_relation,
        "first_act_date": r.first_act_date.isoformat(),
        "notes": r.notes,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


def serialize_act(a: DspAct) -> dict:
    return {
        "id": a.id,
        "dsp_id": a.dsp_id,
        "act_date": a.act_date.isoformat(),
        "tooth": a.tooth,
        "act_label": a.act_label,
        "act_code": a.act_code,
        "coefficient": str(a.coefficient),
        "fee": str(a.fee),
        "created_at": a.created_at.isoformat(),
    }


def registry_acts(db: OrmSession, dsp_id: int) -> list[DspAct]:
    return list(
        db.execute(
            select(DspAct).where(DspAct.dsp_id == dsp_id).order_by(DspAct.act_date.asc(), DspAct.id.asc())
        )
        .scalars()
        .all()
    )
