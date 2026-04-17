"""address parts, client contract extras, nature discount flag, residual snapshot

Revision ID: d012_address_client_revenue_residual_snapshot
Revises: d011_company_allow_contract_generation
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa


revision = "d012_address_client_revenue_residual_snapshot"
down_revision = "d011_company_allow_contract_generation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("suppliers", sa.Column("street", sa.String(length=255), nullable=True))
    op.add_column("suppliers", sa.Column("neighborhood", sa.String(length=120), nullable=True))
    op.add_column("suppliers", sa.Column("city", sa.String(length=120), nullable=True))
    op.add_column("suppliers", sa.Column("state", sa.String(length=2), nullable=True))

    op.add_column("companies", sa.Column("street", sa.String(length=255), nullable=True))
    op.add_column("companies", sa.Column("neighborhood", sa.String(length=120), nullable=True))
    op.add_column("companies", sa.Column("city", sa.String(length=120), nullable=True))
    op.add_column("companies", sa.Column("state", sa.String(length=2), nullable=True))

    op.add_column(
        "contracts",
        sa.Column("client_driver_unit_value", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column("contracts", sa.Column("client_driver_quantity", sa.Integer(), nullable=True))
    op.add_column(
        "contracts",
        sa.Column("client_other_unit_value", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column("contracts", sa.Column("client_other_quantity", sa.Integer(), nullable=True))
    op.add_column(
        "contracts",
        sa.Column("client_absence_reimburse_unit_value", sa.Numeric(precision=10, scale=2), nullable=True),
    )

    op.add_column(
        "financial_natures",
        sa.Column(
            "consider_for_discount",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column("financial_entries", sa.Column("processing_snapshot", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("financial_entries", "processing_snapshot")
    op.drop_column("financial_natures", "consider_for_discount")
    op.drop_column("contracts", "client_absence_reimburse_unit_value")
    op.drop_column("contracts", "client_other_quantity")
    op.drop_column("contracts", "client_other_unit_value")
    op.drop_column("contracts", "client_driver_quantity")
    op.drop_column("contracts", "client_driver_unit_value")
    op.drop_column("companies", "state")
    op.drop_column("companies", "city")
    op.drop_column("companies", "neighborhood")
    op.drop_column("companies", "street")
    op.drop_column("suppliers", "state")
    op.drop_column("suppliers", "city")
    op.drop_column("suppliers", "neighborhood")
    op.drop_column("suppliers", "street")
