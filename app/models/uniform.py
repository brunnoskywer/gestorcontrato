"""Fardamentos: cadastro por item/tamanho, movimentações e saldo em estoque."""
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import validates

from app.extensions import db

# Tamanhos fixos (ordem de exibição)
UNIFORM_SIZES = ("PP", "P", "M", "G", "GG", "XG", "2G", "3G", "4G")
UNIFORM_SIZE_LABELS = {s: s for s in UNIFORM_SIZES}

MOVEMENT_ENTRY = "entry"
MOVEMENT_EXIT = "exit"

ENTRY_PURCHASE = "purchase"
ENTRY_RETURN = "return"

EXIT_DISCARD = "discard"
EXIT_SHIPMENT = "shipment"
EXIT_LOST = "lost"

MOVEMENT_DIRECTION_LABELS = {
    MOVEMENT_ENTRY: "Entrada",
    MOVEMENT_EXIT: "Saída",
}

ENTRY_SUBTYPE_LABELS = {
    ENTRY_PURCHASE: "Compra",
    ENTRY_RETURN: "Retorno",
}

EXIT_SUBTYPE_LABELS = {
    EXIT_DISCARD: "Descarte",
    EXIT_SHIPMENT: "Envio",
    EXIT_LOST: "Perdido",
}

MOVEMENT_SUBTYPE_LABELS = {**ENTRY_SUBTYPE_LABELS, **EXIT_SUBTYPE_LABELS}


class Uniform(db.Model):
    """Item de fardamento (SKU = descrição + tamanho)."""

    __tablename__ = "uniforms"
    __table_args__ = (UniqueConstraint("name", "size", name="uq_uniform_name_size"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    size = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    movements = db.relationship(
        "UniformMovement",
        back_populates="uniform",
        lazy="dynamic",
        foreign_keys="UniformMovement.uniform_id",
    )

    @validates("name")
    def _upper_name(self, _key, value):
        if value is None:
            return value
        return value.strip().upper()

    @validates("size")
    def _validate_size(self, _key, value):
        if value not in UNIFORM_SIZES:
            raise ValueError(f"Tamanho inválido: {value}")
        return value

    @property
    def display_label(self) -> str:
        return f"{self.name} — {self.size}"


class UniformMovement(db.Model):
    """Movimentação de estoque (entrada ou saída)."""

    __tablename__ = "uniform_movements"

    id = db.Column(db.Integer, primary_key=True)
    uniform_id = db.Column(db.Integer, db.ForeignKey("uniforms.id"), nullable=False)
    direction = db.Column(db.String(10), nullable=False)  # entry | exit
    subtype = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    motoboy_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    financial_entry_id = db.Column(
        db.Integer, db.ForeignKey("financial_entries.id"), nullable=True
    )
    notes = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    uniform = db.relationship("Uniform", back_populates="movements", foreign_keys=[uniform_id])
    motoboy = db.relationship("Supplier", foreign_keys=[motoboy_id])
    financial_entry = db.relationship("FinancialEntry", foreign_keys=[financial_entry_id])

    @property
    def direction_label(self) -> str:
        return MOVEMENT_DIRECTION_LABELS.get(self.direction, self.direction)

    @property
    def subtype_label(self) -> str:
        return MOVEMENT_SUBTYPE_LABELS.get(self.subtype, self.subtype)
