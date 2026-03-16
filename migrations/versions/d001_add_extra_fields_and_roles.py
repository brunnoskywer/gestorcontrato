"""add extra fields for suppliers, accounts, absences and user roles

Revision ID: d001_add_extra_fields_and_roles
Revises: c006_contract_absence_unique_date
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa


revision = "d001_add_extra_fields_and_roles"
down_revision = "c006_contract_absence_unique_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Supplier: notes (clients), status/contact_phone (motoboys)
    op.add_column("suppliers", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("suppliers", sa.Column("status", sa.String(length=20), nullable=False, server_default="active"))
    op.add_column("suppliers", sa.Column("contact_phone", sa.String(length=50), nullable=True))
    # Account: bank fields
    op.add_column("accounts", sa.Column("bank_name", sa.String(length=120), nullable=True))
    op.add_column("accounts", sa.Column("agency", sa.String(length=50), nullable=True))
    op.add_column("accounts", sa.Column("account_number", sa.String(length=50), nullable=True))
    op.add_column("accounts", sa.Column("pix_key", sa.String(length=255), nullable=True))
    # ContractAbsence: substitute fields
    op.add_column("contract_absences", sa.Column("substitute_name", sa.String(length=255), nullable=True))
    op.add_column("contract_absences", sa.Column("substitute_document", sa.String(length=50), nullable=True))
    op.add_column("contract_absences", sa.Column("substitute_pix", sa.String(length=255), nullable=True))
    op.add_column("contract_absences", sa.Column("substitute_amount", sa.Numeric(10, 2), nullable=True))
    # User: role
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="admin"),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
    op.drop_column("contract_absences", "substitute_amount")
    op.drop_column("contract_absences", "substitute_pix")
    op.drop_column("contract_absences", "substitute_document")
    op.drop_column("contract_absences", "substitute_name")
    op.drop_column("accounts", "pix_key")
    op.drop_column("accounts", "account_number")
    op.drop_column("accounts", "agency")
    op.drop_column("accounts", "bank_name")
    op.drop_column("suppliers", "contact_phone")
    op.drop_column("suppliers", "status")
    op.drop_column("suppliers", "notes")

