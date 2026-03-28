"""Unifica diarista/substituto: um único substitute_supplier_id."""

import sqlalchemy as sa
from alembic import op

revision = "d006_drop_diarist_supplier_id"
down_revision = "d005_diarist_absence_payable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE contract_absences SET substitute_supplier_id = diarist_supplier_id "
            "WHERE substitute_supplier_id IS NULL AND diarist_supplier_id IS NOT NULL"
        )
    )
    op.drop_constraint("fk_contract_absences_diarist_supplier", "contract_absences", type_="foreignkey")
    op.drop_column("contract_absences", "diarist_supplier_id")


def downgrade() -> None:
    op.add_column(
        "contract_absences",
        sa.Column("diarist_supplier_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_contract_absences_diarist_supplier",
        "contract_absences",
        "suppliers",
        ["diarist_supplier_id"],
        ["id"],
    )
    op.execute(
        sa.text(
            "UPDATE contract_absences SET diarist_supplier_id = substitute_supplier_id "
            "WHERE substitute_supplier_id IS NOT NULL"
        )
    )
