"""Habilita extensão unaccent no PostgreSQL para buscas sem acento.

Revision ID: d019_enable_unaccent_extension
Revises: d018_uppercase_registry_names
Create Date: 2026-05-04
"""

from alembic import op


revision = "d019_enable_unaccent_extension"
down_revision = "d018_uppercase_registry_names"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade():
    op.execute("DROP EXTENSION IF EXISTS unaccent")
