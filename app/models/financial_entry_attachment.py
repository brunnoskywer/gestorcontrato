"""Anexo único por lançamento financeiro (arquivo em disco)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import event

from app.extensions import db


class FinancialEntryAttachment(db.Model):
    __tablename__ = "financial_entry_attachments"
    __table_args__ = (
        db.UniqueConstraint(
            "financial_entry_id",
            name="uq_financial_entry_attachment_entry",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    financial_entry_id = db.Column(
        db.Integer,
        db.ForeignKey("financial_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename = db.Column(db.String(255), nullable=False)
    storage_relpath = db.Column(db.String(512), nullable=False)
    content_type = db.Column(db.String(128), nullable=True)
    file_size = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    entry = db.relationship("FinancialEntry", back_populates="attachment")


@event.listens_for(FinancialEntryAttachment, "before_delete")
def _financial_entry_attachment_remove_file(mapper, connection, target: FinancialEntryAttachment) -> None:
    from app.services.contract_attachment_storage import delete_stored_file

    delete_stored_file(target.storage_relpath)
