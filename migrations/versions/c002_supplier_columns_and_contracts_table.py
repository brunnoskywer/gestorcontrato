"""Add supplier extra columns and create contracts table.

Revision ID: c002_supplier_contracts
Revises: c001_add_suppliers
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa


revision = "c002_supplier_contracts"
down_revision = "c001_add_suppliers"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("suppliers", sa.Column("legal_name", sa.String(length=255), nullable=True))
    op.add_column("suppliers", sa.Column("trade_name", sa.String(length=255), nullable=True))
    op.add_column("suppliers", sa.Column("address", sa.String(length=255), nullable=True))
    op.add_column("suppliers", sa.Column("contact_name", sa.String(length=255), nullable=True))
    op.add_column("suppliers", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("suppliers", sa.Column("billing_company_id", sa.Integer(), nullable=True))
    op.add_column("suppliers", sa.Column("reference_contact", sa.String(length=255), nullable=True))
    op.add_column("suppliers", sa.Column("bike_plate", sa.String(length=20), nullable=True))
    op.add_column("suppliers", sa.Column("bank_account_pix", sa.String(length=120), nullable=True))
    op.add_column("suppliers", sa.Column("document_secondary", sa.String(length=20), nullable=True))
    op.create_foreign_key(
        "fk_suppliers_billing_company",
        "suppliers",
        "companies",
        ["billing_company_id"],
        ["id"],
    )

    op.create_table(
        "contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("contract_type", sa.String(length=20), nullable=False),
        sa.Column("other_supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("service_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("bonus_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("missing_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("contract_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("motoboy_quantity", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_table("contracts")
    op.drop_constraint("fk_suppliers_billing_company", "suppliers", type_="foreignkey")
    op.drop_column("suppliers", "document_secondary")
    op.drop_column("suppliers", "bank_account_pix")
    op.drop_column("suppliers", "bike_plate")
    op.drop_column("suppliers", "reference_contact")
    op.drop_column("suppliers", "billing_company_id")
    op.drop_column("suppliers", "email")
    op.drop_column("suppliers", "contact_name")
    op.drop_column("suppliers", "address")
    op.drop_column("suppliers", "trade_name")
    op.drop_column("suppliers", "legal_name")
