"""add suppliers and link to financial_entries

Revision ID: c001_add_suppliers
Revises: b027add_kind
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa


revision = "c001_add_suppliers"
down_revision = "b027add_kind"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("document", sa.String(length=20), nullable=True, unique=True),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "financial_entries",
        sa.Column("supplier_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        None,
        "financial_entries",
        "suppliers",
        ["supplier_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(None, "financial_entries", type_="foreignkey")
    op.drop_column("financial_entries", "supplier_id")
    op.drop_table("suppliers")

