"""Clinical logic: notes, treatment catalog, patient treatments, odontogram."""
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as OrmSession

from app.core.dates import now_tz
from app.core.errors import AppError
from app.core.models import (
    ClinicalNote,
    PatientTreatment,
    ToothState,
    ToothStateHistory,
    TreatmentCatalogItem,
)
from app.core.money import serialize_amount
from app.patients.service import get_patient_or_404

# FDI numbering. Display order (upper right 18..11, upper left 21..28, lower
# left 38..48) is handled in the UI; here the lists validate tooth numbers.
FDI_PERMANENT = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28,
                 48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
FDI_DECIDUOUS = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65,
                 85, 84, 83, 82, 81, 71, 72, 73, 74, 75]
# Treatments accept both permanent and deciduous (51..85) teeth.
FDI_TEETH = FDI_PERMANENT + FDI_DECIDUOUS

# Odontogram conditions. 'sain' is a reset command, never stored: a healthy
# tooth has no row. Carie/obturation target one of the five surfaces; the other
# conditions apply to the whole tooth.
WHOLE_TOOTH_CONDITIONS = ("a_traiter", "couronne", "bridge", "absent")
SURFACE_CONDITIONS = ("carie", "obturation")
TOOTH_CONDITIONS = WHOLE_TOOTH_CONDITIONS + SURFACE_CONDITIONS
TOOTH_SURFACES = ("occlusale", "mesiale", "distale", "vestibulaire", "linguale")


def validate_note_input(*, motif: str, diagnostic: str, traitement: str, remarques: str) -> dict:
    data = {
        "motif": (motif or "").strip(),
        "diagnostic": (diagnostic or "").strip(),
        "traitement": (traitement or "").strip(),
        "remarques": (remarques or "").strip(),
    }
    if not any(data.values()):
        raise AppError("errors.note_empty", status_code=400, code="note_empty")
    return data


def validate_tooth(tooth: int | None) -> int | None:
    if tooth is None:
        return None
    try:
        tooth = int(tooth)
    except (TypeError, ValueError):
        raise AppError("errors.invalid_tooth", status_code=400, code="invalid_tooth") from None
    if tooth not in FDI_TEETH:
        raise AppError("errors.invalid_tooth", status_code=400, code="invalid_tooth")
    return tooth


def validate_odontogram_tooth(tooth: int) -> int:
    """Odontogram accepts both permanent and deciduous (55..85) teeth."""
    try:
        tooth = int(tooth)
    except (TypeError, ValueError):
        raise AppError("errors.invalid_tooth", status_code=400, code="invalid_tooth") from None
    if tooth not in FDI_PERMANENT and tooth not in FDI_DECIDUOUS:
        raise AppError("errors.invalid_tooth", status_code=400, code="invalid_tooth")
    return tooth


def create_note(db: OrmSession, *, patient_id: int, data: dict, actor_id: int | None) -> ClinicalNote:
    get_patient_or_404(db, patient_id)
    note = ClinicalNote(patient_id=patient_id, created_by=actor_id, updated_by=actor_id, **data)
    db.add(note)
    db.flush()
    return note


def get_note_or_404(db: OrmSession, note_id: int) -> ClinicalNote:
    note = db.get(ClinicalNote, note_id)
    if note is None:
        raise AppError("errors.note_not_found", status_code=404, code="note_not_found")
    return note


def update_note(db: OrmSession, note: ClinicalNote, *, data: dict, actor_id: int | None) -> None:
    for key, value in data.items():
        setattr(note, key, value)
    note.updated_by = actor_id
    note.updated_at = now_tz()


