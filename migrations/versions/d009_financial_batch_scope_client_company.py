"""add client/company scope to financial batches

Revision ID: d009_financial_batch_scope_client_company
Revises: d008_motoboy_inactive_to_terminated
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d009_financial_batch_scope_client_company"
down_revision = "d008_motoboy_inactive_to_terminated"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("financial_batches", sa.Column("company_id", sa.Integer(), nullable=True))
    op.add_column("financial_batches", sa.Column("client_supplier_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_financial_batches_company_id",
        "financial_batches",
        "companies",
        ["company_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_financial_batches_client_supplier_id",
        "financial_batches",
        "suppliers",
        ["client_supplier_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_financial_batches_client_supplier_id", "financial_batches", type_="foreignkey")
    op.drop_constraint("fk_financial_batches_company_id", "financial_batches", type_="foreignkey")
    op.drop_column("financial_batches", "client_supplier_id")
    op.drop_column("financial_batches", "company_id")
