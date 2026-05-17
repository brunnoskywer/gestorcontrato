"""Execução de solicitações pendentes (resolver / rejeitar)."""
from __future__ import annotations

import calendar
import json
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any, Optional, Tuple

from flask import request
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app.admin.motoboy_contracts import (
    _resolve_substitute_amount_from_form,
    _sync_absence_substitute_payable,
)
from app.constants.brazil_ufs import is_valid_uf
from app.extensions import db
from app.models import (
    BATCH_TYPE_MOTOBOY_DISTRATO,
    CONTRACT_TYPE_MOTOBOY,
    Contract,
    ContractAbsence,
    FinancialBatch,
    FinancialEntry,
    FinancialNature,
    Company,
    Supplier,
    SUPPLIER_CLIENT,
    SUPPLIER_MOTOBOY,
    MOTOBOY_TERMINATED_STATUSES,
    motoboy_supplier_operational,
)
from app.models.financial_entry import ENTRY_PAYABLE
from app.models.requests import (
    REQUEST_STATUS_PENDING,
    REQUEST_STATUS_REJECTED,
    REQUEST_STATUS_RESOLVED,
    REQUEST_TYPE_ABSENCE,
    REQUEST_TYPE_DISTRATO,
    REQUEST_TYPE_MOTOBOY_INCLUSION,
    REQUEST_TYPE_RELOCATION,
    Request,
)
from app.models.supplier import client_display_label
from app.services.motoboy_contract_finance import motoboy_contract_in_processing_scope
from app.services.motoboy_distrato import compute_motoboy_distrato_breakdown


def pending_requests_count() -> int:
    return Request.query.filter_by(status=REQUEST_STATUS_PENDING).count()


def mark_request_resolved(req: Request) -> None:
    req.status = REQUEST_STATUS_RESOLVED
    req.resolved_at = datetime.utcnow()
    req.resolved_by_id = current_user.id
    req.updated_at = datetime.utcnow()


def reject_request(req: Request, reason: str) -> None:
    req.status = REQUEST_STATUS_REJECTED
    req.rejection_reason = reason.strip()
    req.rejected_at = datetime.utcnow()
    req.rejected_by_id = current_user.id
    req.updated_at = datetime.utcnow()


def motoboy_from_payload(payload: dict[str, Any]) -> SimpleNamespace:
    """Objeto compatível com o fragmento de formulário de motoboy."""
    status = (payload.get("status") or "pending").strip().lower()
    if status == "inactive":
        status = "terminated"
    return SimpleNamespace(
        name=payload.get("full_name") or "",
        document=payload.get("cpf") or "",
        document_secondary=payload.get("cnpj") or "",
        cep=payload.get("cep") or "",
        city=payload.get("city") or "",
        street=payload.get("street") or "",
        neighborhood=payload.get("neighborhood") or "",
        address=payload.get("address") or "",
        state=payload.get("state") or "",
        reference_contact=payload.get("reference_contact") or "",
        bike_plate=payload.get("bike_plate") or "",
        bank_account_pix=payload.get("bank_account_pix") or "",
        status=status,
        contact_phone=payload.get("contact_phone") or "",
        notes=payload.get("notes") or "",
        is_diarist=bool(payload.get("is_diarist")),
    )


def _parse_date_str(value: str) -> Optional[date]:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _normalize_motoboy_status(raw: str | None) -> str:
    s = (raw or "active").strip().lower()
    if s == "inactive":
        return "terminated"
    if s in ("active", "pending", "terminated"):
        return s
    return "pending"


