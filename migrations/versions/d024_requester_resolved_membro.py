"""Solicitante, status resolvido e campos de rejeição/resolução.

Revision ID: d024_requester_resolved
Revises: d023_requests_table
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa


revision = "d024_requester_resolved"
down_revision = "d023_requests_table"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("requests", "supervisor_id", new_column_name="requester_id")

    op.execute(
        "ALTER INDEX IF EXISTS ix_requests_supervisor_id "
        "RENAME TO ix_requests_requester_id"
    )

    op.add_column("requests", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("requests", sa.Column("resolved_at", sa.DateTime(), nullable=True))
    op.add_column(
        "requests",
        sa.Column("resolved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("requests", sa.Column("rejected_at", sa.DateTime(), nullable=True))
    op.add_column(
        "requests",
        sa.Column("rejected_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    op.execute("UPDATE users SET role = 'solicitante' WHERE role = 'supervisor'")
    op.execute("UPDATE requests SET status = 'resolved' WHERE status = 'approved'")


def downgrade():
    op.execute("UPDATE requests SET status = 'approved' WHERE status = 'resolved'")
    op.execute("UPDATE users SET role = 'supervisor' WHERE role = 'solicitante'")

    op.drop_column("requests", "rejected_by_id")
    op.drop_column("requests", "rejected_at")
    op.drop_column("requests", "resolved_by_id")
    op.drop_column("requests", "resolved_at")
    op.drop_column("requests", "rejection_reason")

    op.execute(
        "ALTER INDEX IF EXISTS ix_requests_requester_id "
        "RENAME TO ix_requests_supervisor_id"
    )
    op.alter_column("requests", "requester_id", new_column_name="supervisor_id")
