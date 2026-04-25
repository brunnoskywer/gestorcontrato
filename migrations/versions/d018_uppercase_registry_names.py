"""Normaliza nomes de empresa e fornecedor (cliente/fornecedor/motoboy) para maiúsculas.

Revision ID: d018_uppercase_registry_names
Revises: d017_financial_entry_attachments
Create Date: 2026-04-24
"""

from alembic import op
from sqlalchemy import text


revision = "d018_uppercase_registry_names"
down_revision = "d017_financial_entry_attachments"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Empresas
    conn.execute(
        text(
            """
            UPDATE companies SET
              legal_name = UPPER(TRIM(legal_name)),
              trade_name = CASE
                WHEN trade_name IS NULL THEN NULL
                WHEN TRIM(trade_name) = '' THEN NULL
                ELSE UPPER(TRIM(trade_name))
              END,
              partner_name = CASE
                WHEN partner_name IS NULL THEN NULL
                WHEN TRIM(partner_name) = '' THEN NULL
                ELSE UPPER(TRIM(partner_name))
              END
            """
        )
    )
    # Fornecedores / clientes / motoboys (tabela suppliers)
    conn.execute(
        text(
            """
            UPDATE suppliers SET
              name = UPPER(TRIM(name)),
              legal_name = CASE
                WHEN legal_name IS NULL THEN NULL
                WHEN TRIM(legal_name) = '' THEN NULL
                ELSE UPPER(TRIM(legal_name))
              END,
              trade_name = CASE
                WHEN trade_name IS NULL THEN NULL
                WHEN TRIM(trade_name) = '' THEN NULL
                ELSE UPPER(TRIM(trade_name))
              END,
              contact_name = CASE
                WHEN contact_name IS NULL THEN NULL
                WHEN TRIM(contact_name) = '' THEN NULL
                ELSE UPPER(TRIM(contact_name))
              END,
              reference_contact = CASE
                WHEN reference_contact IS NULL THEN NULL
                WHEN TRIM(reference_contact) = '' THEN NULL
                ELSE UPPER(TRIM(reference_contact))
              END
            """
        )
    )


def downgrade():
    # Irreversível: perda de capitalização original.
    pass
