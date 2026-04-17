"""add company address for motoboy contract pdf

Revision ID: d010_company_address_for_contract_pdf
Revises: d009_financial_batch_scope_client_company
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d010_company_address_for_contract_pdf"
down_revision = "d009_financial_batch_scope_client_company"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("companies", sa.Column("address", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column("companies", "address")
