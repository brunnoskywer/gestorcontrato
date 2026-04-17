"""rename consider_for_discount to does_not_consider_residual on financial_natures

Revision ID: d013_rename_consider_discount_nature
Revises: d012_address_client_revenue_residual_snapshot
Create Date: 2026-04-17
"""

from alembic import op


revision = "d013_rename_consider_discount_nature"
down_revision = "d012_address_client_revenue_residual_snapshot"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        'ALTER TABLE financial_natures RENAME COLUMN consider_for_discount TO does_not_consider_residual'
    )


def downgrade():
    op.execute(
        'ALTER TABLE financial_natures RENAME COLUMN does_not_consider_residual TO consider_for_discount'
    )
