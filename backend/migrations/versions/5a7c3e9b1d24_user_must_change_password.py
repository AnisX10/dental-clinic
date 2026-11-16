"""Force a password change on accounts created with a bootstrap password.

Revision ID: 5a7c3e9b1d24
Revises: 4c9d2e1f8a03
Create Date: 2026-11-16
"""

import sqlalchemy as sa
from alembic import op

revision = "5a7c3e9b1d24"
down_revision = "4c9d2e1f8a03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
