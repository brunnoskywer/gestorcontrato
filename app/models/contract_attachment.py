"""Anexos de contrato (arquivos armazenados em disco)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import event

from app.extensions import db


CONTRACT_ATTACHMENT_DOCUMENTO = "documento"
CONTRACT_ATTACHMENT_COMPROVANTE_ENDERECO = "comprovante_endereco"
CONTRACT_ATTACHMENT_CONTRATO = "contrato"
CONTRACT_ATTACHMENT_DISTRATO = "distrato"

CONTRACT_ATTACHMENT_KIND_VALUES = frozenset(
    {
        CONTRACT_ATTACHMENT_DOCUMENTO,
        CONTRACT_ATTACHMENT_COMPROVANTE_ENDERECO,
        CONTRACT_ATTACHMENT_CONTRATO,
        CONTRACT_ATTACHMENT_DISTRATO,
    }
)

CONTRACT_ATTACHMENT_KIND_LABELS_PT = {
    CONTRACT_ATTACHMENT_DOCUMENTO: "Documento",
    CONTRACT_ATTACHMENT_COMPROVANTE_ENDERECO: "Comprovante de endereço",
    CONTRACT_ATTACHMENT_CONTRATO: "Contrato",
    CONTRACT_ATTACHMENT_DISTRATO: "Distrato",
}

CONTRACT_ATTACHMENT_KIND_ORDER = (
    CONTRACT_ATTACHMENT_DOCUMENTO,
    CONTRACT_ATTACHMENT_COMPROVANTE_ENDERECO,
    CONTRACT_ATTACHMENT_CONTRATO,
    CONTRACT_ATTACHMENT_DISTRATO,
)


class ContractAttachment(db.Model):
    __tablename__ = "contract_attachments"
    __table_args__ = (
        db.UniqueConstraint(
            "contract_id",
            "kind",
            name="uq_contract_attachment_contract_kind",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(
        db.Integer,
        db.ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind = db.Column(db.String(32), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    storage_relpath = db.Column(db.String(512), nullable=False)
    content_type = db.Column(db.String(128), nullable=True)
    file_size = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    contract = db.relationship("Contract", back_populates="attachments")


@event.listens_for(ContractAttachment, "before_delete")
def _contract_attachment_remove_file(
    mapper, connection, target: ContractAttachment
) -> None:
    from app.services.contract_attachment_storage import delete_stored_file

    delete_stored_file(target.storage_relpath)
