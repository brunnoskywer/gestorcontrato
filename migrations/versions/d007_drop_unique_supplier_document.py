"""Permite documentos duplicados em suppliers.document."""

import sqlalchemy as sa
from alembic import op

revision = "d007_drop_unique_supplier_document"
down_revision = "d006_drop_diarist_supplier_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Remove qualquer UNIQUE constraint que cubra apenas a coluna document.
    for uc in inspector.get_unique_constraints("suppliers"):
        cols = uc.get("column_names") or []
        name = uc.get("name")
        if name and cols == ["document"]:
            op.drop_constraint(name, "suppliers", type_="unique")

    # Em alguns bancos a unicidade pode estar como índice único.
    for idx in inspector.get_indexes("suppliers"):
        cols = idx.get("column_names") or []
        name = idx.get("name")
        if name and idx.get("unique") and cols == ["document"]:
            op.drop_index(name, table_name="suppliers")


def downgrade() -> None:
    op.create_unique_constraint("uq_suppliers_document", "suppliers", ["document"])
