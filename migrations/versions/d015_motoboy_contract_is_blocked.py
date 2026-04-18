"""motoboy contract blocked flag (exclui processamentos financeiros)

Revision ID: d015_motoboy_contract_is_blocked
Revises: d014_contract_attachments
Create Date: 2026-04-17
"""

import sqlalchemy as sa
from alembic import op


revision = "d015_motoboy_contract_is_blocked"
down_revision = "d014_contract_attachments"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "contracts",
        sa.Column(
            "is_blocked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.alter_column("contracts", "is_blocked", server_default=None)


def downgrade():
    op.drop_column("contracts", "is_blocked")
