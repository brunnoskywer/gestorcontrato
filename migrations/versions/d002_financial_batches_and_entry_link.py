"""add financial_batches and link from entries

Revision ID: d002_financial_batches_and_entry_link
Revises: d001_add_extra_fields_and_roles
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa


revision = "d002_financial_batches_and_entry_link"
down_revision = "d001_add_extra_fields_and_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_type", sa.String(length=20), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("financial_nature_id", sa.Integer(), sa.ForeignKey("financial_natures.id"), nullable=False),
        sa.Column("charge_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "financial_entries",
        sa.Column("financial_batch_id", sa.Integer(), sa.ForeignKey("financial_batches.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("financial_entries", "financial_batch_id")
    op.drop_table("financial_batches")

