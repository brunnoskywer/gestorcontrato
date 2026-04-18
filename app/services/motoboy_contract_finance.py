"""Regras de participação de contratos de motoboy em processamentos e lançamentos."""
from __future__ import annotations

from datetime import date
from typing import Optional, Tuple

from app.models import CONTRACT_TYPE_MOTOBOY, Contract
from app.models.supplier import SUPPLIER_MOTOBOY, Supplier, motoboy_supplier_operational


def motoboy_contract_in_processing_scope(contract: Contract) -> bool:
    """
    Contrato de motoboy elegível a adiantamento, residual e impacto em receita (desconto por faltas).
    Encerrado no cadastro ou contrato bloqueado ficam fora.
    """
    if contract.contract_type != CONTRACT_TYPE_MOTOBOY:
        return True
    if getattr(contract, "is_blocked", False):
        return False
    if contract.supplier and not motoboy_supplier_operational(contract.supplier):
        return False
    return True


def motoboy_supplier_has_active_blocked_contract(supplier_id: int) -> bool:
    """Existe contrato de motoboy vigente (hoje) marcado como bloqueado para este motoboy."""
    today = date.today()
    return (
        Contract.query.filter(
            Contract.contract_type == CONTRACT_TYPE_MOTOBOY,
            Contract.supplier_id == supplier_id,
            Contract.is_blocked.is_(True),
            Contract.start_date <= today,
            (Contract.end_date.is_(None)) | (Contract.end_date >= today),
        ).first()
        is not None
    )


def motoboy_supplier_accepts_manual_financial_entries(
    supplier: Supplier,
) -> Tuple[bool, Optional[str]]:
    """
    Pode receber lançamento manual (contas a pagar/receber) vinculado a este fornecedor.
    Motoboy encerrado ou com contrato vigente bloqueado: não.
    """
    if supplier.type != SUPPLIER_MOTOBOY:
        return True, None
    if not motoboy_supplier_operational(supplier):
        return (
            False,
            "Motoboy encerrado no cadastro não pode receber lançamentos financeiros.",
        )
    if motoboy_supplier_has_active_blocked_contract(supplier.id):
        return (
            False,
            "Motoboy com contrato bloqueado não pode receber lançamentos financeiros.",
        )
    return True, None
