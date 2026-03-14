"""Drop old clients, motoboys, client_contracts, motoboy_contracts tables.

Revision ID: c004_drop_old_tables
Revises: c003_data_migrate
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa


revision = "c004_drop_old_tables"
down_revision = "c003_data_migrate"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("motoboy_contracts")
    op.drop_table("client_contracts")
    op.drop_table("clients")
    op.drop_table("motoboys")


def downgrade():
    # Recreate tables (minimal structure for rollback; data is not restored)
    op.create_table(
        "motoboys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("cpf", sa.String(20), nullable=False),
        sa.Column("cnpj", sa.String(20), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("reference_contact", sa.String(255), nullable=True),
        sa.Column("bike_plate", sa.String(20), nullable=True),
        sa.Column("bank_account_pix", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("trade_name", sa.String(255), nullable=True),
        sa.Column("cnpj", sa.String(20), nullable=False),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("billing_company_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["billing_company_id"], ["companies.id"]),
    )
    op.create_table(
        "client_contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("contract_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("motoboy_quantity", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
    )
    op.create_table(
        "motoboy_contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("motoboy_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("service_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("bonus_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("missing_value", sa.Numeric(10, 2), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["motoboy_id"], ["motoboys.id"]),
    )
