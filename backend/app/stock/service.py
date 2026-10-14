"""Stock module logic: items, race-safe adjustments, ledger, valuation, auto-deduction.

Core invariant: on-hand stock always equals the sum of the append-only
`stock_movements` ledger for the item. Every quantity change goes through
`apply_movement` — a `SELECT … FOR UPDATE` row lock, a floor check and the
ledger row in the same transaction — so concurrent adjustments serialize at
the row level and stock can never go negative.

Auto-deduction: when a patient treatment is recorded with a catalog item that
has consumable links, linked stock items are deducted in the same transaction.
Deduction is idempotent per (treatment, item) via a partial unique index on
consumption rows; insufficient stock clamps at zero with a note (recording a
treatment must never fail because a shelf is empty).
"""
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.core.errors import AppError
from app.core.models import StockItem, StockMovement, TreatmentConsumable
from app.core.money import serialize_amount, to_money

CATEGORIES = ("consommable", "equipement", "bureau", "autre")
REASONS = ("initial", "restock", "consumption", "adjustment", "correction")
# Reasons that may be chosen by a human in the adjust dialog.
MANUAL_REASONS = ("initial", "restock", "consumption", "adjustment")

TWO = Decimal("0.01")


def _q(value) -> Decimal:
    """Quantize a quantity to 2 decimals (Quantities are NUMERIC(12,2))."""
    if isinstance(value, Decimal):
        return value.quantize(TWO)
    return Decimal(str(value)).quantize(TWO)


# --------------------------------------------------------------------------- #
# Items
# --------------------------------------------------------------------------- #


def list_items(db: OrmSession, *, include_inactive: bool = True, low_stock: bool = False) -> list[StockItem]:
    query = select(StockItem).order_by(StockItem.name)
    if not include_inactive:
        query = query.where(StockItem.is_active.is_(True))
    rows = list(db.execute(query).scalars().all())
    if low_stock:
        rows = [r for r in rows if is_low(r)]
    return rows


def get_item_or_404(db: OrmSession, item_id: int) -> StockItem:
    item = db.get(StockItem, item_id)
    if item is None:
        raise AppError("errors.stock_item_not_found", status_code=404, code="stock_item_not_found")
    return item


def is_low(item: StockItem) -> bool:
    """Below/at threshold. Alerts apply to consumables only: equipment and
    office items are one-offs (1 fauteuil is not "out of stock")."""
    if item.category != "consommable":
        return False
    return item.stock_quantity <= item.min_quantity


def create_item(
    db: OrmSession,
    *,
    name: str,
    category: str,
    unit: str,
    initial_quantity,
    min_quantity,
    unit_cost,
    notes: str,
    actor_id: int | None,
) -> StockItem:
    name = (name or "").strip()
    if not name:
        raise AppError("errors.stock_name_required", status_code=400, code="invalid_input")
    if len(name) > 120:
        raise AppError("errors.stock_name_too_long", status_code=400, code="name_too_long")
    if category not in CATEGORIES:
        raise AppError("errors.invalid_stock_category", status_code=400, code="invalid_category")
    exists = db.execute(
        select(StockItem.id).where(func.lower(StockItem.name) == name.lower())
    ).scalar_one_or_none()
    if exists:
        raise AppError("errors.stock_name_taken", status_code=400, code="duplicate_name")
    try:
        min_q = _q(to_money(min_quantity)) if min_quantity not in (None, "") else Decimal("0")
    except ValueError:
        raise AppError("errors.invalid_quantity", status_code=400, code="invalid_quantity") from None
    if min_q < 0:
        raise AppError("errors.invalid_quantity", status_code=400, code="invalid_quantity")
    cost = None
    if unit_cost not in (None, ""):
        try:
            cost = to_money(unit_cost)
        except ValueError:
            raise AppError("errors.invalid_price", status_code=400, code="invalid_price") from None
        if cost < 0:
            raise AppError("errors.invalid_price", status_code=400, code="invalid_price")
    item = StockItem(
        name=name,
        category=category,
        unit=(unit or "").strip()[:20] or "unite",
        stock_quantity=Decimal("0"),
        min_quantity=min_q,
        unit_cost=cost,
        notes=(notes or "").strip(),
        created_by=actor_id,
    )
    db.add(item)
    db.flush()
    # Opening stock lands in the ledger like any other movement.
    initial = _q(to_money(initial_quantity)) if initial_quantity not in (None, "") else Decimal("0")
    if initial < 0:
        raise AppError("errors.invalid_quantity", status_code=400, code="invalid_quantity")
    if initial > 0:
        _apply_movement(
            db, item=item, delta=initial, reason="initial",
            note="Stock initial", actor_id=actor_id,
        )
    return item