def resolve_motoboy_inclusion(req: Request) -> Tuple[bool, str]:
    payload = req.payload or {}
    full_name = (request.form.get("full_name") or payload.get("full_name") or "").strip()
    cpf = (request.form.get("cpf") or payload.get("cpf") or "").strip()
    cnpj = (request.form.get("cnpj") or payload.get("cnpj") or "").strip()
    cep = (request.form.get("cep") or payload.get("cep") or "").strip()
    address = (request.form.get("address") or payload.get("address") or "").strip()
    street = (request.form.get("street") or payload.get("street") or "").strip()
    neighborhood = (request.form.get("neighborhood") or payload.get("neighborhood") or "").strip()
    city = (request.form.get("city") or payload.get("city") or "").strip()
    state = (request.form.get("state") or payload.get("state") or "").strip().upper()
    reference_contact = (
        request.form.get("reference_contact") or payload.get("reference_contact") or ""
    ).strip()
    bike_plate = (request.form.get("bike_plate") or payload.get("bike_plate") or "").strip()
    bank_account_pix = (
        request.form.get("bank_account_pix") or payload.get("bank_account_pix") or ""
    ).strip()
    status = _normalize_motoboy_status(request.form.get("status") or payload.get("status"))
    contact_phone = (
        request.form.get("contact_phone") or payload.get("contact_phone") or ""
    ).strip()
    notes = (request.form.get("notes") or payload.get("notes") or "").strip()
    is_diarist = request.form.get("is_diarist") == "1" or bool(payload.get("is_diarist"))

    if not full_name or not cpf:
        return False, "Nome completo e CPF são obrigatórios."
    if not street or not neighborhood or not city or not is_valid_uf(state):
        return False, "Preencha rua, bairro, cidade e UF válidos do motoboy."

    motoboy = Supplier(
        name=full_name,
        document=cpf,
        type=SUPPLIER_MOTOBOY,
        is_active=status not in MOTOBOY_TERMINATED_STATUSES,
        address=address or None,
        cep=cep or None,
        street=street,
        neighborhood=neighborhood,
        city=city,
        state=state,
        reference_contact=reference_contact or None,
        bike_plate=bike_plate or None,
        bank_account_pix=bank_account_pix or None,
        document_secondary=cnpj or None,
        status=status,
        contact_phone=contact_phone or None,
        notes=notes or None,
        is_diarist=is_diarist,
    )
    db.session.add(motoboy)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return False, "Não foi possível salvar o motoboy (CPF já cadastrado?)."
    mark_request_resolved(req)
    return True, "Motoboy incluído e solicitação resolvida."


def resolve_relocation(req: Request) -> Tuple[bool, str]:
    payload = req.payload or {}
    contract_id = payload.get("motoboy_contract_id")
    client_id = request.form.get("new_client_id", type=int) or payload.get("new_client_id")
    if not contract_id:
        return False, "Contrato não informado na solicitação."
    contract = Contract.query.filter_by(
        id=int(contract_id), contract_type=CONTRACT_TYPE_MOTOBOY
    ).first()
    if not contract:
        return False, "Contrato não encontrado."
    if not client_id:
        return False, "Selecione o novo cliente."
    client = Supplier.query.filter_by(id=int(client_id), type=SUPPLIER_CLIENT).first()
    if not client:
        return False, "Cliente inválido."
    contract.other_supplier_id = client.id
    mark_request_resolved(req)
    return True, f"Realocação aplicada para {client_display_label(client)}."


def _apply_contract_end_date(contract: Contract, payload: dict) -> Tuple[bool, str]:
    if contract.end_date:
        return True, ""
    end_raw = (request.form.get("end_date") or payload.get("end_date") or "").strip()
    end_d = _parse_date_str(end_raw)
    if not end_d:
        return False, "Informe a data de distrato."
    contract.end_date = end_d
    return True, ""


