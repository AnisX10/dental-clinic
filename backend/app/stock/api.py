"""Stock API: items, race-safe adjustments, ledger history, valuation, links."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession

from app.core.audit import log_action
from app.core.auth import get_client_ip, get_current_user, require_owner
from app.core.db import get_db
from app.core.models import User
from app.core.money import serialize_amount
from app.stock import service

router = APIRouter(prefix="/api/stock", tags=["stock"])


class StockItemCreate(BaseModel):
    name: str
    category: str
    unit: str = "unite"
    initial_quantity: str | int | float = "0"
    min_quantity: str | int | float = "0"
    unit_cost: str | int | float | None = None
    notes: str = ""


class StockItemUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    unit: str | None = None
    min_quantity: str | int | float | None = None
    unit_cost: str | int | float | None = None
    notes: str | None = None
    is_active: bool | None = None


class StockAdjust(BaseModel):
    delta: str | int | float
    reason: str = "adjustment"
    note: str = ""


class StockCorrect(BaseModel):
    quantity: str | int | float
    note: str = ""


class LinkCreate(BaseModel):
    catalog_item_id: int
    stock_item_id: int
    quantity: str | int | float


@router.get("")
def list_items(
    include_inactive: bool = True,
    low_stock: bool = False,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    rows = service.list_items(db, include_inactive=include_inactive, low_stock=low_stock)
    low_count = sum(1 for r in service.list_items(db, include_inactive=True) if service.is_low(r))
    return {"items": [service.serialize_item(i) for i in rows], "low_count": low_count}


@router.post("", status_code=201)
def create_item(
    payload: StockItemCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    item = service.create_item(
        db,
        name=payload.name,
        category=payload.category,
        unit=payload.unit,
        initial_quantity=payload.initial_quantity,
        min_quantity=payload.min_quantity,
        unit_cost=payload.unit_cost,
        notes=payload.notes,
        actor_id=user.id,
    )
    log_action(
        db, actor_id=user.id, action="stock_item_create", entity="stock_item", entity_id=item.id,
        detail={"name": item.name, "initial": serialize_amount(item.stock_quantity)},
        ip=get_client_ip(request),
    )
    return {"item": service.serialize_item(item)}


@router.patch("/{item_id}")
def update_item(
    item_id: int,
    payload: StockItemUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    item = service.get_item_or_404(db, item_id)
    service.update_item(
        db, item, name=payload.name, category=payload.category, unit=payload.unit,
        min_quantity=payload.min_quantity, unit_cost=payload.unit_cost, notes=payload.notes,
        is_active=payload.is_active,
    )
    log_action(
        db, actor_id=user.id, action="stock_item_update", entity="stock_item", entity_id=item.id,
        detail={"fields": [k for k, v in payload.model_dump().items() if v is not None]},
        ip=get_client_ip(request),
    )
    return {"item": service.serialize_item(item)}


@router.post("/{item_id}/adjust", status_code=201)
def adjust_item(
    item_id: int,
    payload: StockAdjust,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    movement = service.adjust_stock(
        db, item_id=item_id, delta=payload.delta, reason=payload.reason, note=payload.note,
        actor_id=user.id,
    )
    item = service.get_item_or_404(db, item_id)
    log_action(
        db, actor_id=user.id, action="stock_adjust", entity="stock_item", entity_id=item_id,
        detail={"delta": serialize_amount(movement.delta), "reason": movement.reason,
                "new_quantity": serialize_amount(item.stock_quantity)},
        ip=get_client_ip(request),
    )
    return {"item": service.serialize_item(item), "movement": service.serialize_movement(db, movement)}


@router.post("/{item_id}/correct", status_code=201)
def correct_item(
    item_id: int,
    payload: StockCorrect,
    request: Request,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    movement = service.set_absolute_quantity(
        db, item_id=item_id, quantity=payload.quantity, note=payload.note, actor_id=user.id
    )
    item = service.get_item_or_404(db, item_id)
    log_action(
        db, actor_id=user.id, action="stock_correct", entity="stock_item", entity_id=item_id,
        detail={"delta": serialize_amount(movement.delta), "new_quantity": serialize_amount(item.stock_quantity)},
        ip=get_client_ip(request),
    )
    return {"item": service.serialize_item(item), "movement": service.serialize_movement(db, movement)}


@router.get("/{item_id}/movements")
def item_movements(
    item_id: int,
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    return {"movements": service.item_movements(db, item_id, limit=limit)}


@router.get("/valuation")
def valuation(
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    return service.valuation(db)


@router.get("/links")
def list_links(
    catalog_item_id: int | None = None,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
):
    return {"links": service.list_links(db, catalog_item_id=catalog_item_id)}


@router.post("/links", status_code=201)
def create_link(
    payload: LinkCreate,
    request: Request,
    user: User = Depends(require_owner),
    db: OrmSession = Depends(get_db),
):
    link = service.create_link(
        db, catalog_item_id=payload.catalog_item_id, stock_item_id=payload.stock_item_id,
        quantity=payload.quantity, actor_id=user.id,
    )
    log_action(
        db, actor_id=user.id, action="stock_link_create", entity="treatment_consumable", entity_id=link.id,
        detail={"catalog_item_id": link.catalog_item_id, "stock_item_id": link.stock_item_id,
                "quantity": serialize_amount(link.quantity)},
        ip=get_client_ip(request),
    )
    stock_item = service.get_item_or_404(db, link.stock_item_id)
    return {
        "link": {
            "id": link.id,
            "catalog_item_id": link.catalog_item_id,
            "stock_item_id": link.stock_item_id,
            "stock_item_name": stock_item.name,
            "unit": stock_item.unit,
            "quantity": serialize_amount(link.quantity),
        }
    }


@router.delete("/links/{link_id}", status_code=204)
def delete_link(
    link_id: int,
    request: Request,
    user: User = Depends(require_owner),
    db: OrmSession = Depends(get_db),
):
    service.delete_link(db, link_id)
    log_action(
        db, actor_id=user.id, action="stock_link_delete", entity="treatment_consumable", entity_id=link_id,
        detail={}, ip=get_client_ip(request),
    )
    return None
