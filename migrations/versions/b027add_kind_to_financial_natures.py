"""add kind to financial_natures

Revision ID: b027add_kind
Revises: a916c7a53579
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa


revision = "b027add_kind"
down_revision = "a916c7a53579"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "financial_natures",
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="payable"),
    )


def downgrade():
    op.drop_column("financial_natures", "kind")
