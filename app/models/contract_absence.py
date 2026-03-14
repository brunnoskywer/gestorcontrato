"""Registro de falta (ausência) em contrato de motoboy."""
from datetime import date

from sqlalchemy import UniqueConstraint

from app.extensions import db


class ContractAbsence(db.Model):
    __tablename__ = "contract_absences"
    __table_args__ = (UniqueConstraint("contract_id", "absence_date", name="uq_contract_absence_date"),)

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("contracts.id"), nullable=False)
    absence_date = db.Column(db.Date, nullable=False)
    justification = db.Column(db.String(500), nullable=False)

    contract = db.relationship("Contract", back_populates="absences")
