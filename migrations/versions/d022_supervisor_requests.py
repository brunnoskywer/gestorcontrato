"""Solicitações de supervisores.

Revision ID: d022_supervisor_requests
Revises: d021_uniforms
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa


revision = "d022_supervisor_requests"
down_revision = "d021_uniforms"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "supervisor_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_supervisor_requests_supervisor_id",
        "supervisor_requests",
        ["supervisor_id"],
    )
    op.create_index(
        "ix_supervisor_requests_created_at",
        "supervisor_requests",
        ["created_at"],
    )


def downgrade():
    op.drop_index("ix_supervisor_requests_created_at", table_name="supervisor_requests")
    op.drop_index("ix_supervisor_requests_supervisor_id", table_name="supervisor_requests")
    op.drop_table("supervisor_requests")
