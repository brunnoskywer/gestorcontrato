"""add advance_value to contracts (motoboy)

Revision ID: d004_motoboy_advance_value
Revises: d003_contract_revenue_nature
Create Date: 2026-03-17

"""

from alembic import op
import sqlalchemy as sa


revision = "d004_motoboy_advance_value"
down_revision = "d003_contract_revenue_nature"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("advance_value", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contracts", "advance_value")

