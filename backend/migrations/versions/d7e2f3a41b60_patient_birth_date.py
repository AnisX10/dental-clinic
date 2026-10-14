"""Add optional patient birth date (date_naissance).

Revision ID: d7e2f3a41b60
Revises: c4d1e7a90f21
Create Date: 2026-10-10
"""

import sqlalchemy as sa
from alembic import op

revision = "d7e2f3a41b60"
down_revision = "c4d1e7a90f21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("date_naissance", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "date_naissance")
