"""Diaristas elegíveis para falta (mesmas regras do modal de contrato)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import func

from app.models import MOTOBOY_TERMINATED_STATUSES, SUPPLIER_MOTOBOY, Supplier

if TYPE_CHECKING:
    from app.models import Contract, ContractAbsence


def diarist_motoboys_for_contract(
    contract: Optional["Contract"] = None,
    absence: Optional["ContractAbsence"] = None,
) -> list[Supplier]:
    """
    Diaristas ativos, não encerrados, do mesmo UF do titular do contrato.
    Na edição, inclui o substituto atual mesmo fora da lista.
    """
    uf = ""
    if contract and contract.supplier:
        uf = (contract.supplier.state or "").strip().upper()
    q = (
        Supplier.query.filter_by(type=SUPPLIER_MOTOBOY, is_active=True, is_diarist=True)
        .filter(~Supplier.status.in_(MOTOBOY_TERMINATED_STATUSES))
    )
    if uf:
        q = q.filter(func.upper(Supplier.state) == uf)
    rows = q.order_by(Supplier.name).all()
    if absence and absence.substitute_supplier_id:
        current = absence.substitute_supplier
        if current and current.id not in {m.id for m in rows}:
            return [current] + rows
    return rows
