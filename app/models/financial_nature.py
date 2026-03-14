"""Natureza financeira para classificar lançamentos (ex.: combustível, aluguel)."""
from datetime import datetime

from app.extensions import db


class FinancialNature(db.Model):
    __tablename__ = "financial_natures"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    kind = db.Column(db.String(20), nullable=False, default="payable")  # payable | receivable
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    entries = db.relationship("FinancialEntry", back_populates="financial_nature", lazy="dynamic")

