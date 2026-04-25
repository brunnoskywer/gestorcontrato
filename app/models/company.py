from datetime import datetime

from sqlalchemy.orm import validates

from app.extensions import db


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    legal_name = db.Column(db.String(255), nullable=False)  # Razão Social
    trade_name = db.Column(db.String(255), nullable=True)  # Fantasia
    cnpj = db.Column(db.String(20), unique=True, nullable=False)
    partner_name = db.Column(db.String(255), nullable=True)  # Sócio
    address = db.Column(db.String(255), nullable=True)
    cep = db.Column(db.String(9), nullable=True)
    street = db.Column(db.String(255), nullable=True)
    neighborhood = db.Column(db.String(120), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    state = db.Column(db.String(2), nullable=True)
    allow_contract_generation = db.Column(db.Boolean, nullable=False, default=True)

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

    @validates("legal_name", "trade_name", "partner_name")
    def _normalize_company_name_fields(self, key: str, value):
        """Razão social, fantasia e sócio sempre em caixa alta."""
        if key == "legal_name":
            if value is None:
                return ""
            return str(value).strip().upper()
        if value is None:
            return None
        s = str(value).strip().upper()
        return s if s else None

