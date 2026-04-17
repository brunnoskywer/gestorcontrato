"""add allow_contract_generation to companies

Revision ID: d011_company_allow_contract_generation
Revises: d010_company_address_for_contract_pdf
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d011_company_allow_contract_generation"
down_revision = "d010_company_address_for_contract_pdf"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "companies",
        sa.Column(
            "allow_contract_generation",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade():
    op.drop_column("companies", "allow_contract_generation")
