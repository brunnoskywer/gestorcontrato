import calendar
from datetime import date, datetime, time

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Company, FinancialEntry, FinancialNature, ENTRY_PAYABLE, ENTRY_RECEIVABLE

main_bp = Blueprint("main", __name__, template_folder="../templates/main")


def _dashboard_month_range(month_param):
    """Return (first_day, last_day, year, month) for the given YYYY-MM or current month."""
    today = date.today()
    if month_param and len(month_param) >= 7:
        try:
            parts = month_param.strip().split("-")
            if len(parts) == 2:
                year, month = int(parts[0]), int(parts[1])
                if 1 <= month <= 12:
                    first = date(year, month, 1)
                    last = date(year, month, calendar.monthrange(year, month)[1])
                    return first, last, year, month
        except (ValueError, IndexError):
            pass
    first = today.replace(day=1)
    last = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    return first, last, today.year, today.month


@main_bp.route("/")
def index():
    return render_template("main/index.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    today = date.today()
    month_param = request.args.get("month", "").strip()
    company_id = request.args.get("company_id", type=int)
    first_day, last_day, year, month = _dashboard_month_range(month_param)
    month_label = f"{year}-{month:02d}"

    companies = Company.query.order_by(Company.legal_name).all()

    def _company_filter(q):
        if company_id:
            return q.filter(FinancialEntry.company_id == company_id)
        return q

    # A receber hoje / A pagar hoje (pendentes, vencimento hoje)
    today_receivable = (
        _company_filter(
            db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0)).filter(
                FinancialEntry.entry_type == ENTRY_RECEIVABLE,
                FinancialEntry.due_date == today,
                FinancialEntry.settled_at.is_(None),
            )
        ).scalar()
    ) or 0
    today_payable = (
        _company_filter(
            db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0)).filter(
                FinancialEntry.entry_type == ENTRY_PAYABLE,
                FinancialEntry.due_date == today,
                FinancialEntry.settled_at.is_(None),
            )
        ).scalar()
    ) or 0

    # Gráficos: apenas lançamentos QUITADOS no mês (due_date no mês e settled_at preenchido)
    days_in_month = last_day.day
    receivables_per_day = [0] * (days_in_month + 1)
    payables_per_day = [0] * (days_in_month + 1)

    rec_rows = (
        _company_filter(
            db.session.query(FinancialEntry.due_date, func.sum(FinancialEntry.amount))
            .filter(
                FinancialEntry.entry_type == ENTRY_RECEIVABLE,
                FinancialEntry.due_date >= first_day,
                FinancialEntry.due_date <= last_day,
                FinancialEntry.settled_at.isnot(None),
            )
            .group_by(FinancialEntry.due_date)
        )
        .all()
    )
    for d, total in rec_rows:
        if d and 1 <= d.day <= days_in_month:
            receivables_per_day[d.day] = float(total)

    pay_rows = (
        _company_filter(
            db.session.query(FinancialEntry.due_date, func.sum(FinancialEntry.amount))
            .filter(
                FinancialEntry.entry_type == ENTRY_PAYABLE,
                FinancialEntry.due_date >= first_day,
                FinancialEntry.due_date <= last_day,
                FinancialEntry.settled_at.isnot(None),
            )
            .group_by(FinancialEntry.due_date)
        )
        .all()
    )
    for d, total in pay_rows:
        if d and 1 <= d.day <= days_in_month:
            payables_per_day[d.day] = float(total)

    # Saldo acumulado por dia (quitados)
    balance_per_day = []
    cum_rec = 0
    cum_pay = 0
    for day in range(1, days_in_month + 1):
        cum_rec += receivables_per_day[day]
        cum_pay += payables_per_day[day]
        balance_per_day.append(round(cum_rec - cum_pay, 2))

    # Totais do mês (quitados) – "Como está no mês"
    month_total_receivable = sum(receivables_per_day[1:])
    month_total_payable = sum(payables_per_day[1:])
    month_balance = round(month_total_receivable - month_total_payable, 2)

    chart_labels = [str(d) for d in range(1, days_in_month + 1)]
    chart_receivables = [receivables_per_day[d] for d in range(1, days_in_month + 1)]
    chart_payables = [payables_per_day[d] for d in range(1, days_in_month + 1)]

    return render_template(
        "main/dashboard.html",
        companies=companies,
        company_id=company_id,
        today_receivable=float(today_receivable),
        today_payable=float(today_payable),
        month_label=month_label,
        month_param=month_param or month_label,
        chart_labels=chart_labels,
        chart_receivables=chart_receivables,
        chart_payables=chart_payables,
        chart_balance=balance_per_day,
        month_total_receivable=month_total_receivable,
        month_total_payable=month_total_payable,
        month_balance=month_balance,
        days_in_month=days_in_month,
        year=year,
        month=month,
    )


