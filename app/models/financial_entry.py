"""Lançamento financeiro: contas a pagar ou a receber."""
from datetime import date, datetime

from app.extensions import db
from app.models.supplier import Supplier


# Tipos de lançamento
ENTRY_PAYABLE = "payable"        # Conta a pagar
ENTRY_RECEIVABLE = "receivable"  # Conta a receber


class FinancialEntry(db.Model):
    __tablename__ = "financial_entries"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    financial_nature_id = db.Column(
        db.Integer, db.ForeignKey("financial_natures.id"), nullable=False
    )

    entry_type = db.Column(db.String(20), nullable=False)  # payable, receivable
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    settled_at = db.Column(db.DateTime, nullable=True)  # quando foi pago/recebido
    reference = db.Column(db.String(255), nullable=True)
    processing_snapshot = db.Column(db.Text, nullable=True)
    financial_batch_id = db.Column(db.Integer, db.ForeignKey("financial_batches.id"), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = db.relationship("Company", back_populates="financial_entries")
    account = db.relationship(
        "Account",
        back_populates="entries",
        foreign_keys=[account_id],
    )
    financial_nature = db.relationship(
        "FinancialNature",
        back_populates="entries",
        foreign_keys=[financial_nature_id],
    )
    supplier = db.relationship("Supplier", foreign_keys=[supplier_id])
    batch = db.relationship("FinancialBatch", back_populates="entries", foreign_keys=[financial_batch_id])
    attachment = db.relationship(
        "FinancialEntryAttachment",
        back_populates="entry",
        uselist=False,
        cascade="all, delete-orphan",
    )