def _create_distrato_financial(
    contract: Contract, charge_date: date, nature_id: int, company_id: int
) -> Tuple[bool, str]:
    nature = FinancialNature.query.get(nature_id)
    if not nature or not nature.is_active or nature.kind not in ("payable", "both"):
        return False, "Natureza financeira inválida ou inativa."
    company = Company.query.get(company_id)
    if not company:
        return False, "Empresa inválida."
    if contract.supplier and not motoboy_supplier_operational(contract.supplier):
        return False, "Motoboy encerrado no cadastro."

    breakdown, err = compute_motoboy_distrato_breakdown(contract)
    if err:
        return False, err
    if not breakdown:
        return False, "Não foi possível calcular o valor do distrato."

    net = float(breakdown.get("net_amount") or 0)
    year, month = contract.end_date.year, contract.end_date.month
    desc = f"Distrato contrato motoboy #{contract.id} - {year}-{month:02d}"

    if FinancialEntry.query.filter_by(description=desc).first():
        return False, "Já existe um lançamento de distrato para este contrato e período."

    batch_type = BATCH_TYPE_MOTOBOY_DISTRATO
    client_supplier_id = contract.other_supplier_id
    batch = FinancialBatch.query.filter_by(
        batch_type=batch_type,
        year=year,
        month=month,
        financial_nature_id=nature_id,
        client_supplier_id=client_supplier_id,
        company_id=company_id,
    ).first()
    if batch is None:
        batch = FinancialBatch(
            batch_type=batch_type,
            year=year,
            month=month,
            financial_nature_id=nature_id,
            charge_date=charge_date,
            company_id=company_id,
            client_supplier_id=client_supplier_id,
            created_by_id=getattr(current_user, "id", None),
        )
        db.session.add(batch)
        db.session.flush()

    _meses = (
        "",
        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro",
    )
    month_days = calendar.monthrange(year, month)[1]
    snapshot = {
        "v": 2,
        "contract_id": contract.id,
        "contract_start_date": contract.start_date.isoformat() if contract.start_date else None,
        "contract_end_date": contract.end_date.isoformat() if contract.end_date else None,
        "period_label": f"{_meses[month]} de {year}",
        "period_year": year,
        "period_month": month,
        "month_days": month_days,
        "effective_start_date": breakdown["effective_start"].isoformat(),
        "effective_end_date": breakdown["effective_end"].isoformat(),
        "effective_days": breakdown["effective_days"],
        "motoboy_name": (contract.supplier.name if contract.supplier else "") or "-",
        "client_name": client_display_label(contract.other_supplier)
        if contract.other_supplier
        else "-",
        "gross_amount": breakdown["gross_amount"],
        "has_absences": breakdown["has_absences"],
        "bonus_value": breakdown["base_bonus"],
        "absence_count": breakdown["absence_count"],
        "missing_total": breakdown["missing_total"],
        "after_missing": breakdown["after_missing"],
        "paid_total": breakdown["paid_total"],
        "paid_by_nature": breakdown["paid_by_nature"],
        "paid_excluded_residual_nature": breakdown["paid_excluded_residual_nature"],
        "paid_entries": breakdown["paid_entries"],
        "net_amount": net,
    }

    entry = FinancialEntry(
        company_id=company_id,
        account_id=None,
        financial_nature_id=nature_id,
        supplier_id=contract.supplier_id,
        entry_type=ENTRY_PAYABLE,
        description=desc,
        amount=net,
        due_date=charge_date,
        settled_at=None,
        reference=None,
        financial_batch_id=batch.id,
        processing_snapshot=json.dumps(snapshot, ensure_ascii=False),
    )
    db.session.add(entry)
    return True, ""


def resolve_distrato(req: Request) -> Tuple[bool, str]:
    payload = req.payload or {}
    contract_id = payload.get("motoboy_contract_id")
    if not contract_id:
        return False, "Contrato não informado na solicitação."
    contract = Contract.query.filter_by(
        id=int(contract_id), contract_type=CONTRACT_TYPE_MOTOBOY
    ).first()
    if not contract:
        return False, "Contrato não encontrado."

    ok, msg = _apply_contract_end_date(contract, payload)
    if not ok:
        return False, msg

    charge_date_str = (request.form.get("charge_date") or "").strip()
    nature_id = request.form.get("financial_nature_id", type=int)
    company_id = request.form.get("company_id", type=int)
    if not charge_date_str or not nature_id or not company_id:
        return False, "Data de cobrança, natureza financeira e empresa são obrigatórios."
    try:
        charge_date = date.fromisoformat(charge_date_str)
    except ValueError:
        return False, "Data de cobrança inválida."

    ok, err = _create_distrato_financial(contract, charge_date, nature_id, company_id)
    if not ok:
        return False, err
    mark_request_resolved(req)
    return True, "Distrato gerado e solicitação resolvida."


