"""Adiciona created_at em contracts (data de criação do registro).

Revision ID: d020_contract_created_at
Revises: d019_enable_unaccent_extension
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "d020_contract_created_at"
down_revision = "d019_enable_unaccent_extension"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("contracts", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.execute(
        text(
            "UPDATE contracts SET created_at = start_date::timestamp "
            "WHERE created_at IS NULL"
        )
    )
    op.alter_column("contracts", "created_at", nullable=False)


def downgrade():
    op.drop_column("contracts", "created_at")
