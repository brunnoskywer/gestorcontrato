from datetime import datetime

from app.extensions import db


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    legal_name = db.Column(db.String(255), nullable=False)  # Razão Social
    trade_name = db.Column(db.String(255), nullable=True)  # Fantasia
    cnpj = db.Column(db.String(20), unique=True, nullable=False)
    partner_name = db.Column(db.String(255), nullable=True)  # Sócio
    address = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    billing_suppliers = db.relationship(
        "Supplier",
        back_populates="billing_company",
        foreign_keys="Supplier.billing_company_id",
        lazy="dynamic",
    )
    accounts = db.relationship(
        "Account", back_populates="company", lazy="dynamic", cascade="all, delete-orphan"
    )
    financial_entries = db.relationship(
        "FinancialEntry",
        back_populates="company",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

