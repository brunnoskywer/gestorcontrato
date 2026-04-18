"""contract_attachments table for motoboy/client contract files

Revision ID: d014_contract_attachments
Revises: d013_rename_consider_discount_nature
Create Date: 2026-04-17
"""

import sqlalchemy as sa
from alembic import op


revision = "d014_contract_attachments"
down_revision = "d013_rename_consider_discount_nature"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contract_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_relpath", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "contract_id",
            "kind",
            name="uq_contract_attachment_contract_kind",
        ),
    )
    op.create_index(
        "ix_contract_attachments_contract_id",
        "contract_attachments",
        ["contract_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_contract_attachments_contract_id", table_name="contract_attachments")
    op.drop_table("contract_attachments")
