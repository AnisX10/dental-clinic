"""Allow deciduous teeth (51..85) in treatment tooth check constraint.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-17
"""

from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_treatment_tooth", "patient_treatments", type_="check")
    op.create_check_constraint(
        "ck_treatment_tooth",
        "patient_treatments",
        "tooth IS NULL OR (tooth BETWEEN 11 AND 48) OR (tooth BETWEEN 51 AND 85)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_treatment_tooth", "patient_treatments", type_="check")
    op.create_check_constraint(
        "ck_treatment_tooth",
        "patient_treatments",
        "tooth IS NULL OR (tooth BETWEEN 11 AND 48)",
    )

