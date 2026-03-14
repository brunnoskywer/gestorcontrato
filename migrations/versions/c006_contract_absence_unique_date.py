"""Add unique constraint (contract_id, absence_date) on contract_absences.

Revision ID: c006_contract_absence_unique_date
Revises: c005_contract_absences
Create Date: 2026-03-13

"""
from alembic import op


revision = "c006_contract_absence_unique_date"
down_revision = "c005_contract_absences"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_contract_absence_date",
        "contract_absences",
        ["contract_id", "absence_date"],
    )


def downgrade():
    op.drop_constraint("uq_contract_absence_date", "contract_absences", type_="unique")
