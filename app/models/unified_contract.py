"""Unified contract: client contracts and motoboy contracts in one table."""
from datetime import date

from app.extensions import db


CONTRACT_TYPE_CLIENT = "client"
CONTRACT_TYPE_MOTOBOY = "motoboy"


class Contract(db.Model):
    __tablename__ = "contracts"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    contract_type = db.Column(db.String(20), nullable=False)  # client | motoboy
    # Cliente do contrato quando contract_type=motoboy (obrigatório na regra de negócio; coluna permanece nullable no BD).
    other_supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    location = db.Column(db.String(255), nullable=True)

    # Motoboy contract fields
    service_value = db.Column(db.Numeric(10, 2), nullable=True)
    bonus_value = db.Column(db.Numeric(10, 2), nullable=True)
    missing_value = db.Column(db.Numeric(10, 2), nullable=True)
    advance_value = db.Column(db.Numeric(10, 2), nullable=True)
    # Contrato bloqueado: fora de adiantamento/residual/receita (faltas) e sem lançamentos manuais para o motoboy.
    is_blocked = db.Column(db.Boolean, nullable=False, default=False)

    # Client contract fields
    contract_value = db.Column(db.Numeric(10, 2), nullable=True)
    motoboy_quantity = db.Column(db.Integer, nullable=True)
    client_driver_unit_value = db.Column(db.Numeric(10, 2), nullable=True)
    client_driver_quantity = db.Column(db.Integer, nullable=True)
    client_other_unit_value = db.Column(db.Numeric(10, 2), nullable=True)
    client_other_quantity = db.Column(db.Integer, nullable=True)
    client_absence_reimburse_unit_value = db.Column(db.Numeric(10, 2), nullable=True)
    revenue_financial_nature_id = db.Column(
        db.Integer, db.ForeignKey("financial_natures.id"), nullable=True
    )

    supplier = db.relationship("Supplier", foreign_keys=[supplier_id])
    revenue_financial_nature = db.relationship(
        "FinancialNature",
        foreign_keys=[revenue_financial_nature_id],
    )
    other_supplier = db.relationship("Supplier", foreign_keys=[other_supplier_id])
    absences = db.relationship(
        "ContractAbsence",
        back_populates="contract",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    attachments = db.relationship(
        "ContractAttachment",
        back_populates="contract",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
