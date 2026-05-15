"""Fardamentos: cadastro, movimentações e estoque.

Revision ID: d021_uniforms
Revises: d020_contract_created_at
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa


revision = "d021_uniforms"
down_revision = "d020_contract_created_at"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "uniforms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("size", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("name", "size", name="uq_uniform_name_size"),
    )
    op.create_table(
        "uniform_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uniform_id", sa.Integer(), sa.ForeignKey("uniforms.id"), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("subtype", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("motoboy_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column(
            "financial_entry_id",
            sa.Integer(),
            sa.ForeignKey("financial_entries.id"),
            nullable=True,
        ),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("uniform_movements")
    op.drop_table("uniforms")
