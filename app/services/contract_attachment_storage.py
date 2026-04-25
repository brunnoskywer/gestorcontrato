"""Gravação e remoção de arquivos de anexos de contrato no disco."""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any
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
from app.models.financial_entry_attachment import FinancialEntryAttachment

if TYPE_CHECKING:
    from app.models import Contract
    from app.models import FinancialEntry

ALLOWED_EXTENSIONS = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".doc", ".docx"}
)
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024


def get_upload_root() -> Path:
    if has_app_context():
        return Path(current_app.config["UPLOAD_FOLDER"])
    return Path(os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "instance" / "uploads")))


def normalize_storage_relpath(storage_relpath: str | None) -> str:
    if not storage_relpath:
        return ""
    return str(storage_relpath).strip().replace("\\", "/")


def _safe_relpath(relpath: str) -> bool:
    norm = normalize_storage_relpath(relpath)
    if not norm:
        return False
    if norm.startswith("/") or ".." in norm.split("/"):
        return False
    return True


def resolve_stored_file_for_download(storage_relpath: str | None) -> Path | None:
    """Caminho absoluto do arquivo se existir, estiver sob UPLOAD_FOLDER e for arquivo regular."""
    norm = normalize_storage_relpath(storage_relpath)
    if not _safe_relpath(norm):
        return None
    root = get_upload_root().resolve()
    path = (root / norm).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path


def stored_file_is_present(storage_relpath: str | None) -> bool:
    return resolve_stored_file_for_download(storage_relpath) is not None


def describe_storage_miss(storage_relpath: str | None) -> dict[str, Any]:
    """Informações para log ou tela quando o arquivo não está no disco."""
    norm = normalize_storage_relpath(storage_relpath)
    root = get_upload_root().resolve()
    out: dict[str, Any] = {
        "upload_root": str(root),
        "storage_relpath": norm or None,
        "expected_path": None,
        "reason": "empty_relpath",
    }
    if not norm:
        return out
    if not _safe_relpath(norm):
        out["reason"] = "unsafe_or_invalid_relpath"
        return out
    path = (root / norm).resolve()
    out["expected_path"] = str(path)
    try:
        path.relative_to(root)
    except ValueError:
        out["reason"] = "path_outside_upload_root"
        return out
    if path.is_dir():
        out["reason"] = "path_is_directory"
        return out
    if not path.exists():
        out["reason"] = "file_not_found"
        return out
    out["reason"] = "not_a_regular_file"
    return out


def _save_upload_atomic(file_storage: FileStorage, abs_path: Path) -> int:
    """Grava upload em arquivo temporário e faz replace atômico (reduz risco de arquivo parcial)."""
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = abs_path.with_name(f"{abs_path.name}.upload-{uuid4().hex}.part")
    try:
        file_storage.save(tmp)
        size = tmp.stat().st_size
        if size == 0:
            raise ValueError("Arquivo vazio.")
        if size > MAX_ATTACHMENT_BYTES:
            raise ValueError("Arquivo muito grande (máximo 15 MB).")
        os.replace(tmp, abs_path)
        return size
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def delete_stored_file(storage_relpath: str) -> None:
    if not _safe_relpath(storage_relpath):
        return
    root = get_upload_root().resolve()
    norm = normalize_storage_relpath(storage_relpath)
    path = (root / norm).resolve()
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


def delete_attachment_files_for_financial_entry_ids(entry_ids: list[int]) -> None:
    if not entry_ids:
        return
    rows = (
        db.session.query(FinancialEntryAttachment.storage_relpath)
        .filter(FinancialEntryAttachment.financial_entry_id.in_(entry_ids))
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

    upload_root = get_upload_root()
    target_dir = upload_root / "contracts" / str(contract.id)
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4().hex}{ext}"
    relpath = f"contracts/{contract.id}/{stored_name}"
    abs_path = target_dir / stored_name
    try:
        size = _save_upload_atomic(file_storage, abs_path)
    except ValueError:
        abs_path.unlink(missing_ok=True)
        raise

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


def store_financial_entry_upload(
    entry: FinancialEntry,
    file_storage: FileStorage,
) -> FinancialEntryAttachment:
    if not file_storage or not file_storage.filename:
        raise ValueError("Selecione um arquivo.")

    orig_name = secure_filename(file_storage.filename) or "arquivo"
    ext = Path(orig_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Extensão não permitida. Use: PDF, imagens (PNG, JPG, WebP) ou Word (DOC/DOCX)."
        )

    upload_root = get_upload_root()
    target_dir = upload_root / "financial_entries" / str(entry.id)
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4().hex}{ext}"
    relpath = f"financial_entries/{entry.id}/{stored_name}"
    abs_path = target_dir / stored_name
    try:
        size = _save_upload_atomic(file_storage, abs_path)
    except ValueError:
        abs_path.unlink(missing_ok=True)
        raise

    content_type = file_storage.content_type or None
    existing = FinancialEntryAttachment.query.filter_by(financial_entry_id=entry.id).first()
    if existing:
        old_relpath = existing.storage_relpath
        existing.original_filename = orig_name[:255]
        existing.storage_relpath = relpath
        existing.content_type = content_type
        existing.file_size = size
        delete_stored_file(old_relpath)
        return existing

    row = FinancialEntryAttachment(
        financial_entry_id=entry.id,
        original_filename=orig_name[:255],
        storage_relpath=relpath,
        content_type=content_type,
        file_size=size,
    )
    db.session.add(row)
    return row
