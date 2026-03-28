"""Diarista no motoboy; falta com diarista, substituto e lançamento a pagar."""

import sqlalchemy as sa
from alembic import op

revision = "d005_diarist_absence_payable"
down_revision = "d004_motoboy_advance_value"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suppliers",
        sa.Column("is_diarist", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "contract_absences",
        sa.Column("diarist_supplier_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "contract_absences",
        sa.Column("substitute_supplier_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "contract_absences",
        sa.Column("financial_nature_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "contract_absences",
        sa.Column("payable_entry_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_contract_absences_diarist_supplier",
        "contract_absences",
        "suppliers",
        ["diarist_supplier_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_contract_absences_substitute_supplier",
        "contract_absences",
        "suppliers",
        ["substitute_supplier_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_contract_absences_financial_nature",
        "contract_absences",
        "financial_natures",
        ["financial_nature_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_contract_absences_payable_entry",
        "contract_absences",
        "financial_entries",
        ["payable_entry_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_contract_absences_payable_entry", "contract_absences", type_="foreignkey")
    op.drop_constraint("fk_contract_absences_financial_nature", "contract_absences", type_="foreignkey")
    op.drop_constraint("fk_contract_absences_substitute_supplier", "contract_absences", type_="foreignkey")
    op.drop_constraint("fk_contract_absences_diarist_supplier", "contract_absences", type_="foreignkey")
    op.drop_column("contract_absences", "payable_entry_id")
    op.drop_column("contract_absences", "financial_nature_id")
    op.drop_column("contract_absences", "substitute_supplier_id")
    op.drop_column("contract_absences", "diarist_supplier_id")
    op.drop_column("suppliers", "is_diarist")
