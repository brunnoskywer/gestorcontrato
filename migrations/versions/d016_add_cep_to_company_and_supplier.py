"""add cep to company and supplier

Revision ID: d016_add_cep_to_company_and_supplier
Revises: d015_motoboy_contract_is_blocked
Create Date: 2026-04-23
"""

import sqlalchemy as sa
from alembic import op


revision = "d016_add_cep_to_company_and_supplier"
down_revision = "d015_motoboy_contract_is_blocked"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("companies", sa.Column("cep", sa.String(length=9), nullable=True))
    op.add_column("suppliers", sa.Column("cep", sa.String(length=9), nullable=True))


def downgrade():
    op.drop_column("suppliers", "cep")
    op.drop_column("companies", "cep")
