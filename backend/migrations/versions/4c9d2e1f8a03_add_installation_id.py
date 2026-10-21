"""Installation ID on clinic_settings: binds a license to one database.

Revision ID: 4c9d2e1f8a03
Revises: f6a7b8c9d0e1
Create Date: 2026-10-21
"""

import sqlalchemy as sa
from alembic import op

revision = "4c9d2e1f8a03"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clinic_settings",
        sa.Column("installation_id", sa.String(64), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("clinic_settings", "installation_id")
