"""SQLAlchemy models for the clinic data model.

Design notes:
- Money uses Numeric(12,2) everywhere (never floats).
- Clinical/financial records are never hard-deleted; corrections are new
  records (append-only payments) or status changes (appointments, lab orders).
- Append-only event tables keep the history of appointments, backups, stock
  movements and sensitive actions (audit log).
"""
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    from app.core.dates import now_tz

    return now_tz()


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- #
# Auth / users / settings
# --------------------------------------------------------------------------- #


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    # Two logical roles: "dentiste" and "reception".
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # Owner-level account privilege for price/settings changes (no third role).
    is_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (CheckConstraint("role IN ('dentiste', 'reception')", name="ck_users_role"),)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    user: Mapped[User] = relationship(lazy="joined")


class ClinicSettings(Base):
    """Singleton row (id = 1) holding clinic identity and operational options."""

    __tablename__ = "clinic_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    clinic_name: Mapped[str] = mapped_column(String(160), nullable=False, default="Cabinet Dentaire")
    doctor_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    logo_path: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    header_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    footer_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    backup_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    backup_keep_daily: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    backup_keep_manual: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, index=True)


# --------------------------------------------------------------------------- #
# Patients
# --------------------------------------------------------------------------- #


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Background internal number: P-000001...
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nom: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    prenom: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    telephone: Mapped[str] = mapped_column(String(30), nullable=False)
    telephone2: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    adresse: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    wilaya: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    medical: Mapped["MedicalProfile | None"] = relationship(
        back_populates="patient", uselist=False, cascade="all, delete-orphan", lazy="joined"
    )

    __table_args__ = (
        # Case-insensitive uniqueness for identical name+surname duplicates guard
        # (search remains the main dedup tool; constraint is a safety net).
        UniqueConstraint("nom", "prenom", "telephone", name="uq_patient_identity"),
    )


class MedicalProfile(Base):
    __tablename__ = "medical_profiles"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True
    )
    diabete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hypertension: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    maladie_cardiaque: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    grossesse: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    anticoagulants: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    asthme: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    epilepsie: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allergies: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    autre: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    patient: Mapped[Patient] = relationship(back_populates="medical")


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Stored file name (UUID + extension) under data/attachments.
    stored_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, index=True)


# --------------------------------------------------------------------------- #
# Agenda
# --------------------------------------------------------------------------- #


class Appointment(Base):
    """One row per scheduled appointment.

    Status workflow: a_venir -> arrive -> en_cours -> termine.
    `Absent` and cancellation are recorded via flags + events, not statuses.
    """

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Optional exact time; `time_note` holds free approximations like "vers 10h".
    time: Mapped[time | None] = mapped_column(Time, nullable=True)
    time_note: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    motif: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="a_venir", index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    absent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    patient: Mapped[Patient] = relationship(lazy="joined")
    events: Mapped[list["AppointmentEvent"]] = relationship(
        back_populates="appointment", cascade="all, delete-orphan", order_by="AppointmentEvent.id"
    )

    __table_args__ = (CheckConstraint("status IN ('a_venir','arrive','en_cours','termine')", name="ck_appt_status"),)


class AppointmentEvent(Base):
    """Append-only history: status changes, absence, cancellation, edits."""

    __tablename__ = "appointment_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)  # created/status/absent/cancel/edit
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    appointment: Mapped[Appointment] = relationship(back_populates="events")


# --------------------------------------------------------------------------- #
# Clinical
# --------------------------------------------------------------------------- #


class ClinicalNote(Base):
    """Structured clinical note (Motif / Diagnostic / Traitement / Remarques).

    Notes are editable for corrections but never deleted.
    """

    __tablename__ = "clinical_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    motif: Mapped[str] = mapped_column(Text, nullable=False, default="")
    diagnostic: Mapped[str] = mapped_column(Text, nullable=False, default="")
    traitement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    remarques: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class TreatmentCatalogItem(Base):
    __tablename__ = "treatment_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    default_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class PatientTreatment(Base):
    """A treatment applied to a patient. Price is a snapshot (catalog may change).

    Tooth is optional (FDI 11-48). With a tooth, the treatment appears in the
    odontogram context; without one it stays a general treatment record.
    """

    __tablename__ = "patient_treatments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    catalog_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("treatment_catalog.id", ondelete="SET NULL")
    )
    # Snapshot of the treatment name/price at entry time.
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tooth: Mapped[int | None] = mapped_column(Integer, nullable=True)  # FDI 11..48
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, index=True)

    __table_args__ = (
        CheckConstraint("tooth IS NULL OR (tooth BETWEEN 11 AND 48)", name="ck_treatment_tooth"),
        CheckConstraint("price >= 0", name="ck_treatment_price"),
    )