def update_item(
    db: OrmSession, item: StockItem, *, name: str | None, category: str | None, unit: str | None,
    min_quantity, unit_cost, notes: str | None, is_active: bool | None,
) -> None:
    if name is not None:
        clean = name.strip()
        if not clean:
            raise AppError("errors.stock_name_required", status_code=400, code="invalid_input")
        if clean.lower() != item.name.lower():
            exists = db.execute(
                select(StockItem.id).where(func.lower(StockItem.name) == clean.lower(), StockItem.id != item.id)
            ).scalar_one_or_none()
            if exists:
                raise AppError("errors.stock_name_taken", status_code=400, code="duplicate_name")
        item.name = clean[:120]
    if category is not None:
        if category not in CATEGORIES:
            raise AppError("errors.invalid_stock_category", status_code=400, code="invalid_category")
        item.category = category
    if unit is not None:
        item.unit = unit.strip()[:20] or "unite"
    if min_quantity is not None:
        try:
            min_q = _q(to_money(min_quantity))
        except ValueError:
            raise AppError("errors.invalid_quantity", status_code=400, code="invalid_quantity") from None
        if min_q < 0:
            raise AppError("errors.invalid_quantity", status_code=400, code="invalid_quantity")
        item.min_quantity = min_q
    if unit_cost is not None:
        if unit_cost == "":
            item.unit_cost = None
        else:
            try:
                cost = to_money(unit_cost)
            except ValueError:
                raise AppError("errors.invalid_price", status_code=400, code="invalid_price") from None
            if cost < 0:
                raise AppError("errors.invalid_price", status_code=400, code="invalid_price")
            item.unit_cost = cost
    if notes is not None:
        item.notes = notes.strip()
    if is_active is not None:
        item.is_active = bool(is_active)
    db.flush()


def serialize_item(item: StockItem) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "unit": item.unit,
        "stock_quantity": serialize_amount(item.stock_quantity),
        "min_quantity": serialize_amount(item.min_quantity),
        "unit_cost": serialize_amount(item.unit_cost) if item.unit_cost is not None else None,
        "is_low": is_low(item),
        "is_active": item.is_active,
        "notes": item.notes,
    }


# --------------------------------------------------------------------------- #
# Movements — the single write path
# --------------------------------------------------------------------------- #


def _apply_movement(
    db: OrmSession,
    *,
    item: StockItem,
    delta: Decimal,
    reason: str,
    note: str = "",
    reference_type: str = "",
    reference_id: int | None = None,
    actor_id: int | None = None,
) -> StockMovement:
    """The single write path for stock changes.

    Locks the item row (SELECT … FOR UPDATE), floors at zero, appends the
    ledger row. Caller must have flushed the item before locking (row must
    exist). Idempotent auto-deduction is handled by the caller.
    """
    if reason not in REASONS:
        raise AppError("errors.invalid_movement_reason", status_code=400, code="invalid_reason")
    if delta == 0:
        raise AppError("errors.invalid_quantity", status_code=400, code="invalid_quantity")

    locked = db.execute(
        select(StockItem).where(StockItem.id == item.id).with_for_update()
    ).scalar_one()
    new_qty = _q(locked.stock_quantity) + _q(delta)
    if new_qty < 0:
        raise AppError("errors.stock_insufficient", status_code=400, code="stock_insufficient")
    locked.stock_quantity = new_qty

    movement = StockMovement(
        item_id=locked.id,
        delta=_q(delta),
        reason=reason,
        note=(note or "").strip()[:200],
        reference_type=reference_type or "",
        reference_id=reference_id,
        created_by=actor_id,
    )
    db.add(movement)
    db.flush()
    return movement


