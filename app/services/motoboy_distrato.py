"""Cálculo de valores de distrato (adiantamento proporcional e residual proporcional) para contratos de motoboy."""
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


def compute_advance_distrato_net(c: "Contract") -> Tuple[Optional[float], Optional[str]]:
    """
    Mesmas regras do antigo processamento em massa (adiantamento + distrato):
    proporcional aos dias até 15; deduz pagamentos quitados no mês entre dia 1 e 15;
    distrato após dia 15 não gera valor.
    """
    if not c.end_date:
        return None, "Cadastre a data de distrato no contrato antes de gerar o lançamento."
    year, month = c.end_date.year, c.end_date.month
    month_start = date(year, month, 1)
    month_end = _month_end(year, month)
    if not (month_start <= c.end_date <= month_end):
        return None, "Data de distrato fora do mês de referência."

    if c.end_date.day > 15:
        return None, "Distrato após o dia 15: pela regra vigente não gera adiantamento proporcional."

    if not c.advance_value:
        return None, "Contrato sem valor de adiantamento."

    effective_days = min(max(c.end_date.day, 0), 15)
    proportion = effective_days / 15.0 if effective_days > 0 else 0.0
    gross_amount = float(c.advance_value) * proportion if proportion > 0 else 0.0
    if gross_amount <= 0:
        return None, "Valor proporcional de adiantamento é zero."

    period_start = date(year, month, 1)
    period_end = date(year, month, 15)
    paid_qs = (
        FinancialEntry.query.filter(
            FinancialEntry.supplier_id == c.supplier_id,
            FinancialEntry.entry_type == ENTRY_PAYABLE,
            FinancialEntry.settled_at.isnot(None),
        )
        .filter(FinancialEntry.due_date >= period_start)
        .filter(FinancialEntry.due_date <= period_end)
    )
    paid_total = 0.0
    for e in paid_qs.all():
        try:
            paid_total += float(e.amount)
        except (TypeError, ValueError):
            continue
    net_amount = gross_amount - paid_total
    if net_amount <= 0:
        return None, "Valor líquido zero ou negativo após deduzir pagamentos já quitados no período (dias 1–15)."
    return net_amount, None


def compute_residual_distrato_net(c: "Contract") -> Tuple[Optional[float], Optional[str]]:
    """Mesmas regras do antigo residual com distrato no mês (proporcional 30 dias, faltas, pagos no mês)."""
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
    eff_end = min(c.end_date, month_end)
    effective_days = (eff_end - eff_start).days + 1
    if effective_days <= 0:
        return None, "Não há dias efetivos no período para calcular o residual."

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
        return None, "Valor bruto residual proporcional é zero."

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
        .filter(FinancialEntry.due_date <= month_end)
    )
    paid_total = 0.0
    for e in paid_qs.all():
        try:
            paid_total += float(e.amount)
        except (TypeError, ValueError):
            continue

    net_amount = gross_amount - missing_total - paid_total
    if net_amount <= 0:
        return None, "Valor líquido zero ou negativo após descontar faltas e pagamentos quitados no mês."
    return net_amount, None
