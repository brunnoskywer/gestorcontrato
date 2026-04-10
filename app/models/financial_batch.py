from datetime import datetime

from app.extensions import db


BATCH_TYPE_REVENUE = "revenue"
BATCH_TYPE_PAYMENT = "payment"
BATCH_TYPE_ADVANCE = "advance"
BATCH_TYPE_RESIDUAL = "residual"
# Lançamentos de distrato gerados por contrato (não entram no critério de “já existe batch” do processamento em massa).
BATCH_TYPE_ADVANCE_DISTRATO = "advance_distrato"
BATCH_TYPE_RESIDUAL_DISTRATO = "residual_distrato"


class FinancialBatch(db.Model):
    __tablename__ = "financial_batches"

    id = db.Column(db.Integer, primary_key=True)
    batch_type = db.Column(db.String(20), nullable=False)  # revenue | payment | advance | residual
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    financial_nature_id = db.Column(db.Integer, db.ForeignKey("financial_natures.id"), nullable=False)
    charge_date = db.Column(db.Date, nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    client_supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    financial_nature = db.relationship("FinancialNature")
    company = db.relationship("Company", foreign_keys=[company_id])
    client_supplier = db.relationship("Supplier", foreign_keys=[client_supplier_id])
    created_by = db.relationship("User")
    entries = db.relationship(
        "FinancialEntry",
        back_populates="batch",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