def resolve_absence(req: Request) -> Tuple[bool, str]:
    payload = req.payload or {}
    contract_id = payload.get("motoboy_contract_id")
    if not contract_id:
        return False, "Contrato não informado na solicitação."
    contract = Contract.query.filter_by(
        id=int(contract_id), contract_type=CONTRACT_TYPE_MOTOBOY
    ).first()
    if not contract:
        return False, "Contrato não encontrado."
    if not motoboy_contract_in_processing_scope(contract):
        return False, "Contrato bloqueado ou motoboy encerrado."

    absence_date_str = (
        request.form.get("absence_date") or payload.get("absence_date") or ""
    ).strip()
    justification = (
        request.form.get("justification") or payload.get("justification") or ""
    ).strip()
    if not absence_date_str or not justification:
        return False, "Dia e justificativa são obrigatórios."
    try:
        absence_date = date.fromisoformat(absence_date_str)
    except ValueError:
        return False, "Data inválida."

    substitute_id = request.form.get("substitute_supplier_id", type=int)
    if substitute_id is None:
        sub_payload = payload.get("substitute_supplier_id")
        if sub_payload is not None and str(sub_payload).strip():
            try:
                substitute_id = int(sub_payload)
            except (TypeError, ValueError):
                substitute_id = None

    nature_id = request.form.get("financial_nature_id", type=int)
    if substitute_id and not nature_id:
        return False, "Com motoboy diarista, a natureza financeira é obrigatória."

    if substitute_id:
        sub = Supplier.query.filter_by(id=substitute_id, type=SUPPLIER_MOTOBOY).first()
        if not sub or not sub.is_diarist or not motoboy_supplier_operational(sub):
            return False, "Motoboy diarista inválido."
        tit = contract.supplier
        if tit and sub:
            uf_t = (tit.state or "").strip().upper()
            uf_s = (sub.state or "").strip().upper()
            if uf_t and uf_s and uf_t != uf_s:
                return False, "O diarista deve ser do mesmo UF do titular."
    else:
        nature_id = None

    resolved_substitute_amount, amt_err = _resolve_substitute_amount_from_form(
        contract, substitute_id
    )
    if amt_err:
        return False, amt_err

    existing = ContractAbsence.query.filter_by(
        contract_id=contract.id,
        absence_date=absence_date,
    ).first()
    if existing:
        return False, "Já existe falta registrada nesta data."

    absence = ContractAbsence(
        contract_id=contract.id,
        absence_date=absence_date,
        justification=justification,
        substitute_supplier_id=substitute_id,
        financial_nature_id=nature_id,
        substitute_name=None,
        substitute_document=None,
        substitute_pix=None,
        substitute_amount=resolved_substitute_amount,
    )
    db.session.add(absence)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return False, "Já existe falta registrada nesta data."

    ok, err = _sync_absence_substitute_payable(contract, absence)
    if not ok:
        db.session.rollback()
        return False, err or "Não foi possível gerar a conta a pagar."

    mark_request_resolved(req)
    return True, "Falta registrada e solicitação resolvida."


def execute_resolve(req: Request) -> Tuple[bool, str]:
    if req.status != REQUEST_STATUS_PENDING:
        return False, "Somente solicitações pendentes podem ser resolvidas."
    handlers = {
        REQUEST_TYPE_MOTOBOY_INCLUSION: resolve_motoboy_inclusion,
        REQUEST_TYPE_DISTRATO: resolve_distrato,
        REQUEST_TYPE_RELOCATION: resolve_relocation,
        REQUEST_TYPE_ABSENCE: resolve_absence,
    }
    handler = handlers.get(req.request_type)
    if not handler:
        return False, "Tipo de solicitação não suportado para resolução."
    return handler(req)
