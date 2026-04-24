"""financial entry attachments (single file per entry)

Revision ID: d017_financial_entry_attachments
Revises: d016_add_cep_to_company_and_supplier
Create Date: 2026-04-23
"""

import sqlalchemy as sa
from alembic import op


revision = "d017_financial_entry_attachments"
down_revision = "d016_add_cep_to_company_and_supplier"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "financial_entry_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("financial_entry_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_relpath", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["financial_entry_id"],
            ["financial_entries.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "financial_entry_id",
            name="uq_financial_entry_attachment_entry",
        ),
    )
    op.create_index(
        op.f("ix_financial_entry_attachments_financial_entry_id"),
        "financial_entry_attachments",
        ["financial_entry_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_financial_entry_attachments_financial_entry_id"),
        table_name="financial_entry_attachments",
    )
    op.drop_table("financial_entry_attachments")
