"""Cálculo de valor de distrato para contratos de motoboy (regra única, proporcional no mês)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Optional, Tuple

from sqlalchemy.orm import joinedload

from app.models import ContractAbsence, FinancialEntry
from app.models.financial_entry import ENTRY_PAYABLE

if TYPE_CHECKING:
    from app.models import Contract


def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1) - timedelta(days=1)
    return date(year, month + 1, 1) - timedelta(days=1)


def contract_has_distrato_in_month(c: "Contract", year: int, month: int) -> bool:
    """True se a data de distrato (end_date) cai dentro do mês de referência do processamento."""
    if c.end_date is None:
        return False
    month_start = date(year, month, 1)
    month_end = _month_end(year, month)
    return month_start <= c.end_date <= month_end


def compute_motoboy_distrato_breakdown(
    c: "Contract",
) -> Tuple[Optional[dict], Optional[str]]:
    """
    Retorna o detalhamento completo do cálculo de distrato.
    """
    if not c.end_date:
        return None, "Cadastre a data de distrato no contrato antes de gerar o lançamento."
    year, month = c.end_date.year, c.end_date.month
    month_start = date(year, month, 1)
    month_end = _month_end(year, month)
    if not (month_start <= c.end_date <= month_end):
        return None, "Data de distrato fora do mês de referência."

    base_service = float(c.service_value or 0)
    base_bonus = float(c.bonus_value or 0)
    if base_service <= 0 and base_bonus <= 0:
        return None, "Contrato sem valor de prestação ou premiação."

    eff_start = max(c.start_date, month_start)
    eff_end = c.end_date
    if eff_start > eff_end:
        return None, "Período inválido: início do contrato após a data de distrato."

    effective_days = (eff_end - eff_start).days + 1
    if effective_days <= 0:
        return None, "Não há dias efetivos no período para calcular o distrato."

    absences = (
        ContractAbsence.query.filter(
            ContractAbsence.contract_id == c.id,
            ContractAbsence.absence_date >= month_start,
            ContractAbsence.absence_date <= month_end,
        )
        .all()
    )
    has_absences = len(absences) > 0
    base_total = base_service + (0 if has_absences else base_bonus)
    month_days = (month_end - month_start).days + 1
    proportion = (effective_days / month_days) if month_days > 0 else 0.0
    gross_amount = base_total * proportion
    if gross_amount <= 0:
        return None, "Valor bruto proporcional é zero."

    missing_total = 0.0
    if c.missing_value:
        mv = float(c.missing_value)
        for a in absences:
            if eff_start <= a.absence_date <= eff_end:
                missing_total += mv

    paid_qs = (
        FinancialEntry.query.options(joinedload(FinancialEntry.financial_nature))
        .filter(
            FinancialEntry.supplier_id == c.supplier_id,
            FinancialEntry.entry_type == ENTRY_PAYABLE,
            FinancialEntry.settled_at.isnot(None),
        )
        .filter(FinancialEntry.due_date >= month_start)
        .filter(FinancialEntry.due_date <= eff_end)
    )
    paid_total = 0.0
    paid_by_nature: dict[str, float] = {}
    paid_entries_detail: list[dict] = []
    paid_excluded: list[dict] = []
    for e in paid_qs.all():
        nat = e.financial_nature
        try:
            amt = float(e.amount)
        except (TypeError, ValueError):
            continue
        row = {
            "date": (
                e.settled_at.strftime("%d/%m/%Y")
                if e.settled_at
                else (e.due_date.strftime("%d/%m/%Y") if e.due_date else "-")
            ),
            "nature": (nat.name if nat else "-"),
            "amount": amt,
            "excluded_residual": False,
        }
        if nat is not None and getattr(nat, "does_not_consider_residual", False):
            row["excluded_residual"] = True
            paid_excluded.append({"name": nat.name, "amount": amt})
            paid_entries_detail.append(row)
            continue
        paid_total += amt
        if nat:
            paid_by_nature[nat.name] = paid_by_nature.get(nat.name, 0.0) + amt
        paid_entries_detail.append(row)

    net_amount = gross_amount - missing_total - paid_total
    if net_amount <= 0:
        return None, (
            "Valor líquido zero ou negativo após descontar faltas e pagamentos já quitados "
            "no período (do dia 1 do mês até a data de distrato)."
        )
    return (
        {
            "year": year,
            "month": month,
            "month_start": month_start,
            "month_end": month_end,
            "effective_start": eff_start,
            "effective_end": eff_end,
            "effective_days": effective_days,
            "absence_count": sum(1 for a in absences if eff_start <= a.absence_date <= eff_end),
            "has_absences": has_absences,
            "base_bonus": base_bonus,
            "gross_amount": gross_amount,
            "missing_total": missing_total,
            "after_missing": gross_amount - missing_total,
            "paid_total": paid_total,
            "paid_by_nature": [
                {"name": nm, "amount": val}
                for nm, val in sorted(paid_by_nature.items(), key=lambda x: x[0])
            ],
            "paid_entries": paid_entries_detail,
            "paid_excluded_residual_nature": paid_excluded,
            "net_amount": net_amount,
        },
        None,
    )


def compute_motoboy_distrato_net(c: "Contract") -> Tuple[Optional[float], Optional[str]]:
    breakdown, err = compute_motoboy_distrato_breakdown(c)
    if err or not breakdown:
        return None, err
    return float(breakdown.get("net_amount") or 0), None
