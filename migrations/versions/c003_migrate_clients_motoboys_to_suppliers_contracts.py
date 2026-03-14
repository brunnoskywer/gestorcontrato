"""Migrate data from clients/motoboys to suppliers and contracts.

Revision ID: c003_data_migrate
Revises: c002_supplier_contracts
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "c003_data_migrate"
down_revision = "c002_supplier_contracts"
branch_labels = None
depends_on = None


def _last_insert_id(conn):
    if conn.dialect.name == "sqlite":
        return conn.execute(text("SELECT last_insert_rowid()")).scalar()
    return None


def upgrade():
    conn = op.get_bind()
    client_id_to_supplier = {}
    motoboy_id_to_supplier = {}

    # Copy clients -> suppliers
    if conn.dialect.name == "sqlite":
        r = conn.execute(text("SELECT id, legal_name, trade_name, cnpj, address, contact_name, email, billing_company_id, created_at FROM clients"))
        rows = r.fetchall()
        for row in rows:
            (old_id, legal_name, trade_name, cnpj, address, contact_name, email, billing_company_id, created_at) = row
            conn.execute(
                text("""
                    INSERT INTO suppliers (name, document, type, is_active, created_at, legal_name, trade_name, address, contact_name, email, billing_company_id)
                    VALUES (:name, :doc, 'client', 1, :created_at, :legal_name, :trade_name, :address, :contact_name, :email, :billing_company_id)
                """),
                {
                    "name": legal_name or "",
                    "doc": cnpj,
                    "created_at": created_at,
                    "legal_name": legal_name,
                    "trade_name": trade_name,
                    "address": address,
                    "contact_name": contact_name,
                    "email": email,
                    "billing_company_id": billing_company_id,
                },
            )
            new_id = _last_insert_id(conn)
            client_id_to_supplier[old_id] = new_id
    else:
        r = conn.execute(text("SELECT id, legal_name, trade_name, cnpj, address, contact_name, email, billing_company_id, created_at FROM clients"))
        rows = r.fetchall()
        for row in rows:
            (old_id, legal_name, trade_name, cnpj, address, contact_name, email, billing_company_id, created_at) = row
            r2 = conn.execute(
                text("""
                    INSERT INTO suppliers (name, document, type, is_active, created_at, legal_name, trade_name, address, contact_name, email, billing_company_id)
                    VALUES (:name, :doc, 'client', true, :created_at, :legal_name, :trade_name, :address, :contact_name, :email, :billing_company_id)
                    RETURNING id
                """),
                {
                    "name": legal_name or "",
                    "doc": cnpj,
                    "created_at": created_at,
                    "legal_name": legal_name,
                    "trade_name": trade_name,
                    "address": address,
                    "contact_name": contact_name,
                    "email": email,
                    "billing_company_id": billing_company_id,
                },
            )
            new_id = r2.scalar()
            client_id_to_supplier[old_id] = new_id

    # Copy motoboys -> suppliers
    if conn.dialect.name == "sqlite":
        r = conn.execute(text("SELECT id, full_name, cpf, cnpj, address, reference_contact, bike_plate, bank_account_pix, created_at FROM motoboys"))
        rows = r.fetchall()
        for row in rows:
            (old_id, full_name, cpf, cnpj, address, reference_contact, bike_plate, bank_account_pix, created_at) = row
            conn.execute(
                text("""
                    INSERT INTO suppliers (name, document, type, is_active, created_at, address, reference_contact, bike_plate, bank_account_pix, document_secondary)
                    VALUES (:name, :doc, 'motoboy', 1, :created_at, :address, :reference_contact, :bike_plate, :bank_account_pix, :document_secondary)
                """),
                {
                    "name": full_name or "",
                    "doc": cpf,
                    "created_at": created_at,
                    "address": address,
                    "reference_contact": reference_contact,
                    "bike_plate": bike_plate,
                    "bank_account_pix": bank_account_pix,
                    "document_secondary": cnpj,
                },
            )
            new_id = _last_insert_id(conn)
            motoboy_id_to_supplier[old_id] = new_id
    else:
        r = conn.execute(text("SELECT id, full_name, cpf, cnpj, address, reference_contact, bike_plate, bank_account_pix, created_at FROM motoboys"))
        rows = r.fetchall()
        for row in rows:
            (old_id, full_name, cpf, cnpj, address, reference_contact, bike_plate, bank_account_pix, created_at) = row
            r2 = conn.execute(
                text("""
                    INSERT INTO suppliers (name, document, type, is_active, created_at, address, reference_contact, bike_plate, bank_account_pix, document_secondary)
                    VALUES (:name, :doc, 'motoboy', true, :created_at, :address, :reference_contact, :bike_plate, :bank_account_pix, :document_secondary)
                    RETURNING id
                """),
                {
                    "name": full_name or "",
                    "doc": cpf,
                    "created_at": created_at,
                    "address": address,
                    "reference_contact": reference_contact,
                    "bike_plate": bike_plate,
                    "bank_account_pix": bank_account_pix,
                    "document_secondary": cnpj,
                },
            )
            new_id = r2.scalar()
            motoboy_id_to_supplier[old_id] = new_id

    # Copy client_contracts -> contracts
    r = conn.execute(text("SELECT id, client_id, start_date, end_date, contract_value, motoboy_quantity FROM client_contracts"))
    for row in r.fetchall():
        (_, client_id, start_date, end_date, contract_value, motoboy_quantity) = row
        supplier_id = client_id_to_supplier.get(client_id)
        if supplier_id is None:
            continue
        conn.execute(
            text("""
                INSERT INTO contracts (supplier_id, contract_type, start_date, end_date, contract_value, motoboy_quantity)
                VALUES (:supplier_id, 'client', :start_date, :end_date, :contract_value, :motoboy_quantity)
            """),
            {
                "supplier_id": supplier_id,
                "start_date": start_date,
                "end_date": end_date,
                "contract_value": contract_value,
                "motoboy_quantity": motoboy_quantity,
            },
        )

    # Copy motoboy_contracts -> contracts
    r = conn.execute(text("SELECT id, motoboy_id, client_id, start_date, end_date, location, service_value, bonus_value, missing_value FROM motoboy_contracts"))
    for row in r.fetchall():
        (_, motoboy_id, client_id, start_date, end_date, location, service_value, bonus_value, missing_value) = row
        supplier_id = motoboy_id_to_supplier.get(motoboy_id)
        if supplier_id is None:
            continue
        other_id = client_id_to_supplier.get(client_id) if client_id else None
        conn.execute(
            text("""
                INSERT INTO contracts (supplier_id, contract_type, other_supplier_id, start_date, end_date, location, service_value, bonus_value, missing_value)
                VALUES (:supplier_id, 'motoboy', :other_supplier_id, :start_date, :end_date, :location, :service_value, :bonus_value, :missing_value)
            """),
            {
                "supplier_id": supplier_id,
                "other_supplier_id": other_id,
                "start_date": start_date,
                "end_date": end_date,
                "location": location,
                "service_value": service_value,
                "bonus_value": bonus_value,
                "missing_value": missing_value,
            },
        )


def downgrade():
    # Data migration downgrade: clear new tables (contracts; suppliers that came from clients/motoboys would need to be identified and removed - we don't store old ids, so we just clear contracts and leave suppliers as-is or truncate suppliers and re-run would lose new manual suppliers). So we only clear contracts on downgrade.
    op.get_bind().execute(text("DELETE FROM contracts"))
