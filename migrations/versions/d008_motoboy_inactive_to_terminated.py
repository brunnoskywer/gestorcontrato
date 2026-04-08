"""Normaliza status legado inactive → terminated (motoboys)."""

from alembic import op
import sqlalchemy as sa

revision = "d008_motoboy_term"
down_revision = "d007_drop_unique_supplier_document"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE suppliers SET status = 'terminated' "
            "WHERE type = 'motoboy' AND status = 'inactive'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE suppliers SET status = 'inactive' "
            "WHERE type = 'motoboy' AND status = 'terminated'"
        )
    )