def latest_note(db: OrmSession, patient_id: int) -> ClinicalNote | None:
    return db.execute(
        select(ClinicalNote)
        .where(ClinicalNote.patient_id == patient_id)
        .order_by(ClinicalNote.created_at.desc(), ClinicalNote.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def notes_history(db: OrmSession, patient_id: int, limit: int = 100) -> list[ClinicalNote]:
    return list(
        db.execute(
            select(ClinicalNote)
            .where(ClinicalNote.patient_id == patient_id)
            .order_by(ClinicalNote.created_at.desc(), ClinicalNote.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def serialize_note(n: ClinicalNote, *, include_content: bool = True) -> dict:
    data = {
        "id": n.id,
        "patient_id": n.patient_id,
        "created_at": n.created_at.isoformat(),
        "updated_at": n.updated_at.isoformat(),
    }
    if include_content:
        data.update(
            {
                "motif": n.motif,
                "diagnostic": n.diagnostic,
                "traitement": n.traitement,
                "remarques": n.remarques,
            }
        )
    return data


# --------------------------------------------------------------------------- #
# Treatment catalog
# --------------------------------------------------------------------------- #


def get_catalog_item_or_404(db: OrmSession, item_id: int) -> TreatmentCatalogItem:
    item = db.get(TreatmentCatalogItem, item_id)
    if item is None:
        raise AppError("errors.catalog_item_not_found", status_code=404, code="not_found")
    return item


def create_catalog_item(db: OrmSession, *, name: str, category: str, default_price) -> TreatmentCatalogItem:
    name = (name or "").strip()
    if not name:
        raise AppError("errors.catalog_name_required", status_code=400, code="invalid_input")
    if category not in CATALOG_CATEGORIES:
        raise AppError("errors.invalid_category", status_code=400, code="invalid_category")
    from app.core.money import to_money

    try:
        price = to_money(default_price)
    except ValueError:
        raise AppError("errors.invalid_price", status_code=400, code="invalid_price") from None
    if price < 0:
        raise AppError("errors.invalid_price", status_code=400, code="invalid_price")
    exists = db.execute(
        select(TreatmentCatalogItem.id).where(func.lower(TreatmentCatalogItem.name) == name.lower())
    ).scalar_one_or_none()
    if exists:
        raise AppError("errors.catalog_name_taken", status_code=400, code="duplicate_name")
    item = TreatmentCatalogItem(name=name, category=category, default_price=price, is_active=True)
    db.add(item)
    db.flush()
    return item


CATALOG_CATEGORIES = (
    "Consultation",
    "Soins",
    "Chirurgie",
    "Prothèse",
    "Orthodontie",
    "Parodontologie",
    "Autre",
)


def serialize_catalog_item(item: TreatmentCatalogItem) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "default_price": serialize_amount(item.default_price),
        "is_active": item.is_active,
    }


# --------------------------------------------------------------------------- #
# Patient treatments
# --------------------------------------------------------------------------- #


def add_patient_treatment(
    db: OrmSession,
    *,
    patient_id: int,
    catalog_item_id: int | None,
    name: str | None,
    category: str | None,
    price,
    tooth: int | None,
    note: str,
    actor_id: int | None,
) -> PatientTreatment:
    from app.core.money import to_money

    get_patient_or_404(db, patient_id)
    tooth = validate_tooth(tooth)
    try:
        price_dec = to_money(price) if price not in (None, "") else Decimal("0")
    except ValueError:
        raise AppError("errors.invalid_price", status_code=400, code="invalid_price") from None
    if price_dec < 0:
        raise AppError("errors.invalid_price", status_code=400, code="invalid_price")

    catalog_item = None
    if catalog_item_id:
        catalog_item = get_catalog_item_or_404(db, catalog_item_id)
        if not catalog_item.is_active:
            raise AppError("errors.catalog_item_inactive", status_code=400, code="inactive_item")
        # Default to the catalog price when none is entered (quick workflow).
        if price_dec == 0:
            price_dec = to_money(catalog_item.default_price)

    final_name = (name or "").strip() if name else ""
    if catalog_item is not None and not final_name:
        final_name = catalog_item.name
    if not final_name:
        raise AppError("errors.treatment_name_required", status_code=400, code="name_required")
    if len(final_name) > 160:
        raise AppError("errors.treatment_name_too_long", status_code=400, code="name_too_long")

    treatment = PatientTreatment(
        patient_id=patient_id,
        catalog_item_id=catalog_item.id if catalog_item else None,
        name=final_name,
        category=(category or (catalog_item.category if catalog_item else "") or "Autre"),
        price=price_dec,
        tooth=tooth,
        note=(note or "").strip(),
        created_by=actor_id,
    )
    db.add(treatment)
    db.flush()
    # Auto-deduct linked consumables from stock (same transaction, idempotent,
    # clamps at zero — never blocks the treatment).
    if catalog_item is not None:
        from app.stock.service import apply_treatment_consumption

        apply_treatment_consumption(db, treatment, actor_id=actor_id)
    return treatment


def patient_treatments(db: OrmSession, patient_id: int, limit: int = 100) -> list[PatientTreatment]:
    return list(
        db.execute(
            select(PatientTreatment)
            .where(PatientTreatment.patient_id == patient_id)
            .order_by(PatientTreatment.created_at.desc(), PatientTreatment.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def serialize_treatment(t: PatientTreatment) -> dict:
    return {
        "id": t.id,
        "patient_id": t.patient_id,
        "name": t.name,
        "category": t.category,
        "price": serialize_amount(t.price),
        "tooth": t.tooth,
        "note": t.note,
        "created_at": t.created_at.isoformat(),
    }


# --------------------------------------------------------------------------- #
# Odontogram
# --------------------------------------------------------------------------- #


def tooth_conditions(db: OrmSession, patient_id: int) -> list[dict]:
    """Current odontogram: one entry per marked tooth/surface."""
    rows = (
        db.execute(
            select(ToothState)
            .where(ToothState.patient_id == patient_id)
            .order_by(ToothState.tooth, ToothState.surface)
        )
        .scalars()
        .all()
    )
    return [{"tooth": r.tooth, "condition": r.state, "surface": r.surface} for r in rows]


def tooth_history(db: OrmSession, patient_id: int, limit: int = 200) -> list[ToothStateHistory]:
    """Append-only audit of odontogram changes, most recent first."""
    return list(
        db.execute(
            select(ToothStateHistory)
            .where(ToothStateHistory.patient_id == patient_id)
            .order_by(ToothStateHistory.changed_at.desc(), ToothStateHistory.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def serialize_tooth_history(h: ToothStateHistory, actor_name: str | None = None) -> dict:
    return {
        "id": h.id,
        "tooth": h.tooth,
        "surface": h.surface,
        "condition": h.condition,
        "action": h.action,
        "changed_at": h.changed_at.isoformat(),
        "changed_by": actor_name,
    }


def _record_tooth_history(
    db: OrmSession,
    *,
    patient_id: int,
    tooth: int,
    surface: str,
    condition: str,
    action: str,
    actor_id: int | None,
) -> None:
    db.add(
        ToothStateHistory(
            patient_id=patient_id,
            tooth=tooth,
            surface=surface,
            condition=condition,
            action=action,
            changed_by=actor_id,
        )
    )


def _upsert_tooth_row(
    db: OrmSession, *, patient_id: int, tooth: int, surface: str, state: str, actor_id: int | None
) -> None:
    row = db.execute(
        select(ToothState).where(
            ToothState.patient_id == patient_id,
            ToothState.tooth == tooth,
            ToothState.surface == surface,
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(
            ToothState(
                patient_id=patient_id,
                tooth=tooth,
                surface=surface,
                state=state,
                updated_by=actor_id,
            )
        )
    else:
        row.state = state
        row.updated_by = actor_id
        row.updated_at = now_tz()


def set_tooth_condition(
    db: OrmSession, *, patient_id: int, tooth: int, condition: str, surface: str, actor_id: int | None
) -> dict:
    """Apply a condition change. 'sain' clears the tooth; 'couronne' coexists
    with surface marks (a crowned tooth may still carry carie/obturation
    records); other whole-tooth conditions replace any surface marks."""
    get_patient_or_404(db, patient_id)
    tooth = validate_odontogram_tooth(tooth)
    condition = (condition or "").strip().lower()
    surface = (surface or "").strip().lower()

    if condition == "sain":
        # 'sain' with a surface clears that single mark; without one it clears
        # the whole tooth (whole-tooth row + all surface marks).
        where = [ToothState.patient_id == patient_id, ToothState.tooth == tooth]
        if surface:
            if surface not in TOOTH_SURFACES:
                raise AppError("errors.surface_required", status_code=400, code="surface_required")
            where.append(ToothState.surface == surface)
        deleted = db.execute(delete(ToothState).where(*where))
        removed = deleted.rowcount or 0
        if removed:
            # Audit only when something actually changed, so empty clearings
            # don't fill the log. A whole-tooth reset purges surface marks too:
            # one row covers the reset (details live in tooth_states before it).
            _record_tooth_history(
                db, patient_id=patient_id, tooth=tooth, surface=surface,
                condition="sain", action="clear", actor_id=actor_id,
            )
        db.flush()
        return {"tooth": tooth, "condition": "sain", "surface": surface}

    if condition not in TOOTH_CONDITIONS:
        raise AppError("errors.invalid_tooth_state", status_code=400, code="invalid_state")

    if condition in SURFACE_CONDITIONS:
        if surface not in TOOTH_SURFACES:
            raise AppError("errors.surface_required", status_code=400, code="surface_required")
        _upsert_tooth_row(
            db, patient_id=patient_id, tooth=tooth, surface=surface, state=condition, actor_id=actor_id
        )
        _record_tooth_history(
            db, patient_id=patient_id, tooth=tooth, surface=surface,
            condition=condition, action="set", actor_id=actor_id,
        )
        db.flush()
        return {"tooth": tooth, "condition": condition, "surface": surface}

    if surface:
        raise AppError("errors.surface_not_allowed", status_code=400, code="surface_not_allowed")
    if condition != "couronne":
        # Only non-couronne whole-tooth states wipe surface marks; a crowned
        # tooth keeps its carie/obturation records alongside the restoration.
        db.execute(
            delete(ToothState).where(
                ToothState.patient_id == patient_id,
                ToothState.tooth == tooth,
                ToothState.surface != "",
            )
        )
    _upsert_tooth_row(
        db, patient_id=patient_id, tooth=tooth, surface="", state=condition, actor_id=actor_id
    )
    _record_tooth_history(
        db, patient_id=patient_id, tooth=tooth, surface="",
        condition=condition, action="set", actor_id=actor_id,
    )
    db.flush()
    return {"tooth": tooth, "condition": condition, "surface": ""}


def treatments_by_tooth(db: OrmSession, patient_id: int) -> dict[int, list[dict]]:
    rows = list(
        db.execute(
            select(PatientTreatment)
            .where(
                PatientTreatment.patient_id == patient_id,
                PatientTreatment.tooth.isnot(None),
            )
            .order_by(PatientTreatment.created_at.desc(), PatientTreatment.id.desc())
        )
        .scalars()
        .all()
    )
    result: dict[int, list[dict]] = {}
    for t in rows:
        result.setdefault(t.tooth, []).append(serialize_treatment(t))
    return result
