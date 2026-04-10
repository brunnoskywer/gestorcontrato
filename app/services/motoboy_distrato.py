"""Cálculo de valor de distrato para contratos de motoboy (regra única, proporcional no mês)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Optional, Tuple

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


def compute_motoboy_distrato_net(c: "Contract") -> Tuple[Optional[float], Optional[str]]:
    """
    Proporcional do início do mês (ou do início do contrato, o que for mais tardio) até a data de
    distrato: base mensal = prestação + premiação (premiação zerada se houver falta no mês),
    proporcional em até 30 dias; desconta valor de faltas no período e contas a pagar já quitadas
    com vencimento entre o dia 1 do mês e a data de distrato (inclusive).
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
    base_for_30 = base_service + (0 if has_absences else base_bonus)
    eff_days_30 = min(max(effective_days, 0), 30)
    proportion = eff_days_30 / 30.0 if eff_days_30 > 0 else 0.0
    gross_amount = base_for_30 * proportion
    if gross_amount <= 0:
        return None, "Valor bruto proporcional é zero."

    missing_total = 0.0
    if c.missing_value:
        mv = float(c.missing_value)
        for a in absences:
            if eff_start <= a.absence_date <= eff_end:
                missing_total += mv

    paid_qs = (
        FinancialEntry.query.filter(
            FinancialEntry.supplier_id == c.supplier_id,
            FinancialEntry.entry_type == ENTRY_PAYABLE,
            FinancialEntry.settled_at.isnot(None),
        )
        .filter(FinancialEntry.due_date >= month_start)
        .filter(FinancialEntry.due_date <= eff_end)
    )
    paid_total = 0.0
    for e in paid_qs.all():
        try:
            paid_total += float(e.amount)
        except (TypeError, ValueError):
            continue

    net_amount = gross_amount - missing_total - paid_total
    if net_amount <= 0:
        return None, (
            "Valor líquido zero ou negativo após descontar faltas e pagamentos já quitados "
            "no período (do dia 1 do mês até a data de distrato)."
        )
    return net_amount, None
