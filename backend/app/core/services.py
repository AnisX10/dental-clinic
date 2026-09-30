"""Clinic services: users, settings, catalog seeding, patient numbering."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.core.errors import AppError
from app.core.models import ClinicSettings, Patient, TreatmentCatalogItem, User
from app.core.security import hash_password

# Default treatment catalog (name, category, default price in DA).
DEFAULT_CATALOG = [
    ("Consultation", "Consultation", 1500),
    ("Consultation de contrôle", "Consultation", 1000),
    ("Détartrage", "Soins", 3000),
    ("Composite", "Soins", 3500),
    ("Amalgame", "Soins", 2500),
    ("Traitement de canal (1 canal)", "Soins", 6000),
    ("Traitement de canal (multi-canaux)", "Soins", 9000),
    ("Extraction simple", "Chirurgie", 2000),
    ("Extraction dent de sagesse", "Chirurgie", 5000),
    ("Extraction complexe", "Chirurgie", 7000),
    ("Couronne céramique", "Prothèse", 18000),
    ("Couronne métallique", "Prothèse", 12000),
    ("Bridge (par dent)", "Prothèse", 15000),
    ("Prothèse amovible partielle", "Prothèse", 25000),
    ("Prothèse complète", "Prothèse", 45000),
    ("Appareil orthodontique (métal)", "Orthodontie", 60000),
    ("Appareil orthodontique (céramique)", "Orthodontie", 80000),
    ("Détartrage parodontal", "Parodontologie", 4000),
    ("Traitement parodontal", "Parodontologie", 8000),
    ("Radiographie rétro-alvéolaire", "Autre", 800),
    ("Panoramique dentaire", "Autre", 2000),
]

CATEGORIES = [
    "Consultation",
    "Soins",
    "Chirurgie",
    "Prothèse",
    "Orthodontie",
    "Parodontologie",
    "Autre",
]


def get_settings_row(db: OrmSession) -> ClinicSettings:
    row = db.get(ClinicSettings, 1)
    if row is None:
        row = ClinicSettings(id=1)
        db.add(row)
        db.flush()
    return row


def create_user(
    db: OrmSession,
    *,
    username: str,
    password: str,
    full_name: str,
    role: str,
    is_owner: bool = False,
) -> User:
    username = username.strip().lower()
    if not username or not password:
        raise AppError("errors.invalid_user_data", status_code=400, code="invalid_user")
    if role not in ("dentiste", "reception"):
        raise AppError("errors.invalid_role", status_code=400, code="invalid_role")
    if len(password) < 8:
        raise AppError("errors.password_too_short", status_code=400, code="weak_password")
    exists = db.execute(select(User.id).where(User.username == username)).scalar_one_or_none()
    if exists:
        raise AppError("errors.username_taken", status_code=400, code="username_taken")
    user = User(
        username=username,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        role=role,
        is_owner=is_owner,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def next_patient_code(db: OrmSession) -> str:
    """Human-friendly internal patient number, computed from current max id."""
    max_id = db.execute(select(func.max(Patient.id))).scalar() or 0
    return f"P-{max_id + 1:06d}"


def seed_catalog(db: OrmSession) -> int:
    """Idempotently insert the default treatment catalog. Returns added count."""
    added = 0
    existing = set(
        db.execute(select(TreatmentCatalogItem.name)).scalars().all()
    )
    for name, category, price in DEFAULT_CATALOG:
        if name in existing:
            continue
        db.add(
            TreatmentCatalogItem(
                name=name, category=category, default_price=price, is_active=True
            )
        )
        added += 1
    if added:
        db.flush()
    return added
