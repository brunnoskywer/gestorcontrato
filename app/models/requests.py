"""Solicitações (workflow pendente → resolvida / rejeitada)."""
from datetime import datetime

from app.extensions import db

REQUEST_TYPE_MOTOBOY_INCLUSION = "motoboy_inclusion"
REQUEST_TYPE_DISTRATO = "distrato"
REQUEST_TYPE_RELOCATION = "relocation"
REQUEST_TYPE_ABSENCE = "absence"

REQUEST_TYPES = (
    REQUEST_TYPE_MOTOBOY_INCLUSION,
    REQUEST_TYPE_DISTRATO,
    REQUEST_TYPE_RELOCATION,
    REQUEST_TYPE_ABSENCE,
)

REQUEST_STATUS_PENDING = "pending"
REQUEST_STATUS_RESOLVED = "resolved"
REQUEST_STATUS_REJECTED = "rejected"
# Legado (migrado para resolved)
REQUEST_STATUS_APPROVED = "approved"

REQUEST_STATUSES = (
    REQUEST_STATUS_PENDING,
    REQUEST_STATUS_RESOLVED,
    REQUEST_STATUS_REJECTED,
)

REQUEST_TYPE_LABELS = {
    REQUEST_TYPE_MOTOBOY_INCLUSION: "Inclusão de Motoboy",
    REQUEST_TYPE_DISTRATO: "Distrato de motoboy",
    REQUEST_TYPE_RELOCATION: "Realocação de motoboy",
    REQUEST_TYPE_ABSENCE: "Inclusão de falta",
}

REQUEST_STATUS_LABELS = {
    REQUEST_STATUS_PENDING: "Pendente",
    REQUEST_STATUS_RESOLVED: "Resolvida",
    REQUEST_STATUS_REJECTED: "Rejeitada",
}

# Opções do filtro (sem status legado duplicado)
REQUEST_STATUS_FILTER_LABELS = {
    s: REQUEST_STATUS_LABELS[s] for s in REQUEST_STATUSES
}


class Request(db.Model):
    __tablename__ = "requests"

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    request_type = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=REQUEST_STATUS_PENDING)
    payload = db.Column(db.JSON, nullable=False, default=dict)
    rejection_reason = db.Column(db.Text, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    rejected_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    requester = db.relationship("User", foreign_keys=[requester_id])
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_id])
    rejected_by = db.relationship("User", foreign_keys=[rejected_by_id])

    @property
    def supervisor(self):
        """Compatibilidade com código legado."""
        return self.requester

    @property
    def supervisor_id(self):
        return self.requester_id

    @property
    def is_pending(self) -> bool:
        return self.status == REQUEST_STATUS_PENDING

    @property
    def is_resolved(self) -> bool:
        return self.status in (REQUEST_STATUS_RESOLVED, REQUEST_STATUS_APPROVED)

    @property
    def type_label(self) -> str:
        return REQUEST_TYPE_LABELS.get(self.request_type, self.request_type)

    @property
    def status_label(self) -> str:
        if self.status == REQUEST_STATUS_APPROVED:
            return REQUEST_STATUS_LABELS[REQUEST_STATUS_RESOLVED]
        return REQUEST_STATUS_LABELS.get(self.status, self.status)