@main_bp.route("/dre")
@login_required
def dre():
    """DRE Gerencial: receitas e despesas realizadas (quitadas) no período."""
    month_param = request.args.get("month", "").strip()
    company_id = request.args.get("company_id", type=int)
    first_day, last_day, year, month = _dashboard_month_range(month_param)
    month_label = f"{year}-{month:02d}"
    companies = Company.query.order_by(Company.legal_name).all()

    settled_start = datetime.combine(first_day, time(0, 0, 0))
    settled_end = datetime.combine(last_day, time(23, 59, 59))

    def _company_filter(q):
        if company_id:
            return q.filter(FinancialEntry.company_id == company_id)
        return q

    # Totais realizados no período (quitados)
    total_receitas = (
        _company_filter(
            db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0)).filter(
                FinancialEntry.entry_type == ENTRY_RECEIVABLE,
                FinancialEntry.settled_at >= settled_start,
                FinancialEntry.settled_at <= settled_end,
            )
        ).scalar()
    ) or 0
    total_despesas = (
        _company_filter(
            db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0)).filter(
                FinancialEntry.entry_type == ENTRY_PAYABLE,
                FinancialEntry.settled_at >= settled_start,
                FinancialEntry.settled_at <= settled_end,
            )
        ).scalar()
    ) or 0
    resultado = float(total_receitas) - float(total_despesas)

    # Detalhamento por natureza (receitas)
    rec_por_natureza = (
        _company_filter(
            db.session.query(
                FinancialEntry.financial_nature_id,
                FinancialNature.name,
                func.sum(FinancialEntry.amount).label("total"),
            )
            .join(FinancialNature)
            .filter(
                FinancialEntry.entry_type == ENTRY_RECEIVABLE,
                FinancialEntry.settled_at >= settled_start,
                FinancialEntry.settled_at <= settled_end,
            )
            .group_by(FinancialEntry.financial_nature_id, FinancialNature.name)
        )
        .all()
    )
    # Detalhamento por natureza (despesas)
    pay_por_natureza = (
        _company_filter(
            db.session.query(
                FinancialEntry.financial_nature_id,
                FinancialNature.name,
                func.sum(FinancialEntry.amount).label("total"),
            )
            .join(FinancialNature)
            .filter(
                FinancialEntry.entry_type == ENTRY_PAYABLE,
                FinancialEntry.settled_at >= settled_start,
                FinancialEntry.settled_at <= settled_end,
            )
            .group_by(FinancialEntry.financial_nature_id, FinancialNature.name)
        )
        .all()
    )

    return render_template(
        "main/dre.html",
        companies=companies,
        company_id=company_id,
        month_label=month_label,
        month_param=month_param or month_label,
        total_receitas=float(total_receitas),
        total_despesas=float(total_despesas),
        resultado=resultado,
        rec_por_natureza=rec_por_natureza,
        pay_por_natureza=pay_por_natureza,
    )

