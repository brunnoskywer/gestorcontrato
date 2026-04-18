"""Gravação e remoção de arquivos de anexos de contrato no disco."""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from flask import current_app, has_app_context
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.config import BASE_DIR
from app.extensions import db
from app.models.contract_attachment import (
    CONTRACT_ATTACHMENT_KIND_VALUES,
    ContractAttachment,
)

if TYPE_CHECKING:
    from app.models import Contract

ALLOWED_EXTENSIONS = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".doc", ".docx"}
)
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024


def get_upload_root() -> Path:
    if has_app_context():
        return Path(current_app.config["UPLOAD_FOLDER"])
    return Path(os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "instance" / "uploads")))


def _safe_relpath(relpath: str) -> bool:
    if not relpath or not relpath.strip():
        return False
    norm = relpath.replace("\\", "/")
    if norm.startswith("/") or ".." in norm.split("/"):
        return False
    return True


def delete_stored_file(storage_relpath: str) -> None:
    if not _safe_relpath(storage_relpath):
        return
    root = get_upload_root().resolve()
    path = (root / storage_relpath).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def delete_attachment_files_for_contract_ids(contract_ids: list[int]) -> None:
    if not contract_ids:
        return
    rows = (
        db.session.query(ContractAttachment.storage_relpath)
        .filter(ContractAttachment.contract_id.in_(contract_ids))
        .all()
    )
    for (relpath,) in rows:
        delete_stored_file(relpath)


def store_motoboy_contract_upload(
    contract: Contract,
    kind: str,
    file_storage: FileStorage,
) -> ContractAttachment:
    if kind not in CONTRACT_ATTACHMENT_KIND_VALUES:
        raise ValueError("Tipo de anexo inválido.")
    if not file_storage or not file_storage.filename:
        raise ValueError("Selecione um arquivo.")

    orig_name = secure_filename(file_storage.filename) or "arquivo"
    ext = Path(orig_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Extensão não permitida. Use: PDF, imagens (PNG, JPG, WebP) ou Word (DOC/DOCX)."
        )

    if file_storage.content_length is not None:
        size = int(file_storage.content_length)
    else:
        stream = file_storage.stream
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(0)
    if size > MAX_ATTACHMENT_BYTES:
        raise ValueError("Arquivo muito grande (máximo 15 MB).")
    if size == 0:
        raise ValueError("Arquivo vazio.")

    upload_root = get_upload_root()
    target_dir = upload_root / "contracts" / str(contract.id)
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4().hex}{ext}"
    relpath = f"contracts/{contract.id}/{stored_name}"
    abs_path = target_dir / stored_name
    file_storage.save(abs_path)

    content_type = file_storage.content_type or None

    existing = ContractAttachment.query.filter_by(
        contract_id=contract.id, kind=kind
    ).first()
    if existing:
        old_relpath = existing.storage_relpath
        existing.original_filename = orig_name[:255]
        existing.storage_relpath = relpath
        existing.content_type = content_type
        existing.file_size = size
        delete_stored_file(old_relpath)
        return existing

    row = ContractAttachment(
        contract_id=contract.id,
        kind=kind,
        original_filename=orig_name[:255],
        storage_relpath=relpath,
        content_type=content_type,
        file_size=size,
    )
    db.session.add(row)
    return row
