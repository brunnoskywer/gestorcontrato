"""Add contract_absences table for motoboy contract absences.

Revision ID: c005_contract_absences
Revises: c004_drop_old_tables
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa


revision = "c005_contract_absences"
down_revision = "c004_drop_old_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contract_absences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contracts.id"), nullable=False),
        sa.Column("absence_date", sa.Date(), nullable=False),
        sa.Column("justification", sa.String(500), nullable=False),
    )


def downgrade():
    op.drop_table("contract_absences")
