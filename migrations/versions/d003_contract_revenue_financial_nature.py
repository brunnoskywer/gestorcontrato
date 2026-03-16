"""add revenue_financial_nature_id to contracts

Revision ID: d003_contract_revenue_nature
Revises: d002_financial_batches_and_entry_link
Create Date: 2026-03-16

"""

from alembic import op
import sqlalchemy as sa


revision = "d003_contract_revenue_nature"
down_revision = "d002_financial_batches_and_entry_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column(
            "revenue_financial_nature_id",
            sa.Integer(),
            sa.ForeignKey("financial_natures.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("contracts", "revenue_financial_nature_id")
