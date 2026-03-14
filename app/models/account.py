"""Conta (conta bancária/caixa) vinculada à empresa."""
from datetime import datetime

from app.extensions import db


class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship("Company", back_populates="accounts")
    entries = db.relationship(
        "FinancialEntry",
        back_populates="account",
        foreign_keys="FinancialEntry.account_id",
        lazy="dynamic",
    )
