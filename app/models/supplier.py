from datetime import datetime

from app.extensions import db


SUPPLIER_CLIENT = "client"
SUPPLIER_SUPPLIER = "supplier"
SUPPLIER_MOTOBOY = "motoboy"


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    document = db.Column(db.String(20), nullable=True, unique=True)
    type = db.Column(db.String(20), nullable=False)  # client | supplier | motoboy
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Client-type fields (nullable)
    legal_name = db.Column(db.String(255), nullable=True)
    trade_name = db.Column(db.String(255), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    contact_name = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    billing_company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)

    # Motoboy-type fields (nullable)
    reference_contact = db.Column(db.String(255), nullable=True)
    bike_plate = db.Column(db.String(20), nullable=True)
    bank_account_pix = db.Column(db.String(120), nullable=True)
    document_secondary = db.Column(db.String(20), nullable=True)  # e.g. motoboy CNPJ

    billing_company = db.relationship("Company", back_populates="billing_suppliers", foreign_keys=[billing_company_id])

