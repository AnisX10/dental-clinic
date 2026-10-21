from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession

from app.core.audit import log_action
from app.core.auth import get_client_ip, get_current_user, require_owner
from app.core.db import get_db
from app.core.models import User
from app.core.money import to_money
from app.core.services import get_settings_row
from app.documents.service import clinic_template_data

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    clinic_name: str | None = None
    doctor_name: str | None = None
    address: str | None = None
    phone: str | None = None
    header_note: str | None = None
    footer_note: str | None = None
    backup_hour: int | None = None
    backup_keep_daily: int | None = None
    backup_keep_manual: int | None = None
    dsp_default_caisse: str | None = None
    dsp_default_code: str | None = None
    dsp_default_coefficient: str | int | float | None = None
    dsp_default_fee: str | int | float | None = None


@router.get("")
def get_settings_view(user: User = Depends(get_current_user), db: OrmSession = Depends(get_db)):
    settings = get_settings_row(db)
    data = clinic_template_data(settings)
    data["backup_hour"] = settings.backup_hour
    data["backup_keep_daily"] = settings.backup_keep_daily
    data["backup_keep_manual"] = settings.backup_keep_manual
    data["dsp_default_caisse"] = settings.dsp_default_caisse
    data["dsp_default_code"] = settings.dsp_default_code
    data["dsp_default_coefficient"] = str(settings.dsp_default_coefficient)
    data["dsp_default_fee"] = str(settings.dsp_default_fee)
    from app.core.config import APP_VERSION

    data["version"] = APP_VERSION
    return {"settings": data}


@router.put("")
def update_settings(
    payload: SettingsUpdate,
    request: Request,
    user: User = Depends(require_owner),
    db: OrmSession = Depends(get_db),
):
    settings = get_settings_row(db)
    changes = []

    text_fields = {
        "clinic_name": 160,
        "doctor_name": 160,
        "address": 255,
        "phone": 40,
        "header_note": 500,
        "footer_note": 500,
    }
    for field, max_len in text_fields.items():
        value = getattr(payload, field)
        if value is not None:
            clean = value.strip()[:max_len]
            if clean != getattr(settings, field):
                setattr(settings, field, clean)
                changes.append(field)

    if payload.backup_hour is not None:
        hour = int(payload.backup_hour)
        if not 0 <= hour <= 23:
            from app.core.errors import AppError

            raise AppError("errors.invalid_backup_hour", status_code=400, code="invalid_backup_hour")
        if hour != settings.backup_hour:
            settings.backup_hour = hour
            changes.append("backup_hour")
    for field in ("backup_keep_daily", "backup_keep_manual"):
        value = getattr(payload, field)
        if value is not None:
            num = max(1, min(60, int(value)))
            if num != getattr(settings, field):
                setattr(settings, field, num)
                changes.append(field)

    if payload.dsp_default_caisse is not None:
        from app.dsp.service import CAISSES

        caisse = payload.dsp_default_caisse.strip()
        if caisse not in CAISSES:
            from app.core.errors import AppError

            raise AppError("errors.invalid_caisse", status_code=400, code="invalid_caisse")
        if caisse != settings.dsp_default_caisse:
            settings.dsp_default_caisse = caisse
            changes.append("dsp_default_caisse")
    if payload.dsp_default_code is not None:
        code = payload.dsp_default_code.strip()[:20]
        if code != settings.dsp_default_code:
            settings.dsp_default_code = code
            changes.append("dsp_default_code")
    if payload.dsp_default_coefficient is not None:
        try:
            coeff = max(Decimal("0.00"), Decimal(str(payload.dsp_default_coefficient)))
        except (ValueError, ArithmeticError):
            raise AppError("errors.invalid_amount", status_code=400, code="invalid_amount") from None
        if coeff != settings.dsp_default_coefficient:
            settings.dsp_default_coefficient = coeff
            changes.append("dsp_default_coefficient")
    if payload.dsp_default_fee is not None:
        try:
            fee = to_money(payload.dsp_default_fee)
            if fee < 0:
                raise ValueError
        except ValueError:
            raise AppError("errors.invalid_amount", status_code=400, code="invalid_amount") from None
        if fee != settings.dsp_default_fee:
            settings.dsp_default_fee = fee
            changes.append("dsp_default_fee")

    if changes:

        from app.core.dates import now_tz

        settings.updated_at = now_tz()
        _ = now_tz  # keep import local usage clear
        log_action(
            db,
            actor_id=user.id,
            action="settings_update",
            entity="clinic_settings",
            entity_id=1,
            detail={"fields": changes},
            ip=get_client_ip(request),
        )
    return {"settings": (lambda s: {
        **clinic_template_data(s),
        "backup_hour": s.backup_hour,
        "backup_keep_daily": s.backup_keep_daily,
        "backup_keep_manual": s.backup_keep_manual,
        "dsp_default_caisse": s.dsp_default_caisse,
        "dsp_default_code": s.dsp_default_code,
        "dsp_default_coefficient": str(s.dsp_default_coefficient),
        "dsp_default_fee": str(s.dsp_default_fee),
    })(settings)}
