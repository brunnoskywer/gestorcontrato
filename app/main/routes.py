import calendar
from datetime import date, datetime, time, timedelta

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Company,
    Contract,
    FinancialEntry,
    FinancialNature,
    Supplier,
    CONTRACT_TYPE_MOTOBOY,
    ENTRY_PAYABLE,
    ENTRY_RECEIVABLE,
    SUPPLIER_CLIENT,
    SUPPLIER_MOTOBOY,
    SUPPLIER_SUPPLIER,
)
from app.models.supplier import client_display_label

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


def _dashboard_period_range(start_param: str, end_param: str):
    """Return (first_day, last_day) from YYYY-MM-DD inputs; fallback current month."""
    today = date.today()
    default_first = today.replace(day=1)
    default_last = date(
        today.year, today.month, calendar.monthrange(today.year, today.month)[1]
    )
    first = default_first
    last = default_last
    if start_param:
        try:
            first = date.fromisoformat(start_param)
        except ValueError:
            first = default_first
    if end_param:
        try:
            last = date.fromisoformat(end_param)
        except ValueError:
            last = default_last
    if first > last:
        first, last = last, first
    return first, last


def _dre_resolve_client_label_for_entry(
    entry: FinancialEntry, contract_cache: dict[tuple[int, date], str]
) -> str:
    """Resolve cliente relacionado ao lançamento para agrupamento da DRE."""
    supplier = entry.supplier
    if supplier and supplier.type == SUPPLIER_CLIENT:
        return client_display_label(supplier)

    if (
        entry.batch
        and entry.batch.client_supplier
        and entry.batch.client_supplier.type == SUPPLIER_CLIENT
    ):
        return client_display_label(entry.batch.client_supplier)

    if supplier and supplier.type == SUPPLIER_MOTOBOY:
        ref_date = (
            entry.settled_at.date()
            if entry.settled_at
            else (entry.due_date or date.today())
        )
        cache_key = (supplier.id, ref_date)
        if cache_key in contract_cache:
            return contract_cache[cache_key]

        contract = (
            Contract.query.filter(
                Contract.contract_type == CONTRACT_TYPE_MOTOBOY,
                Contract.supplier_id == supplier.id,
                Contract.start_date <= ref_date,
                (Contract.end_date.is_(None)) | (Contract.end_date >= ref_date),
            )
            .order_by(Contract.start_date.desc())
            .first()
        )
        label = (
            client_display_label(contract.other_supplier)
            if contract and contract.other_supplier
            else "Sem cliente vinculado"
        )
        contract_cache[cache_key] = label
        return label

    return "Sem cliente vinculado"


def _dre_third_party_label(entry: FinancialEntry) -> tuple[str, str]:
    supplier = entry.supplier
    if not supplier:
        return "Sem terceiro", "-"
    if supplier.type == SUPPLIER_MOTOBOY:
        return "Motoboy", supplier.name or "-"
    if supplier.type == SUPPLIER_CLIENT:
        return "Cliente", client_display_label(supplier)
    if supplier.type == SUPPLIER_SUPPLIER:
        return "Fornecedor", supplier.name or "-"
    return "Outro", supplier.name or "-"


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
    period_start_param = request.args.get("date_from", "").strip()
    period_end_param = request.args.get("date_to", "").strip()
    company_id = request.args.get("company_id", type=int)
    first_day, last_day = _dashboard_period_range(period_start_param, period_end_param)
    period_label = f"{first_day.strftime('%d/%m/%Y')} a {last_day.strftime('%d/%m/%Y')}"
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
    rec_por_natureza = sorted(rec_por_natureza, key=lambda x: (x.name or "").lower())
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
    pay_por_natureza = sorted(pay_por_natureza, key=lambda x: (x.name or "").lower())

    # Gráficos: composição por natureza (quitados no período)
    chart_rec_labels = [r.name or "Sem natureza" for r in rec_por_natureza]
    chart_rec_values = [float(r.total or 0) for r in rec_por_natureza]
    chart_pay_labels = [p.name or "Sem natureza" for p in pay_por_natureza]
    chart_pay_values = [float(p.total or 0) for p in pay_por_natureza]

    # Gráfico: evolução diária do resultado acumulado (por data de quitação)
    rec_by_day_rows = (
        _company_filter(
            db.session.query(
                func.date(FinancialEntry.settled_at).label("settled_date"),
                func.sum(FinancialEntry.amount).label("total"),
            ).filter(
                FinancialEntry.entry_type == ENTRY_RECEIVABLE,
                FinancialEntry.settled_at >= settled_start,
                FinancialEntry.settled_at <= settled_end,
            )
        )
        .group_by(func.date(FinancialEntry.settled_at))
        .all()
    )
    pay_by_day_rows = (
        _company_filter(
            db.session.query(
                func.date(FinancialEntry.settled_at).label("settled_date"),
                func.sum(FinancialEntry.amount).label("total"),
            ).filter(
                FinancialEntry.entry_type == ENTRY_PAYABLE,
                FinancialEntry.settled_at >= settled_start,
                FinancialEntry.settled_at <= settled_end,
            )
        )
        .group_by(func.date(FinancialEntry.settled_at))
        .all()
    )
    rec_by_day = {d: float(total or 0) for d, total in rec_by_day_rows if d}
    pay_by_day = {d: float(total or 0) for d, total in pay_by_day_rows if d}

    chart_day_labels = []
    chart_day_rec = []
    chart_day_pay = []
    chart_day_balance = []
    running_balance = 0.0
    cur = first_day
    while cur <= last_day:
        rec_val = rec_by_day.get(cur, 0.0)
        pay_val = pay_by_day.get(cur, 0.0)
        running_balance += rec_val - pay_val
        chart_day_labels.append(cur.strftime("%d/%m"))
        chart_day_rec.append(rec_val)
        chart_day_pay.append(pay_val)
        chart_day_balance.append(round(running_balance, 2))
        cur = cur + timedelta(days=1)

    return render_template(
        "main/dre.html",
        companies=companies,
        company_id=company_id,
        period_label=period_label,
        date_from=first_day.isoformat(),
        date_to=last_day.isoformat(),
        total_receitas=float(total_receitas),
        total_despesas=float(total_despesas),
        resultado=resultado,
        rec_por_natureza=rec_por_natureza,
        pay_por_natureza=pay_por_natureza,
        chart_rec_labels=chart_rec_labels,
        chart_rec_values=chart_rec_values,
        chart_pay_labels=chart_pay_labels,
        chart_pay_values=chart_pay_values,
        chart_day_labels=chart_day_labels,
        chart_day_rec=chart_day_rec,
        chart_day_pay=chart_day_pay,
        chart_day_balance=chart_day_balance,
    )


