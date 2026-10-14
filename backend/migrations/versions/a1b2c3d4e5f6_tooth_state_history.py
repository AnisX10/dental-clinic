"""Add tooth_state_history audit table.

Revision ID: a1b2c3d4e5f6
Revises: d7e2f3a41b60
Create Date: 2026-10-10
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "d7e2f3a41b60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tooth_state_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tooth", sa.Integer(), nullable=False),
        sa.Column("surface", sa.String(length=12), nullable=False, server_default=""),
        sa.Column("condition", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False, server_default="set"),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.CheckConstraint("action IN ('set','clear')", name="ck_tooth_history_action"),
    )
    op.create_index("ix_tooth_history_patient_tooth", "tooth_state_history", ["patient_id", "tooth"])


def downgrade() -> None:
    op.drop_index("ix_tooth_history_patient_tooth", table_name="tooth_state_history")
    op.drop_table("tooth_state_history")
