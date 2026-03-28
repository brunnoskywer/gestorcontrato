"""Registro de falta (ausência) em contrato de motoboy."""

from sqlalchemy import UniqueConstraint

from app.extensions import db


class ContractAbsence(db.Model):
    __tablename__ = "contract_absences"
    __table_args__ = (UniqueConstraint("contract_id", "absence_date", name="uq_contract_absence_date"),)

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("contracts.id"), nullable=False)
    absence_date = db.Column(db.Date, nullable=False)
    justification = db.Column(db.String(500), nullable=False)
    substitute_name = db.Column(db.String(255), nullable=True)
    substitute_document = db.Column(db.String(50), nullable=True)
    substitute_pix = db.Column(db.String(255), nullable=True)
    substitute_amount = db.Column(db.Numeric(10, 2), nullable=True)

    diarist_supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    substitute_supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    financial_nature_id = db.Column(db.Integer, db.ForeignKey("financial_natures.id"), nullable=True)
    payable_entry_id = db.Column(db.Integer, db.ForeignKey("financial_entries.id"), nullable=True)

    contract = db.relationship("Contract", back_populates="absences")
    diarist_supplier = db.relationship("Supplier", foreign_keys=[diarist_supplier_id])
    substitute_supplier = db.relationship("Supplier", foreign_keys=[substitute_supplier_id])
    financial_nature = db.relationship("FinancialNature", foreign_keys=[financial_nature_id], lazy="joined")
    payable_entry = db.relationship("FinancialEntry", foreign_keys=[payable_entry_id], lazy="joined")
