"""lab + stock modules: labs, lab orders/invoices, stock items/movements, consumable links

Revision ID: b3f8a2c91d47
Revises: ef676d97f0ce
Create Date: 2026-10-05 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = "b3f8a2c91d47"
down_revision = "ef676d97f0ce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Labs registry ------------------------------------------------------
    op.create_table(
        "labs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_lab_name"),
    )

    # --- Lab orders ---------------------------------------------------------
    op.create_table(
        "lab_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("lab_id", sa.Integer(), nullable=False),
        sa.Column("work_type", sa.String(length=20), nullable=False),
        sa.Column("teeth", sa.String(length=60), nullable=False),
        sa.Column("shade", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("sent_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("received_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('envoye','en_fabrication','pret','recu','annule')",
            name="ck_lab_order_status",
        ),
        sa.CheckConstraint("price >= 0", name="ck_lab_order_price"),
        sa.CheckConstraint(
            "work_type IN ('couronne','bridge','prothese','gouttiere','autre')",
            name="ck_lab_order_work_type",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lab_orders_patient_id"), "lab_orders", ["patient_id"], unique=False)
    op.create_index(op.f("ix_lab_orders_lab_id"), "lab_orders", ["lab_id"], unique=False)
    op.create_index(op.f("ix_lab_orders_status"), "lab_orders", ["status"], unique=False)

    # --- Lab invoices -------------------------------------------------------
    op.create_table(
        "lab_invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lab_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=60), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("issued_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_lab_invoice_amount"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lab_id", "number", name="uq_lab_invoice_lab_number"),
    )
    op.create_index(op.f("ix_lab_invoices_lab_id"), "lab_invoices", ["lab_id"], unique=False)
    # Case-insensitive invoice-number uniqueness per lab (service check + DB net).
    op.create_index(
        "uq_lab_invoice_number_ci",
        "lab_invoices",
        ["lab_id", sa.text("lower(number)")],
        unique=True,
    )

    # --- Lab invoice payments (append-only) ----------------------------------
    op.create_table(
        "lab_invoice_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_lab_payment_amount_positive"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invoice_id"], ["lab_invoices.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_lab_invoice_payments_invoice_id"), "lab_invoice_payments", ["invoice_id"], unique=False
    )
    op.create_index(
        op.f("ix_lab_invoice_payments_created_at"), "lab_invoice_payments", ["created_at"], unique=False
    )

    # --- Stock items ----------------------------------------------------------
    op.create_table(
        "stock_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("stock_quantity", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("min_quantity", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("stock_quantity >= 0", name="ck_stock_quantity_non_negative"),
        sa.CheckConstraint("min_quantity >= 0", name="ck_stock_min_non_negative"),
        sa.CheckConstraint(
            "category IN ('consommable','equipement','bureau','autre')",
            name="ck_stock_category",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_stock_item_name"),
    )
    op.create_index(op.f("ix_stock_items_category"), "stock_items", ["category"], unique=False)
    op.create_index(op.f("ix_stock_items_is_active"), "stock_items", ["is_active"], unique=False)

    # --- Stock movements (append-only ledger) ---------------------------------
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("delta", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=False),
        sa.Column("reference_type", sa.String(length=40), nullable=False),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "reason IN ('initial','restock','consumption','adjustment','correction')",
            name="ck_stock_movement_reason",
        ),
        sa.CheckConstraint("delta != 0", name="ck_stock_movement_delta_nonzero"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["item_id"], ["stock_items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stock_movements_item_id"), "stock_movements", ["item_id"], unique=False)
    op.create_index(
        op.f("ix_stock_movements_created_at"), "stock_movements", ["created_at"], unique=False
    )
    # Idempotent auto-deduction: at most one consumption row per (ref, item).
    # Manual consumptions have a NULL reference_id and are exempt (NULLs are
    # distinct in unique indexes).
    op.create_index(
        "uq_stock_movements_consumption_ref",
        "stock_movements",
        ["reference_type", "reference_id", "item_id"],
        unique=True,
        postgresql_where=sa.text("reason = 'consumption'"),
    )

    # --- Treatment -> consumable links ----------------------------------------
    op.create_table(
        "treatment_consumables",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("catalog_item_id", sa.Integer(), nullable=False),
        sa.Column("stock_item_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_treatment_consumable_quantity"),
        sa.ForeignKeyConstraint(["catalog_item_id"], ["treatment_catalog.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stock_item_id"], ["stock_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_item_id", "stock_item_id", name="uq_treatment_consumable"),
    )
    op.create_index(
        op.f("ix_treatment_consumables_catalog_item_id"),
        "treatment_consumables",
        ["catalog_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_treatment_consumables_stock_item_id"),
        "treatment_consumables",
        ["stock_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("treatment_consumables")
    op.drop_index("uq_stock_movements_consumption_ref", table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_created_at"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_item_id"), table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_index(op.f("ix_stock_items_is_active"), table_name="stock_items")
    op.drop_index(op.f("ix_stock_items_category"), table_name="stock_items")
    op.drop_table("stock_items")
    op.drop_index(op.f("ix_lab_invoice_payments_created_at"), table_name="lab_invoice_payments")
    op.drop_index(op.f("ix_lab_invoice_payments_invoice_id"), table_name="lab_invoice_payments")
    op.drop_table("lab_invoice_payments")
    op.drop_index("uq_lab_invoice_number_ci", table_name="lab_invoices")
    op.drop_index(op.f("ix_lab_invoices_lab_id"), table_name="lab_invoices")
    op.drop_table("lab_invoices")
    op.drop_index(op.f("ix_lab_orders_status"), table_name="lab_orders")
    op.drop_index(op.f("ix_lab_orders_lab_id"), table_name="lab_orders")
    op.drop_index(op.f("ix_lab_orders_patient_id"), table_name="lab_orders")
    op.drop_table("lab_orders")
    op.drop_table("labs")