class ToothState(Base):
    """Odontogram state per tooth (FDI numbering). Upserted per patient/tooth."""

    __tablename__ = "tooth_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tooth: Mapped[int] = mapped_column(Integer, nullable=False)
    # sain / a_traiter / traite / absent
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="sain")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("patient_id", "tooth", name="uq_tooth_state_patient_tooth"),
        CheckConstraint("tooth BETWEEN 11 AND 48", name="ck_tooth_state_tooth"),
        CheckConstraint("state IN ('sain','a_traiter','traite','absent')", name="ck_tooth_state_value"),
    )


# --------------------------------------------------------------------------- #
# Finance
# --------------------------------------------------------------------------- #


class Payment(Base):
    """Append-only cash payments. Never deleted; corrections are new payments."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, index=True)

    __table_args__ = (CheckConstraint("amount > 0", name="ck_payment_amount_positive"),)


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #


class Document(Base):
    """Generated patient document with a content snapshot (printable later)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # ordonnance / certificat / attestation
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, index=True)

    __table_args__ = (CheckConstraint("doc_type IN ('ordonnance','certificat','attestation')", name="ck_document_type"),)


# --------------------------------------------------------------------------- #
# Backups
# --------------------------------------------------------------------------- #


class BackupRecord(Base):
    __tablename__ = "backup_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # auto / manual
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success / failed
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, index=True)


# --------------------------------------------------------------------------- #
# Laboratory (prostheses sent to external labs + supplier invoices)
# --------------------------------------------------------------------------- #


class Lab(Base):
    """External dental laboratory (supplier of prosthetic work)."""

    __tablename__ = "labs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (UniqueConstraint("name", name="uq_lab_name"),)


class LabOrder(Base):
    """Prosthetic work sent to a lab for a patient.

    Status workflow: envoye -> en_fabrication -> pret -> recu (+ annule).
    Financial records are never hard-deleted; cancellation is a status.
    """

    __tablename__ = "lab_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    lab_id: Mapped[int] = mapped_column(
        ForeignKey("labs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # couronne / bridge / prothese / gouttiere / autre
    work_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # FDI tooth numbers as entered, e.g. "26,27"
    teeth: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    shade: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="envoye", index=True)
    sent_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    received_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    patient: Mapped[Patient] = relationship(lazy="joined")
    lab: Mapped[Lab] = relationship(lazy="joined")

    __table_args__ = (
        CheckConstraint(
            "status IN ('envoye','en_fabrication','pret','recu','annule')",
            name="ck_lab_order_status",
        ),
        CheckConstraint("price >= 0", name="ck_lab_order_price"),
        CheckConstraint(
            "work_type IN ('couronne','bridge','prothese','gouttiere','autre')",
            name="ck_lab_order_work_type",
        ),
    )


class LabInvoice(Base):
    """Invoice received from a lab (monthly statement, per-case, ...)."""

    __tablename__ = "lab_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lab_id: Mapped[int] = mapped_column(
        ForeignKey("labs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    lab: Mapped[Lab] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("lab_id", "number", name="uq_lab_invoice_lab_number"),
        CheckConstraint("amount > 0", name="ck_lab_invoice_amount"),
    )


class LabInvoicePayment(Base):
    """Append-only cash payments toward a lab invoice."""

    __tablename__ = "lab_invoice_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("lab_invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, index=True)

    __table_args__ = (CheckConstraint("amount > 0", name="ck_lab_payment_amount_positive"),)


# --------------------------------------------------------------------------- #
# Stock / materials
# --------------------------------------------------------------------------- #


class StockItem(Base):
    """Clinic material with on-hand quantity and low-stock threshold."""

    __tablename__ = "stock_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # consommable / equipement / bureau / autre
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="unite")
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_stock_quantity_non_negative"),
        CheckConstraint("min_quantity >= 0", name="ck_stock_min_non_negative"),
        CheckConstraint(
            "category IN ('consommable','equipement','bureau','autre')",
            name="ck_stock_category",
        ),
        UniqueConstraint("name", name="uq_stock_item_name"),
    )


class StockMovement(Base):
    """Append-only ledger of every stock change. Ledger sums to on-hand stock."""

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("stock_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # signed quantity: + restock, - consumption, ± adjustment
    delta: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # initial / restock / consumption / adjustment / correction
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # loose business reference, e.g. ("patient_treatment", 42) for auto-deduction
    reference_type: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, index=True)

    __table_args__ = (
        CheckConstraint(
            "reason IN ('initial','restock','consumption','adjustment','correction')",
            name="ck_stock_movement_reason",
        ),
        CheckConstraint("delta != 0", name="ck_stock_movement_delta_nonzero"),
    )


class TreatmentConsumable(Base):
    """Link between a catalog treatment and a stock item auto-consumed on use."""

    __tablename__ = "treatment_consumables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    catalog_item_id: Mapped[int] = mapped_column(
        ForeignKey("treatment_catalog.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stock_item_id: Mapped[int] = mapped_column(
        ForeignKey("stock_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("catalog_item_id", "stock_item_id", name="uq_treatment_consumable"),
        CheckConstraint("quantity > 0", name="ck_treatment_consumable_quantity"),
    )
