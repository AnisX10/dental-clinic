"""odontogram conditions: per-surface carie/obturation, bridge, deciduous teeth

Revision ID: c4d1e7a90f21
Revises: b3f8a2c91d47
Create Date: 2026-10-07 10:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = "c4d1e7a90f21"
down_revision = "b3f8a2c91d47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Surface marks: '' = whole-tooth condition, otherwise one of the five faces.
    op.add_column(
        "tooth_states",
        sa.Column("surface", sa.String(length=12), nullable=False, server_default=""),
    )

    # Data migration before tightening the value domain:
    # - 'traite' becomes 'obturation' (closest whole-tooth equivalent)
    # - 'sain' rows are dropped (a healthy tooth simply has no row)
    op.execute("UPDATE tooth_states SET state = 'obturation' WHERE state = 'traite'")
    op.execute("DELETE FROM tooth_states WHERE state = 'sain'")

    op.drop_constraint("uq_tooth_state_patient_tooth", "tooth_states", type_="unique")
    op.drop_constraint("ck_tooth_state_value", "tooth_states", type_="check")
    op.drop_constraint("ck_tooth_state_tooth", "tooth_states", type_="check")

    op.create_unique_constraint(
        "uq_tooth_state_patient_tooth_surface", "tooth_states", ["patient_id", "tooth", "surface"]
    )
    op.create_check_constraint(
        "ck_tooth_state_value",
        "tooth_states",
        "state IN ('a_traiter','carie','obturation','couronne','bridge','absent')",
    )
    op.create_check_constraint(
        "ck_tooth_state_tooth",
        "tooth_states",
        "(tooth BETWEEN 11 AND 48) OR (tooth BETWEEN 51 AND 85 AND tooth % 10 BETWEEN 1 AND 5)",
    )
    op.create_check_constraint(
        "ck_tooth_state_surface",
        "tooth_states",
        "surface IN ('','occlusale','mesiale','distale','vestibulaire','linguale')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tooth_state_surface", "tooth_states", type_="check")
    op.drop_constraint("ck_tooth_state_tooth", "tooth_states", type_="check")
    op.drop_constraint("ck_tooth_state_value", "tooth_states", type_="check")
    op.drop_constraint("uq_tooth_state_patient_tooth_surface", "tooth_states", type_="unique")

    # Surface marks and the new conditions have no direct equivalent in the
    # old schema: fold them onto the closest legacy state.
    op.execute("DELETE FROM tooth_states WHERE surface <> ''")
    op.execute(
        "UPDATE tooth_states SET state = 'traite' "
        "WHERE state IN ('obturation','couronne','bridge')"
    )
    op.execute("UPDATE tooth_states SET state = 'a_traiter' WHERE state = 'carie'")

    op.create_unique_constraint(
        "uq_tooth_state_patient_tooth", "tooth_states", ["patient_id", "tooth"]
    )
    op.create_check_constraint(
        "ck_tooth_state_value", "tooth_states", "state IN ('sain','a_traiter','traite','absent')"
    )
    op.create_check_constraint("ck_tooth_state_tooth", "tooth_states", "tooth BETWEEN 11 AND 48")

    op.drop_column("tooth_states", "surface")