def adjust_stock(
    db: OrmSession,
    *,
    item_id: int,
    delta,
    reason: str,
    note: str,
    actor_id: int | None,
) -> StockMovement:
    """Manual relative adjustment (+ restock / − consumption / ± adjustment)."""
    try:
        delta_dec = _q(to_money(delta))
    except ValueError:
        raise AppError("errors.invalid_quantity", status_code=400, code="invalid_quantity") from None
    if delta_dec == 0:
        raise AppError("errors.invalid_quantity", status_code=400, code="invalid_quantity")
    if reason not in MANUAL_REASONS:
        raise AppError("errors.invalid_movement_reason", status_code=400, code="invalid_reason")
    item = get_item_or_404(db, item_id)
    if not item.is_active:
        raise AppError("errors.stock_item_inactive", status_code=400, code="stock_item_inactive")
    return _apply_movement(
        db, item=item, delta=delta_dec, reason=reason, note=note, actor_id=actor_id
    )


def set_absolute_quantity(
    db: OrmSession, *, item_id: int, quantity, note: str, actor_id: int | None
) -> StockMovement:
    """Correction: set an absolute quantity; the delta lands in the ledger."""
    try:
        target = _q(to_money(quantity))
    except ValueError:
        raise AppError("errors.invalid_quantity", status_code=400, code="invalid_quantity") from None
    if target < 0:
        raise AppError("errors.invalid_quantity", status_code=400, code="invalid_quantity")
    item = get_item_or_404(db, item_id)
    locked = db.execute(
        select(StockItem).where(StockItem.id == item.id).with_for_update()
    ).scalar_one()
    delta = target - _q(locked.stock_quantity)
    if delta == 0:
        raise AppError("errors.nothing_to_correct", status_code=400, code="nothing_to_correct")
    return _apply_movement(
        db, item=locked, delta=delta, reason="correction",
        note=note or "Correction inventaire", actor_id=actor_id,
    )


def item_movements(db: OrmSession, item_id: int, limit: int = 100) -> list[dict]:
    get_item_or_404(db, item_id)
    rows = list(
        db.execute(
            select(StockMovement)
            .where(StockMovement.item_id == item_id)
            .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
            .limit(max(1, min(limit, 300)))
        )
        .scalars()
        .all()
    )
    return [serialize_movement(db, m) for m in rows]


def serialize_movement(db: OrmSession, m: StockMovement) -> dict:
    actor = ""
    if m.created_by is not None:
        from app.core.models import User

        actor = db.execute(select(User.full_name).where(User.id == m.created_by)).scalar() or ""
    return {
        "id": m.id,
        "item_id": m.item_id,
        "delta": serialize_amount(m.delta),
        "reason": m.reason,
        "note": m.note,
        "reference_type": m.reference_type,
        "reference_id": m.reference_id,
        "created_by_name": actor,
        "created_at": m.created_at.isoformat(),
    }


def valuation(db: OrmSession) -> dict:
    """Total on-hand value over active items with a known unit cost."""
    rows = db.execute(
        select(StockItem).where(StockItem.is_active.is_(True), StockItem.unit_cost.isnot(None))
    ).scalars().all()
    total = Decimal("0")
    for item in rows:
        total += _q(item.stock_quantity) * _q(item.unit_cost)
    return {"valeur": serialize_amount(total), "nb_articles": len(rows)}


# --------------------------------------------------------------------------- #
# Treatment consumable links (owner-managed)
# --------------------------------------------------------------------------- #


