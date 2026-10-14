"""DSP & CNAS register (CNAS AS 2), devis/plans, sterilization cycles.

Revision ID: e5f6a7b8c9d0
Revises: a1b2c3d4e5f6
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Clinic settings: DSP defaults (owner-editable) -----------------------
    op.add_column("clinic_settings", sa.Column("dsp_default_caisse", sa.String(length=10), nullable=False, server_default="CNAS"))
    op.add_column("clinic_settings", sa.Column("dsp_default_code", sa.String(length=20), nullable=False, server_default=""))
    op.add_column("clinic_settings", sa.Column("dsp_default_coefficient", sa.Numeric(precision=8, scale=2), nullable=False, server_default="0"))
    op.add_column("clinic_settings", sa.Column("dsp_default_fee", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"))

    # --- DSP registry (Feuille de soins dentaires AS 2) ------------------------
    op.create_table(
        "dsp_registry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("caisse", sa.String(length=10), nullable=False, index=True),
        sa.Column("insured_nin", sa.String(length=18), nullable=False, server_default=""),
        sa.Column("affiliation_no", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("beneficiary_relation", sa.String(length=20), nullable=False, server_default="assure"),
        sa.Column("first_act_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("caisse IN ('CNAS','CASNOS')", name="ck_dsp_caisse"),
        sa.CheckConstraint(
            "beneficiary_relation IN ('assure','conjoint','enfant','autre')",
            name="ck_dsp_beneficiary",
        ),
    )
    # NOTE: sa.Column(..., index=True) inside create_table already creates
    # ix_dsp_registry_caisse / ix_dsp_registry_patient_id — no explicit call.

    # --- DSP acts (one row per treated tooth per act) --------------------------
    op.create_table(
        "dsp_acts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dsp_id", sa.Integer(), sa.ForeignKey("dsp_registry.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("act_date", sa.Date(), nullable=False),
        sa.Column("tooth", sa.Integer(), nullable=True),
        sa.Column("act_label", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("act_code", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("coefficient", sa.Numeric(precision=8, scale=2), nullable=False, server_default="0"),
        sa.Column("fee", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("tooth IS NULL OR ((tooth BETWEEN 11 AND 48) OR (tooth BETWEEN 51 AND 85 AND tooth % 10 BETWEEN 1 AND 5))", name="ck_dsp_act_tooth"),
        sa.CheckConstraint("fee >= 0", name="ck_dsp_act_fee"),
    )


    # --- Devis (treatment plan quotes) -----------------------------------------
    op.create_table(
        "devis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("status", sa.String(length=20), nullable=False, index=True),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft','sent','accepted','rejected','expired','cancelled')",
            name="ck_devis_status",
        ),
    )


    op.create_table(
        "devis_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("devis_id", sa.Integer(), sa.ForeignKey("devis.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("catalog_item_id", sa.Integer(), sa.ForeignKey("treatment_catalog.id", ondelete="SET NULL"), nullable=True),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("tooth", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_devis_item_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_devis_item_price"),
    )


    # --- Sterilization cycles ---------------------------------------------------
    op.create_table(
        "sterilization_cycles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_no", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="in_progress", index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("autoclave_name", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("program", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("status IN ('in_progress','done','failed')", name="ck_sterilization_status"),
        sa.UniqueConstraint("cycle_no", name="uq_sterilization_cycle_no"),
    )

    op.create_table(
        "sterilization_cycle_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("sterilization_cycles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("item_name", sa.String(length=160), nullable=False),
        sa.Column("stock_item_id", sa.Integer(), sa.ForeignKey("stock_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("instrument_status", sa.String(length=20), nullable=False, server_default="sterile"),
        sa.CheckConstraint("quantity > 0", name="ck_sterilization_item_quantity"),
        sa.CheckConstraint("instrument_status IN ('sterile','failed')", name="ck_sterilization_item_status"),
    )
    # ix_sterilization_cycle_items_cycle_id created via index=True above.


def downgrade() -> None:
    op.drop_table("sterilization_cycle_items")
    op.drop_table("sterilization_cycles")
    op.drop_table("devis_items")
    op.drop_table("devis")
    op.drop_table("dsp_acts")
    op.drop_table("dsp_registry")
    op.drop_column("clinic_settings", "dsp_default_fee")
    op.drop_column("clinic_settings", "dsp_default_coefficient")
    op.drop_column("clinic_settings", "dsp_default_code")
    op.drop_column("clinic_settings", "dsp_default_caisse")