@main_bp.get("/dre/detail")
@login_required
def dre_detail():
    """Detalhamento clicável da DRE por cliente e terceiro."""
    kind = (request.args.get("kind") or "").strip().lower()
    if kind not in ("receitas", "despesas"):
        kind = "receitas"
    entry_type = ENTRY_RECEIVABLE if kind == "receitas" else ENTRY_PAYABLE
    kind_label = "Receitas" if kind == "receitas" else "Despesas"
    color_class = "text-success" if kind == "receitas" else "text-danger"

    period_start_param = request.args.get("date_from", "").strip()
    period_end_param = request.args.get("date_to", "").strip()
    company_id = request.args.get("company_id", type=int)
    nature_id = request.args.get("nature_id", type=int)
    first_day, last_day = _dashboard_period_range(period_start_param, period_end_param)
    settled_start = datetime.combine(first_day, time(0, 0, 0))
    settled_end = datetime.combine(last_day, time(23, 59, 59))
    period_label = f"{first_day.strftime('%d/%m/%Y')} a {last_day.strftime('%d/%m/%Y')}"

    q = (
        FinancialEntry.query.options(
            joinedload(FinancialEntry.supplier),
            joinedload(FinancialEntry.batch),
        )
        .filter(
            FinancialEntry.entry_type == entry_type,
            FinancialEntry.settled_at >= settled_start,
            FinancialEntry.settled_at <= settled_end,
        )
        .order_by(FinancialEntry.settled_at, FinancialEntry.id)
    )
    if company_id:
        q = q.filter(FinancialEntry.company_id == company_id)
    selected_nature_name = None
    if nature_id:
        nature = FinancialNature.query.get(nature_id)
        if nature:
            q = q.filter(FinancialEntry.financial_nature_id == nature_id)
            selected_nature_name = nature.name
    entries = q.all()

    contract_cache: dict[tuple[int, date], str] = {}
    by_client: dict[str, dict] = {}
    for e in entries:
        try:
            amount = float(e.amount or 0)
        except (TypeError, ValueError):
            amount = 0.0
        client_label = _dre_resolve_client_label_for_entry(e, contract_cache)
        third_type, third_name = _dre_third_party_label(e)

        bucket = by_client.setdefault(
            client_label,
            {"client": client_label, "total": 0.0, "thirds": {}},
        )
        bucket["total"] += amount
        third_key = (third_type, third_name)
        thirds = bucket["thirds"]
        if third_key not in thirds:
            thirds[third_key] = {"type": third_type, "name": third_name, "total": 0.0}
        thirds[third_key]["total"] += amount

    details = []
    for _, bucket in sorted(by_client.items(), key=lambda kv: kv[0].lower()):
        thirds_list = sorted(
            bucket["thirds"].values(),
            key=lambda x: (x["type"], x["name"].lower()),
        )
        details.append(
            {
                "client": bucket["client"],
                "total": bucket["total"],
                "thirds": thirds_list,
            }
        )

    grand_total = sum(d["total"] for d in details)
    return render_template(
        "main/_dre_detail_modal_body.html",
        kind=kind,
        kind_label=kind_label,
        color_class=color_class,
        period_label=period_label,
        selected_nature_name=selected_nature_name,
        details=details,
        grand_total=grand_total,
    )