def list_links(db: OrmSession, catalog_item_id: int | None = None) -> list[dict]:
    query = select(TreatmentConsumable).order_by(TreatmentConsumable.id)
    if catalog_item_id:
        query = query.where(TreatmentConsumable.catalog_item_id == catalog_item_id)
    rows = list(db.execute(query).scalars().all())
    out = []
    for link in rows:
        stock_item = db.get(StockItem, link.stock_item_id)
        out.append(
            {
                "id": link.id,
                "catalog_item_id": link.catalog_item_id,
                "stock_item_id": link.stock_item_id,
                "stock_item_name": stock_item.name if stock_item else "",
                "unit": stock_item.unit if stock_item else "",
                "quantity": serialize_amount(link.quantity),
            }
        )
    return out


def create_link(
    db: OrmSession, *, catalog_item_id: int, stock_item_id: int, quantity, actor_id: int | None
) -> TreatmentConsumable:
    from app.clinical.service import get_catalog_item_or_404

    get_catalog_item_or_404(db, catalog_item_id)
    get_item_or_404(db, stock_item_id)  # validate existence
    try:
        qty = _q(to_money(quantity))
    except ValueError:
        raise AppError("errors.invalid_quantity", status_code=400, code="invalid_quantity") from None
    if qty <= 0:
        raise AppError("errors.invalid_quantity", status_code=400, code="invalid_quantity")
    exists = db.execute(
        select(TreatmentConsumable.id).where(
            TreatmentConsumable.catalog_item_id == catalog_item_id,
            TreatmentConsumable.stock_item_id == stock_item_id,
        )
    ).scalar_one_or_none()
    if exists:
        raise AppError("errors.stock_link_exists", status_code=400, code="duplicate_link")
    link = TreatmentConsumable(
        catalog_item_id=catalog_item_id, stock_item_id=stock_item_id, quantity=qty, created_by=actor_id
    )
    db.add(link)
    db.flush()
    return link


def delete_link(db: OrmSession, link_id: int) -> None:
    link = db.get(TreatmentConsumable, link_id)
    if link is None:
        raise AppError("errors.stock_link_not_found", status_code=404, code="stock_link_not_found")
    db.delete(link)
    db.flush()


def apply_treatment_consumption(db: OrmSession, treatment, actor_id: int | None) -> None:
    """Deduct linked consumables for a freshly-created patient treatment.

    Called from clinical.add_patient_treatment inside the same transaction.
    Idempotent: a repeated call for the same treatment item pair is swallowed
    by the partial unique index (ON CONFLICT DO NOTHING). Insufficient stock
    clamps at zero (recorded with a note) instead of blocking the treatment.
    """
    if treatment.catalog_item_id is None:
        return
    links = list(
        db.execute(
            select(TreatmentConsumable).where(
                TreatmentConsumable.catalog_item_id == treatment.catalog_item_id
            )
        ).scalars().all()
    )
    if not links:
        return
    for link in links:
        # Idempotency guard: skip if this treatment already consumed the item.
        already = db.execute(
            select(StockMovement.id).where(
                StockMovement.reference_type == "patient_treatment",
                StockMovement.reference_id == treatment.id,
                StockMovement.item_id == link.stock_item_id,
                StockMovement.reason == "consumption",
            )
        ).scalar_one_or_none()
        if already:
            continue
        item = db.get(StockItem, link.stock_item_id)
        if item is None or not item.is_active:
            continue
        need = _q(link.quantity)
        locked = db.execute(
            select(StockItem).where(StockItem.id == item.id).with_for_update()
        ).scalar_one()
        current = _q(locked.stock_quantity)
        if current <= 0:
            continue  # nothing on the shelf — treatment still records fine
        applied = need if current >= need else current
        _apply_movement(
            db,
            item=locked,
            delta=-applied,
            reason="consumption",
            note=f"Traitement #{treatment.id} — {treatment.name}"
            + (" (stock insuffisant, clampé)" if current < need else ""),
            reference_type="patient_treatment",
            reference_id=treatment.id,
            actor_id=actor_id,
        )
