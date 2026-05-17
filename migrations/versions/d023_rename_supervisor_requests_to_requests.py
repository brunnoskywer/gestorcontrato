"""Renomeia supervisor_requests para requests.

Revision ID: d023_requests_table
Revises: d022_supervisor_requests
Create Date: 2026-05-16
"""

from alembic import op


revision = "d023_requests_table"
down_revision = "d022_supervisor_requests"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("supervisor_requests", "requests")
    op.execute(
        "ALTER INDEX IF EXISTS ix_supervisor_requests_supervisor_id "
        "RENAME TO ix_requests_supervisor_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_supervisor_requests_created_at "
        "RENAME TO ix_requests_created_at"
    )


def downgrade():
    op.execute(
        "ALTER INDEX IF EXISTS ix_requests_created_at "
        "RENAME TO ix_supervisor_requests_created_at"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_requests_supervisor_id "
        "RENAME TO ix_supervisor_requests_supervisor_id"
    )
    op.rename_table("requests", "supervisor_requests")
