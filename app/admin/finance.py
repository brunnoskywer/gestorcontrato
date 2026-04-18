"""Rotas do módulo Financeiro: contas a pagar, a receber, despesa e lançamento manual."""
import calendar as cal
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for, make_response
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.admin.auth_helpers import require_admin, handle_delete_constraint_error, resolve_next_url
from app.extensions import db
from app.models import (
    Account,
    Company,
    FinancialEntry,
    FinancialNature,
    Supplier,
    SUPPLIER_CLIENT,
    SUPPLIER_SUPPLIER,
    SUPPLIER_MOTOBOY,
    ENTRY_PAYABLE,
    ENTRY_RECEIVABLE,
    FinancialBatch,
    BATCH_TYPE_REVENUE,
    BATCH_TYPE_PAYMENT,
    BATCH_TYPE_ADVANCE,
    BATCH_TYPE_RESIDUAL,
    BATCH_TYPE_MOTOBOY_DISTRATO,
    BATCH_TYPE_ADVANCE_DISTRATO,
    BATCH_TYPE_RESIDUAL_DISTRATO,
    Contract,
    CONTRACT_TYPE_CLIENT,
    CONTRACT_TYPE_MOTOBOY,
    ContractAbsence,
    motoboy_supplier_operational,
)
from io import BytesIO

from app.models.supplier import client_display_label
from app.services.motoboy_distrato import contract_has_distrato_in_month

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except ImportError:  # pragma: no cover - depende de pacote externo
    A4 = None
    canvas = None


def _companies_with_accounts():
    return Company.query.order_by(Company.legal_name).all()


def _all_companies():
    return Company.query.order_by(Company.legal_name).all()


def _active_clients():
    return (
        Supplier.query.filter_by(type=SUPPLIER_CLIENT, is_active=True)
        .order_by(func.coalesce(Supplier.trade_name, Supplier.legal_name, Supplier.name))
        .all()
    )


def _financial_natures():
    # Retorna todas as naturezas ativas (payable, receivable e both).
    return FinancialNature.query.filter_by(is_active=True).order_by(FinancialNature.name).all()


def _suggest_charge_date(year: int, month: int) -> date:
    # mês seguinte, dia 5, pulando fim de semana para segunda
    if month == 12:
        y, m = year + 1, 1
    else:
        y, m = year, month + 1
    d = date(y, m, 5)
    if d.weekday() == 5:  # sábado
        d = d + timedelta(days=2)
    elif d.weekday() == 6:  # domingo
        d = d + timedelta(days=1)
    return d


def _manual_entry_redirect():
    return redirect(resolve_next_url("admin.finance_manual_entry"))


def _suggest_advance_charge_date(year: int, month: int) -> date:
    # mesmo mês, dia 20, ajustando para segunda-feira se cair em fim de semana
    d = date(year, month, 20)
    if d.weekday() == 5:  # sábado
        d = d + timedelta(days=2)
    elif d.weekday() == 6:  # domingo
        d = d + timedelta(days=1)
    return d


def register_routes(bp: Blueprint) -> None:
    @bp.route("/financeiro")
    @login_required
    def finance_index():
        """Página inicial do financeiro com links para as seções."""
        require_admin()
        return redirect(url_for("admin.finance_manual_entry"))

    def _accounts_by_company(companies):
        """Map company_id -> list of {id, name} for active accounts (for JS)."""
        return {
            c.id: [{"id": acc.id, "name": acc.name} for acc in c.accounts if acc.is_active]
            for c in companies
        }

    def _all_accounts_for_transfer():
        """List of active accounts with label 'name (company)' for transfer dropdown."""
        accounts = Account.query.filter_by(is_active=True).all()
        accounts.sort(key=lambda a: (a.company.legal_name, a.name))
        return [{"id": a.id, "label": f"{a.name} ({a.company.legal_name})"} for a in accounts]

    @bp.route("/financeiro/lancamento/form")
    @login_required
    def finance_entry_form_new():
        require_admin()
        companies = _companies_with_accounts()
        natures = _financial_natures()
        accounts_by_company = _accounts_by_company(companies)
        return render_template(
            "admin/financeiro/_launch_form_fragment.html",
            companies=companies,
            natures=natures,
            accounts_by_company=accounts_by_company,
            entry=None,
            default_date=date.today().isoformat(),
            action_url=url_for("admin.finance_entry_create"),
        )

    @bp.route("/financeiro/lancamento/<int:entry_id>/form")
    @login_required
    def finance_entry_form_edit(entry_id: int):
        require_admin()
        entry = FinancialEntry.query.get_or_404(entry_id)
        if entry.settled_at:
            flash("Não é possível editar lançamento já quitado. Reabra-o antes.", "warning")
            return _manual_entry_redirect()
        companies = _companies_with_accounts()
        natures = _financial_natures()
        accounts_by_company = _accounts_by_company(companies)
        return render_template(
            "admin/financeiro/_launch_form_fragment.html",
            companies=companies,
            natures=natures,
            accounts_by_company=accounts_by_company,
            entry=entry,
            default_date=date.today().isoformat(),
            action_url=url_for("admin.finance_entry_update", entry_id=entry_id),
        )

    @bp.route("/financeiro/lancamento/<int:entry_id>/update", methods=["POST"])
    @login_required
    def finance_entry_update(entry_id: int):
        require_admin()
        entry = FinancialEntry.query.get_or_404(entry_id)
        if entry.settled_at:
            flash("Não é possível editar lançamento já quitado. Reabra-o antes.", "warning")
            return _manual_entry_redirect()
        entry_type = request.form.get("entry_type")
        if entry_type not in (ENTRY_PAYABLE, ENTRY_RECEIVABLE):
            flash("Tipo de lançamento inválido.", "danger")
            return _manual_entry_redirect()
        return _update_entry(entry)

    @bp.route("/financeiro/lancamento/create", methods=["POST"])
    @login_required
    def finance_entry_create():
        require_admin()
        entry_type = request.form.get("entry_type")
        if entry_type not in (ENTRY_PAYABLE, ENTRY_RECEIVABLE):
            flash("Tipo de lançamento inválido.", "danger")
            return _manual_entry_redirect()
        label = "Conta a pagar" if entry_type == ENTRY_PAYABLE else "Conta a receber"
        return _create_entry(entry_type, "admin.finance_manual_entry", label)

    # ---- Lançamento manual (pagar ou receber) ----
    @bp.route("/financeiro/lancamento-manual")
    @login_required
    def finance_manual_entry():
        require_admin()
        companies = _companies_with_accounts()
        natures = _financial_natures()
        # filtros
        date_from_str = request.args.get("date_from", "").strip()
        date_to_str = request.args.get("date_to", "").strip()
        company_id = request.args.get("company_id", type=int)
        entry_type = request.args.get("entry_type", "").strip()
        supplier_type = request.args.get("supplier_type", "").strip()
        supplier_id = request.args.get("supplier_id", type=int)
        supplier_name = request.args.get("supplier_name", "").strip()
        # Sem "status" na URL (acesso inicial ou Limpar): padrão = só pendentes.
        if "status" not in request.args:
            status = "pending"
        else:
            status = request.args.get("status", "").strip()  # '', pending, settled

        date_from_filter = None
        date_to_filter = None
        if date_from_str:
            try:
                date_from_filter = date.fromisoformat(date_from_str)
            except ValueError:
                pass
        if date_to_str:
            try:
                date_to_filter = date.fromisoformat(date_to_str)
            except ValueError:
                pass
        if not date_from_filter and not date_to_filter:
            # padrão: mês civil corrente (dia 1 ao último dia)
            today = date.today()
            _, last_dom = cal.monthrange(today.year, today.month)
            date_from_filter = today.replace(day=1)
            date_to_filter = today.replace(day=last_dom)
            date_from_str = date_from_filter.isoformat()
            date_to_str = date_to_filter.isoformat()

        query = (
            FinancialEntry.query.options(
                joinedload(FinancialEntry.company),
                joinedload(FinancialEntry.account),
                joinedload(FinancialEntry.financial_nature),
                joinedload(FinancialEntry.supplier),
                joinedload(FinancialEntry.batch),
            ).outerjoin(Supplier)
        )
        if date_from_filter:
            query = query.filter(FinancialEntry.due_date >= date_from_filter)
        if date_to_filter:
            query = query.filter(FinancialEntry.due_date <= date_to_filter)
        if company_id:
            query = query.filter(FinancialEntry.company_id == company_id)
        if entry_type in (ENTRY_PAYABLE, ENTRY_RECEIVABLE):
            query = query.filter(FinancialEntry.entry_type == entry_type)
        if supplier_type in (SUPPLIER_CLIENT, SUPPLIER_SUPPLIER, SUPPLIER_MOTOBOY):
            query = query.filter(Supplier.type == supplier_type)
        if supplier_id:
            query = query.filter(FinancialEntry.supplier_id == supplier_id)
        elif supplier_name:
            query = query.filter(Supplier.name.ilike(f"%{supplier_name}%"))

        supplier_filter_display = supplier_name
        if supplier_id:
            sup_row = Supplier.query.get(supplier_id)
            if sup_row and sup_row.name:
                supplier_filter_display = sup_row.name
        if status == "pending":
            query = query.filter(FinancialEntry.settled_at.is_(None))
        elif status == "settled":
            query = query.filter(FinancialEntry.settled_at.isnot(None))

        entries = query.order_by(
            FinancialEntry.due_date.desc().nullslast(), FinancialEntry.id.desc()
        ).all()
        entries_total = sum(
            (e.amount for e in entries if e.amount is not None),
            Decimal("0"),
        )
        return render_template(
            "admin/financeiro/manual_entry.html",
            companies=companies,
            natures=natures,
            entries=entries,
            entries_total=entries_total,
            supplier_filter_display=supplier_filter_display,
            filters={
                "date_from": date_from_str,
                "date_to": date_to_str,
                "company_id": company_id,
                "entry_type": entry_type,
                "supplier_type": supplier_type,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "status": status,
            },
        )

    @bp.get("/financeiro/lancamento/<int:entry_id>/residual-detalhe.pdf")
    @login_required
    def finance_entry_residual_detail_pdf(entry_id: int):
        require_admin()
        entry = FinancialEntry.query.options(joinedload(FinancialEntry.batch)).get_or_404(entry_id)
        if entry.entry_type != ENTRY_PAYABLE or not entry.processing_snapshot:
            flash(
                "Detalhamento disponível apenas para lançamentos residuais com registro de cálculo.",
                "warning",
            )
            return _manual_entry_redirect()
        if entry.batch is None or entry.batch.batch_type != BATCH_TYPE_RESIDUAL:
            flash("Detalhamento disponível apenas para processamento residual.", "warning")
            return _manual_entry_redirect()
        from app.services.residual_entry_detail_pdf import (
            build_residual_entry_detail_pdf,
            parse_residual_snapshot_json,
        )

        snap = parse_residual_snapshot_json(entry.processing_snapshot)
        if not snap:
            flash("Não foi possível ler o detalhamento deste lançamento.", "danger")
            return _manual_entry_redirect()
        try:
            pdf_bytes = build_residual_entry_detail_pdf(snap)
        except RuntimeError:
            flash("Geração de PDF indisponível: instale o pacote 'reportlab' no ambiente.", "danger")
            return _manual_entry_redirect()
        resp = make_response(pdf_bytes)
        resp.headers["Content-Type"] = "application/pdf"
        resp.headers["Content-Disposition"] = f'attachment; filename="residual_detalhe_{entry.id}.pdf"'
        return resp

    @bp.route("/financeiro/processamentos")
    @login_required
    def finance_batches():
        require_admin()
        date_from_str = request.args.get("date_from", "").strip()
        date_to_str = request.args.get("date_to", "").strip()
        batch_type_filter = request.args.get("batch_type", "").strip().lower()
        next_param = request.args.get("next") or url_for("admin.finance_manual_entry")

        today = date.today()
        first_of_month = today.replace(day=1)
        _, last_day = cal.monthrange(today.year, today.month)
        last_of_month = today.replace(day=last_day)

        date_from = None
        date_to = None
        if date_from_str:
            try:
                date_from = date.fromisoformat(date_from_str)
            except ValueError:
                pass
        if date_to_str:
            try:
                date_to = date.fromisoformat(date_to_str)
            except ValueError:
                pass
        if date_from is None:
            date_from = first_of_month
            date_from_str = first_of_month.isoformat()
        if date_to is None:
            date_to = last_of_month
            date_to_str = last_of_month.isoformat()

        q = FinancialBatch.query
        if batch_type_filter == "revenue":
            q = q.filter(FinancialBatch.batch_type == BATCH_TYPE_REVENUE)
        elif batch_type_filter == "payment":
            q = q.filter(
                FinancialBatch.batch_type.in_(
                    [
                        BATCH_TYPE_PAYMENT,
                        BATCH_TYPE_ADVANCE,
                        BATCH_TYPE_RESIDUAL,
                        BATCH_TYPE_MOTOBOY_DISTRATO,
                        BATCH_TYPE_ADVANCE_DISTRATO,
                        BATCH_TYPE_RESIDUAL_DISTRATO,
                    ]
                )
            )
        elif batch_type_filter == "advance":
            q = q.filter(
                FinancialBatch.batch_type.in_(
                    [BATCH_TYPE_ADVANCE, BATCH_TYPE_ADVANCE_DISTRATO]
                )
            )
        elif batch_type_filter == "residual":
            q = q.filter(
                FinancialBatch.batch_type.in_(
                    [BATCH_TYPE_RESIDUAL, BATCH_TYPE_RESIDUAL_DISTRATO]
                )
            )
        q = q.filter(FinancialBatch.created_at >= datetime.combine(date_from, time.min))
        q = q.filter(FinancialBatch.created_at <= datetime.combine(date_to, time.max))
        batches = q.order_by(FinancialBatch.created_at.desc()).all()

        return render_template(
            "admin/financeiro/_batches_modal.html",
            batches=batches,
            filters={"date_from": date_from_str, "date_to": date_to_str, "batch_type": batch_type_filter},
            next_url=next_param,
        )

    @bp.route("/financeiro/receitas/processamentos")
    @login_required
    def finance_revenue_batches():
        """Redireciona para o modal unificado com filtro de receitas."""
        args = {k: v for k, v in request.args.items() if v}
        args.setdefault("batch_type", "revenue")
        return redirect(url_for("admin.finance_batches", **args))

    @bp.route("/financeiro/receitas/processar/form")
    @login_required
    def finance_revenue_process_form():
        require_admin()
        next_url = request.args.get("next") or url_for("admin.finance_manual_entry")
        today = date.today()
        default_year = today.year
        default_month = today.month
        suggested_charge_date = _suggest_charge_date(default_year, default_month)
        return render_template(
            "admin/financeiro/_revenue_process_form_fragment.html",
            default_year=default_year,
            default_month=default_month,
            suggested_charge_date=suggested_charge_date.isoformat(),
            clients=_active_clients(),
            companies=_all_companies(),
            action_url=url_for("admin.finance_revenue_process"),
            next_url=next_url,
        )

    @bp.post("/financeiro/receitas/processar")
    @login_required
    def finance_revenue_process():
        require_admin()
        next_url = resolve_next_url("admin.finance_manual_entry")
        year = request.form.get("year", type=int)
        month = request.form.get("month", type=int)
        charge_date_str = request.form.get("charge_date", "").strip()
        client_supplier_id = request.form.get("client_supplier_id", type=int)
        company_id_override = request.form.get("company_id", type=int)

        if not year or not month or not charge_date_str:
            flash("Ano, mês e data de cobrança são obrigatórios.", "danger")
            return redirect(next_url)
        if not client_supplier_id and not company_id_override:
            flash("Informe pelo menos um Cliente ou uma Empresa para processar.", "danger")
            return redirect(next_url)

        try:
            charge_date = date.fromisoformat(charge_date_str)
        except ValueError:
            flash("Data de cobrança inválida.", "danger")
            return redirect(next_url)

        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        existing = FinancialBatch.query.filter_by(
            batch_type=BATCH_TYPE_REVENUE,
            year=year,
            month=month,
            client_supplier_id=client_supplier_id,
            company_id=company_id_override,
        ).first()
        if existing:
            flash("Já existe um processamento de receitas para este mês/ano.", "warning")
            return redirect(next_url)

        contracts = (
            Contract.query.filter(Contract.contract_type == CONTRACT_TYPE_CLIENT)
            .filter(Contract.start_date <= month_end)
            .filter((Contract.end_date.is_(None)) | (Contract.end_date >= month_start))
        )
        if client_supplier_id:
            contracts = contracts.filter(Contract.supplier_id == client_supplier_id)
        contracts = contracts.all()

        created = 0
        skipped_no_company = 0
        skipped_no_nature = 0
        skipped_zero_amount = 0
        batch = None

        for c in contracts:
            # Natureza vem do cadastro do contrato do cliente
            nature = c.revenue_financial_nature if c.revenue_financial_nature_id else None
            if not nature or not nature.is_active or nature.kind not in ("receivable", "both"):
                skipped_no_nature += 1
                continue
            # Usar a empresa associada ao cliente para emissão de nota (billing_company_id)
            company_id = company_id_override
            if company_id is None and c.supplier and c.supplier.billing_company_id:
                company_id = c.supplier.billing_company_id
            if company_id is None:
                skipped_no_company += 1
                continue

            if batch is None:
                batch = FinancialBatch(
                    batch_type=BATCH_TYPE_REVENUE,
                    year=year,
                    month=month,
                    financial_nature_id=nature.id,
                    charge_date=charge_date,
                    company_id=company_id_override,
                    client_supplier_id=client_supplier_id,
                    created_by_id=getattr(current_user, "id", None),
                )
                db.session.add(batch)
                db.session.flush()

            eff_start = max(c.start_date, month_start)
            eff_end = min(c.end_date or month_end, month_end)
            days_in_month = (month_end - month_start).days + 1
            effective_days = (eff_end - eff_start).days + 1
            proportion = effective_days / days_in_month if days_in_month > 0 else 1
            motoboy_qty = int(c.motoboy_quantity) if c.motoboy_quantity is not None else 1
            cv = float(c.contract_value or 0)
            drv_q = int(c.client_driver_quantity or 0)
            drv_u = float(c.client_driver_unit_value or 0)
            oth_q = int(c.client_other_quantity or 0)
            oth_u = float(c.client_other_unit_value or 0)
            base_line = cv * motoboy_qty * proportion
            extras = (drv_u * drv_q + oth_u * oth_q) * proportion
            reimburse = float(c.client_absence_reimburse_unit_value or 0)
            d0 = max(month_start, eff_start)
            d1 = min(month_end, eff_end)
            no_sub = (
                db.session.query(func.count(ContractAbsence.id))
                .join(Contract, ContractAbsence.contract_id == Contract.id)
                .filter(
                    Contract.contract_type == CONTRACT_TYPE_MOTOBOY,
                    Contract.other_supplier_id == c.supplier_id,
                    ContractAbsence.absence_date >= d0,
                    ContractAbsence.absence_date <= d1,
                    ContractAbsence.substitute_supplier_id.is_(None),
                )
                .scalar()
            ) or 0
            discount_abs = float(no_sub) * reimburse
            amount = base_line + extras - discount_abs
            if amount <= 0:
                skipped_zero_amount += 1
                continue

            entry = FinancialEntry(
                company_id=company_id,
                account_id=None,
                financial_nature_id=nature.id,
                supplier_id=c.supplier_id,
                entry_type=ENTRY_RECEIVABLE,
                description=f"Receita contrato cliente #{c.id} - {year}-{month:02d}",
                amount=amount,
                due_date=charge_date,
                settled_at=None,
                reference=None,
                financial_batch_id=batch.id,
            )
            db.session.add(entry)
            created += 1

        if created == 0:
            db.session.rollback()
            if skipped_no_nature and not skipped_no_company:
                flash("Nenhuma receita gerada: defina a natureza financeira de receita no cadastro de cada contrato de cliente.", "warning")
            elif skipped_no_company:
                flash("Nenhuma receita gerada: os clientes dos contratos precisam ter uma empresa associada para emissão de nota (cadastro do cliente).", "warning")
            elif skipped_zero_amount:
                flash(
                    "Nenhuma receita gerada: valor líquido zerado ou negativo após extras e descontos por falta sem substituto.",
                    "warning",
                )
            else:
                flash("Nenhuma receita foi gerada para os contratos vigentes no período.", "warning")
        else:
            db.session.commit()
            msg = f"{created} lançamento(s) de receita gerado(s)."
            if skipped_no_company:
                msg += f" {skipped_no_company} contrato(s) ignorado(s): cliente sem empresa para emissão de nota."
            if skipped_no_nature:
                msg += f" {skipped_no_nature} contrato(s) ignorado(s): sem natureza financeira de receita."
            if skipped_zero_amount:
                msg += (
                    f" {skipped_zero_amount} contrato(s) ignorado(s): valor líquido da receita "
                    "zerado ou negativo."
                )
            flash(msg, "success" if not (skipped_no_company or skipped_no_nature) else "warning")

        return redirect(next_url)

    @bp.post("/financeiro/processamentos/<int:batch_id>/delete")
    @login_required
    def finance_batch_delete(batch_id: int):
        require_admin()
        next_url = resolve_next_url("admin.finance_manual_entry")
        batch = FinancialBatch.query.get_or_404(batch_id)
        any_settled = (
            FinancialEntry.query.filter_by(financial_batch_id=batch.id)
            .filter(FinancialEntry.settled_at.isnot(None))
            .first()
        )
        if any_settled:
            flash("Não é possível excluir: existem lançamentos quitados neste processamento.", "danger")
            return redirect(next_url)
        FinancialEntry.query.filter_by(financial_batch_id=batch.id).delete(synchronize_session=False)
        db.session.delete(batch)
        db.session.commit()
        tipo = "receita" if batch.batch_type == BATCH_TYPE_REVENUE else "pagamento"
        flash(f"Processamento de {tipo} excluído com seus lançamentos pendentes.", "info")
        return redirect(next_url)

    @bp.post("/financeiro/receitas/processamentos/<int:batch_id>/delete")
    @login_required
    def finance_revenue_batch_delete(batch_id: int):
        """Compatibilidade: mesma lógica de exclusão."""
        return finance_batch_delete(batch_id)

    @bp.route("/financeiro/pagamentos/processar/form")
    @login_required
    def finance_payment_process_form():
        require_admin()
        next_url = request.args.get("next") or url_for("admin.finance_manual_entry")
        today = date.today()
        default_year = today.year
        default_month = today.month
        suggested_charge_date = _suggest_charge_date(default_year, default_month)
        return render_template(
            "admin/financeiro/_payment_process_form_fragment.html",
            default_year=default_year,
            default_month=default_month,
            suggested_charge_date=suggested_charge_date.isoformat(),
            action_url=url_for("admin.finance_payment_process"),
            next_url=next_url,
        )

    @bp.post("/financeiro/pagamentos/processar")
    @login_required
    def finance_payment_process():
        require_admin()
        next_url = resolve_next_url("admin.finance_manual_entry")
        year = request.form.get("year", type=int)
        month = request.form.get("month", type=int)
        charge_date_str = request.form.get("charge_date", "").strip()
        if not year or not month or not charge_date_str:
            flash("Ano, mês e data de cobrança são obrigatórios.", "danger")
            return redirect(next_url)
        try:
            charge_date = date.fromisoformat(charge_date_str)
        except ValueError:
            flash("Data de cobrança inválida.", "danger")
            return redirect(next_url)
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)
        existing = FinancialBatch.query.filter_by(
            batch_type=BATCH_TYPE_PAYMENT,
            year=year,
            month=month,
        ).first()
        if existing:
            flash("Já existe um processamento de pagamentos para este mês/ano.", "warning")
            return redirect(next_url)
        nature = (
            FinancialNature.query.filter(
                FinancialNature.is_active.is_(True),
                FinancialNature.kind.in_(["payable", "both"]),
            )
            .order_by(FinancialNature.name)
            .first()
        )
        if not nature:
            flash("Cadastre uma natureza financeira do tipo 'Contas a pagar' ou 'Ambas' para processar pagamentos.", "danger")
            return redirect(next_url)
        batch = FinancialBatch(
            batch_type=BATCH_TYPE_PAYMENT,
            year=year,
            month=month,
            financial_nature_id=nature.id,
            charge_date=charge_date,
            created_by_id=getattr(current_user, "id", None),
        )
        db.session.add(batch)
        db.session.commit()
        flash("Processamento de pagamentos criado. Em breve os lançamentos serão gerados a partir dos contratos de motoboy.", "success")
        return redirect(next_url)

    @bp.route("/financeiro/adiantamentos/processar/form")
    @login_required
    def finance_advance_process_form():
        require_admin()
        next_url = request.args.get("next") or url_for("admin.finance_manual_entry")
        today = date.today()
        default_year = today.year
        default_month = today.month
        suggested_charge_date = _suggest_advance_charge_date(default_year, default_month)
        natures = (
            FinancialNature.query.filter(
                FinancialNature.is_active.is_(True),
                FinancialNature.kind.in_(["payable", "both"]),
            )
            .order_by(FinancialNature.name)
            .all()
        )
        return render_template(
            "admin/financeiro/_advance_process_form_fragment.html",
            default_year=default_year,
            default_month=default_month,
            suggested_charge_date=suggested_charge_date.isoformat(),
            natures=natures,
            clients=_active_clients(),
            companies=_all_companies(),
            action_url=url_for("admin.finance_advance_process"),
            next_url=next_url,
        )

    @bp.post("/financeiro/adiantamentos/processar")
    @login_required
    def finance_advance_process():
        require_admin()
        next_url = resolve_next_url("admin.finance_manual_entry")
        year = request.form.get("year", type=int)
        month = request.form.get("month", type=int)
        charge_date_str = request.form.get("charge_date", "").strip()
        advance_nature_id = request.form.get("advance_nature_id", type=int)
        client_supplier_id = request.form.get("client_supplier_id", type=int)
        company_id_override = request.form.get("company_id", type=int)

        if not year or not month or not charge_date_str or not advance_nature_id:
            flash("Ano, mês, data de cobrança e natureza de adiantamento são obrigatórios.", "danger")
            return redirect(next_url)
        if not client_supplier_id and not company_id_override:
            flash("Informe pelo menos um Cliente ou uma Empresa para processar.", "danger")
            return redirect(next_url)

        try:
            charge_date = date.fromisoformat(charge_date_str)
        except ValueError:
            flash("Data de cobrança inválida.", "danger")
            return redirect(next_url)

        adv_nature = FinancialNature.query.get(advance_nature_id)
        if (
            not adv_nature
            or not adv_nature.is_active
            or adv_nature.kind not in ("payable", "both")
        ):
            flash("Natureza financeira deve ser ativa e do tipo 'Contas a pagar' ou 'Ambas'.", "danger")
            return redirect(next_url)

        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        contracts = (
            Contract.query.filter(Contract.contract_type == CONTRACT_TYPE_MOTOBOY)
            .filter(Contract.start_date <= month_end)
            .filter((Contract.end_date.is_(None)) | (Contract.end_date >= month_start))
        )
        if client_supplier_id:
            contracts = contracts.filter(Contract.other_supplier_id == client_supplier_id)
        contracts = contracts.all()

        if not contracts:
            flash("Nenhum contrato de motoboy ativo no período selecionado.", "warning")
            return redirect(next_url)

        existing_adv = FinancialBatch.query.filter_by(
            batch_type=BATCH_TYPE_ADVANCE,
            year=year,
            month=month,
            financial_nature_id=advance_nature_id,
            client_supplier_id=client_supplier_id,
            company_id=company_id_override,
        ).first()
        if existing_adv:
            flash("Já existe um processamento de adiantamentos para este mês/naturezas.", "warning")
            return redirect(next_url)

        batch_adv = None
        created_adv = 0
        skipped_no_company = 0
        skipped_no_advance_value = 0
        skipped_motoboy_encerrado = 0
        skipped_distrato_no_mes = 0

        for c in contracts:
            if contract_has_distrato_in_month(c, year, month):
                skipped_distrato_no_mes += 1
                continue
            if c.supplier and not motoboy_supplier_operational(c.supplier):
                skipped_motoboy_encerrado += 1
                continue
            if not c.advance_value:
                skipped_no_advance_value += 1
                continue

            company_id = company_id_override
            if company_id is None and c.other_supplier and c.other_supplier.billing_company_id:
                company_id = c.other_supplier.billing_company_id
            elif company_id is None and c.supplier and c.supplier.billing_company_id:
                company_id = c.supplier.billing_company_id
            if company_id is None:
                skipped_no_company += 1
                continue

            amount = float(c.advance_value)

            if batch_adv is None:
                batch_adv = FinancialBatch(
                    batch_type=BATCH_TYPE_ADVANCE,
                    year=year,
                    month=month,
                    financial_nature_id=advance_nature_id,
                    charge_date=charge_date,
                    company_id=company_id_override,
                    client_supplier_id=client_supplier_id,
                    created_by_id=getattr(current_user, "id", None),
                )
                db.session.add(batch_adv)
                db.session.flush()

            desc = f"Adiantamento contrato motoboy #{c.id} - {year}-{month:02d}"
            entry = FinancialEntry(
                company_id=company_id,
                account_id=None,
                financial_nature_id=batch_adv.financial_nature_id,
                supplier_id=c.supplier_id,
                entry_type=ENTRY_PAYABLE,
                description=desc,
                amount=amount,
                due_date=charge_date,
                settled_at=None,
                reference=None,
                financial_batch_id=batch_adv.id,
            )
            db.session.add(entry)
            created_adv += 1

        db.session.commit()

        msg_parts = []
        if created_adv:
            msg_parts.append(f"{created_adv} lançamento(s) de adiantamento criado(s).")
        if skipped_no_advance_value:
            msg_parts.append(f"{skipped_no_advance_value} contrato(s) sem valor de adiantamento foram ignorados.")
        if skipped_no_company:
            msg_parts.append(f"{skipped_no_company} contrato(s) sem empresa de cobrança foram ignorados.")
        if skipped_distrato_no_mes:
            msg_parts.append(
                f"{skipped_distrato_no_mes} contrato(s) com distrato no mês foram ignorados — use Gerar distrato no contrato."
            )
        if skipped_motoboy_encerrado:
            msg_parts.append(
                f"{skipped_motoboy_encerrado} contrato(s) ignorados: motoboy encerrado no cadastro."
            )

        if not msg_parts:
            flash("Nenhum lançamento de adiantamento foi gerado.", "warning")
        else:
            flash(" ".join(msg_parts), "success")

        return redirect(next_url)

    @bp.route("/financeiro/residual/processar/form")
    @login_required
    def finance_residual_process_form():
        require_admin()
        next_url = request.args.get("next") or url_for("admin.finance_manual_entry")
        today = date.today()
        default_year = today.year
        default_month = today.month
        suggested_charge_date = _suggest_charge_date(default_year, default_month)
        natures = (
            FinancialNature.query.filter(
                FinancialNature.is_active.is_(True),
                FinancialNature.kind.in_(["payable", "both"]),
            )
            .order_by(FinancialNature.name)
            .all()
        )
        return render_template(
            "admin/financeiro/_residual_process_form_fragment.html",
            default_year=default_year,
            default_month=default_month,
            suggested_charge_date=suggested_charge_date.isoformat(),
            natures=natures,
            clients=_active_clients(),
            companies=_all_companies(),
            action_url=url_for("admin.finance_residual_process"),
            next_url=next_url,
        )

    @bp.post("/financeiro/residual/processar")
    @login_required
    def finance_residual_process():
        require_admin()
        next_url = resolve_next_url("admin.finance_manual_entry")
        year = request.form.get("year", type=int)
        month = request.form.get("month", type=int)
        charge_date_str = request.form.get("charge_date", "").strip()
        residual_nature_id = request.form.get("residual_nature_id", type=int)
        client_supplier_id = request.form.get("client_supplier_id", type=int)
        company_id_override = request.form.get("company_id", type=int)

        if not year or not month or not charge_date_str or not residual_nature_id:
            flash("Ano, mês, data de cobrança e natureza residual são obrigatórios.", "danger")
            return redirect(next_url)
        if not client_supplier_id and not company_id_override:
            flash("Informe pelo menos um Cliente ou uma Empresa para processar.", "danger")
            return redirect(next_url)

        try:
            charge_date = date.fromisoformat(charge_date_str)
        except ValueError:
            flash("Data de cobrança inválida.", "danger")
            return redirect(next_url)

        res_nature = FinancialNature.query.get(residual_nature_id)
        if (
            not res_nature
            or not res_nature.is_active
            or res_nature.kind not in ("payable", "both")
        ):
            flash("Natureza financeira deve ser ativa e do tipo 'Contas a pagar' ou 'Ambas'.", "danger")
            return redirect(next_url)

        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        contracts = (
            Contract.query.filter(Contract.contract_type == CONTRACT_TYPE_MOTOBOY)
            .filter(Contract.start_date <= month_end)
            .filter((Contract.end_date.is_(None)) | (Contract.end_date >= month_start))
        )
        if client_supplier_id:
            contracts = contracts.filter(Contract.other_supplier_id == client_supplier_id)
        contracts = contracts.all()

        if not contracts:
            flash("Nenhum contrato de motoboy ativo no período selecionado.", "warning")
            return redirect(next_url)

        existing_res = FinancialBatch.query.filter_by(
            batch_type=BATCH_TYPE_RESIDUAL,
            year=year,
            month=month,
            financial_nature_id=residual_nature_id,
            client_supplier_id=client_supplier_id,
            company_id=company_id_override,
        ).first()
        if existing_res:
            flash("Já existe um processamento residual para este mês/naturezas.", "warning")
            return redirect(next_url)

        batch_res = None
        created_res = 0
        skipped_no_company = 0
        skipped_no_base = 0
        skipped_fully_paid = 0
        skipped_motoboy_encerrado = 0
        skipped_distrato_no_mes = 0

        for c in contracts:
            if contract_has_distrato_in_month(c, year, month):
                skipped_distrato_no_mes += 1
                continue
            if c.supplier and not motoboy_supplier_operational(c.supplier):
                skipped_motoboy_encerrado += 1
                continue
            base_service = float(c.service_value or 0)
            base_bonus = float(c.bonus_value or 0)
            if base_service <= 0 and base_bonus <= 0:
                skipped_no_base += 1
                continue

            company_id = company_id_override
            if company_id is None and c.other_supplier and c.other_supplier.billing_company_id:
                company_id = c.other_supplier.billing_company_id
            elif company_id is None and c.supplier and c.supplier.billing_company_id:
                company_id = c.supplier.billing_company_id
            if company_id is None:
                skipped_no_company += 1
                continue

            eff_start = max(c.start_date, month_start)
            eff_end = min(c.end_date or month_end, month_end)
            effective_days = (eff_end - eff_start).days + 1
            if effective_days <= 0:
                skipped_no_base += 1
                continue

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
            gross_amount = base_total
            if gross_amount <= 0:
                skipped_no_base += 1
                continue

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
                .filter(FinancialEntry.due_date <= month_end)
            )
            paid_total = 0.0
            paid_by_nature: dict[str, float] = {}
            paid_excluded: list[dict] = []
            for e in paid_qs.all():
                try:
                    amt = float(e.amount)
                except (TypeError, ValueError):
                    continue
                nat = e.financial_nature
                if nat is not None and getattr(nat, "does_not_consider_residual", False):
                    paid_excluded.append({"name": nat.name, "amount": amt})
                    continue
                paid_total += amt
                if nat:
                    paid_by_nature[nat.name] = paid_by_nature.get(nat.name, 0.0) + amt

            net_amount = gross_amount - missing_total - paid_total
            if net_amount <= 0:
                skipped_fully_paid += 1
                continue

            if batch_res is None:
                batch_res = FinancialBatch(
                    batch_type=BATCH_TYPE_RESIDUAL,
                    year=year,
                    month=month,
                    financial_nature_id=residual_nature_id,
                    charge_date=charge_date,
                    company_id=company_id_override,
                    client_supplier_id=client_supplier_id,
                    created_by_id=getattr(current_user, "id", None),
                )
                db.session.add(batch_res)
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
            after_missing = gross_amount - missing_total
            snapshot = {
                "v": 1,
                "contract_id": c.id,
                "motoboy_name": (c.supplier.name if c.supplier else "") or "-",
                "client_name": client_display_label(c.other_supplier) if c.other_supplier else "-",
                "period_label": f"{_meses[month]} de {year}",
                "gross_amount": gross_amount,
                "has_absences": has_absences,
                "missing_total": missing_total,
                "after_missing": after_missing,
                "paid_total": paid_total,
                "paid_by_nature": [
                    {"name": nm, "amount": val}
                    for nm, val in sorted(paid_by_nature.items(), key=lambda x: x[0])
                ],
                "paid_excluded_residual_nature": paid_excluded,
                "net_amount": net_amount,
            }

            desc = f"Residual contrato motoboy #{c.id} - {year}-{month:02d}"
            entry = FinancialEntry(
                company_id=company_id,
                account_id=None,
                financial_nature_id=batch_res.financial_nature_id,
                supplier_id=c.supplier_id,
                entry_type=ENTRY_PAYABLE,
                description=desc,
                amount=net_amount,
                due_date=charge_date,
                settled_at=None,
                reference=None,
                financial_batch_id=batch_res.id,
                processing_snapshot=json.dumps(snapshot, ensure_ascii=False),
            )
            db.session.add(entry)
            created_res += 1

        db.session.commit()

        msg_parts = []
        if created_res:
            msg_parts.append(f"{created_res} lançamento(s) residuais criado(s).")
        if skipped_no_base:
            msg_parts.append(f"{skipped_no_base} contrato(s) sem base de valor foram ignorados.")
        if skipped_no_company:
            msg_parts.append(f"{skipped_no_company} contrato(s) sem empresa de cobrança foram ignorados.")
        if skipped_fully_paid:
            msg_parts.append(f"{skipped_fully_paid} contrato(s) já totalmente pagos no mês foram ignorados.")
        if skipped_distrato_no_mes:
            msg_parts.append(
                f"{skipped_distrato_no_mes} contrato(s) com distrato no mês foram ignorados — use Gerar distrato no contrato."
            )
        if skipped_motoboy_encerrado:
            msg_parts.append(
                f"{skipped_motoboy_encerrado} contrato(s) ignorados: motoboy encerrado no cadastro."
            )

        if not msg_parts:
            flash("Nenhum lançamento residual foi gerado.", "warning")
        else:
            flash(" ".join(msg_parts), "success")

        return redirect(next_url)

    # ---- Aprovar (definir data de baixa) ----
    @bp.route("/financeiro/lancamento/<int:entry_id>/aprovar/form")
    @login_required
    def finance_approve_entry_form(entry_id: int):
        require_admin()
        entry = FinancialEntry.query.get_or_404(entry_id)
        if entry.settled_at:
            flash("Lançamento já quitado.", "warning")
            return _manual_entry_redirect()
        next_url = resolve_next_url("admin.finance_manual_entry")
        return render_template(
            "admin/financeiro/_approve_form_fragment.html",
            entry=entry,
            action_url=url_for("admin.finance_approve_entry", entry_id=entry_id),
            next_url=next_url,
            default_date=date.today().isoformat(),
        )

    @bp.route("/financeiro/lancamento/aprovar-lote/form")
    @login_required
    def finance_approve_bulk_form():
        require_admin()
        next_url = resolve_next_url("admin.finance_manual_entry")
        ids = request.args.getlist("ids", type=int)
        if not ids:
            flash("Selecione um ou mais lançamentos pendentes para aprovar.", "warning")
            return redirect(next_url)
        entries = (
            FinancialEntry.query.filter(FinancialEntry.id.in_(ids))
            .order_by(FinancialEntry.due_date, FinancialEntry.id)
            .all()
        )
        if not entries:
            flash("Nenhum lançamento válido encontrado para aprovação em lote.", "warning")
            return redirect(next_url)
        if any(e.settled_at for e in entries):
            flash("Todos os lançamentos selecionados para aprovação em lote devem estar pendentes.", "danger")
            return redirect(next_url)
        active_accounts = Account.query.filter_by(is_active=True).order_by(Account.name).all()
        return render_template(
            "admin/financeiro/_approve_bulk_form_fragment.html",
            ids=[e.id for e in entries],
            entries_count=len(entries),
            accounts=active_accounts,
            action_url=url_for("admin.finance_approve_bulk"),
            next_url=next_url,
            default_date=date.today().isoformat(),
        )

    @bp.post("/financeiro/lancamento/<int:entry_id>/aprovar")
    @login_required
    def finance_approve_entry(entry_id: int):
        require_admin()
        entry = FinancialEntry.query.get_or_404(entry_id)
        settled_date_str = request.form.get("settled_date", "").strip()
        if not settled_date_str:
            flash("Data de baixa é obrigatória.", "danger")
            return _manual_entry_redirect()
        try:
            settled_date = date.fromisoformat(settled_date_str)
        except ValueError:
            flash("Data de baixa inválida.", "danger")
            return _manual_entry_redirect()
        account_id = request.form.get("account_id", "").strip()
        if not account_id:
            flash("Conta é obrigatória para dar baixa.", "danger")
            return _manual_entry_redirect()
        try:
            aid = int(account_id)
        except (ValueError, TypeError):
            flash("Conta inválida.", "danger")
            return _manual_entry_redirect()
        acc = Account.query.get(aid)
        if not acc or not acc.is_active or acc.company_id != entry.company_id:
            flash("Conta inválida para a empresa do lançamento.", "danger")
            return _manual_entry_redirect()
        entry.settled_at = datetime.combine(settled_date, time(0, 0))
        entry.account_id = aid
        db.session.commit()
        flash("Lançamento aprovado (quitado).", "success")
        return _manual_entry_redirect()

    @bp.post("/financeiro/lancamento/aprovar-lote")
    @login_required
    def finance_approve_bulk():
        require_admin()
        next_url = resolve_next_url("admin.finance_manual_entry")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhum lançamento selecionado.", "warning")
            return redirect(next_url)

        settled_date_str = request.form.get("settled_date", "").strip()
        if not settled_date_str:
            flash("Data de baixa é obrigatória.", "danger")
            return redirect(next_url)
        try:
            settled_date = date.fromisoformat(settled_date_str)
        except ValueError:
            flash("Data de baixa inválida.", "danger")
            return redirect(next_url)

        entries = (
            FinancialEntry.query.filter(FinancialEntry.id.in_(ids))
            .order_by(FinancialEntry.id)
            .all()
        )
        if not entries:
            flash("Nenhum lançamento válido encontrado.", "warning")
            return redirect(next_url)
        if len(entries) != len(set(ids)):
            flash("Há lançamento(s) inválido(s) na seleção.", "danger")
            return redirect(next_url)
        if any(e.settled_at for e in entries):
            flash("Todos os lançamentos selecionados devem estar pendentes para baixa em lote.", "danger")
            return redirect(next_url)

        account_id_raw = (request.form.get("account_id") or "").strip()
        if not account_id_raw:
            flash("Conta é obrigatória para dar baixa em lote.", "danger")
            return redirect(next_url)
        try:
            aid = int(account_id_raw)
        except (ValueError, TypeError):
            flash("Conta inválida.", "danger")
            return redirect(next_url)
        chosen_account = Account.query.get(aid)
        if not chosen_account or not chosen_account.is_active:
            flash("Conta inválida ou inativa.", "danger")
            return redirect(next_url)
        incompatible = [e.id for e in entries if e.company_id != chosen_account.company_id]
        if incompatible:
            flash(
                "A conta selecionada não pertence à mesma empresa de todos os lançamentos.",
                "danger",
            )
            return redirect(next_url)

        settled_at = datetime.combine(settled_date, time(0, 0))
        for entry in entries:
            entry.settled_at = settled_at
            entry.account_id = chosen_account.id

        db.session.commit()
        flash(f"{len(entries)} lançamento(s) aprovado(s) em lote.", "success")
        return redirect(next_url)

    @bp.route("/financeiro/lancamento/alterar-lote/form")
    @login_required
    def finance_bulk_update_form():
        require_admin()
        next_url = resolve_next_url("admin.finance_manual_entry")
        ids = request.args.getlist("ids", type=int)
        if not ids:
            flash("Selecione um ou mais lançamentos para alterar em massa.", "warning")
            return redirect(next_url)
        entries = (
            FinancialEntry.query.filter(FinancialEntry.id.in_(ids))
            .order_by(FinancialEntry.due_date, FinancialEntry.id)
            .all()
        )
        if not entries:
            flash("Nenhum lançamento válido encontrado.", "warning")
            return redirect(next_url)
        if any(e.settled_at for e in entries):
            flash("A alteração em massa só pode ser aplicada em lançamentos pendentes.", "danger")
            return redirect(next_url)
        companies = Company.query.order_by(Company.legal_name).all()
        accounts = Account.query.filter_by(is_active=True).order_by(Account.name).all()
        accounts_by_company = {}
        for acc in accounts:
            if not acc.company_id:
                continue
            key = str(acc.company_id)
            accounts_by_company.setdefault(key, []).append(
                {"id": acc.id, "name": acc.name}
            )
        return render_template(
            "admin/financeiro/_bulk_update_form_fragment.html",
            ids=[e.id for e in entries],
            entries_count=len(entries),
            companies=companies,
            accounts_by_company=accounts_by_company,
            action_url=url_for("admin.finance_bulk_update_apply"),
            next_url=next_url,
        )

    @bp.post("/financeiro/lancamento/alterar-lote")
    @login_required
    def finance_bulk_update_apply():
        require_admin()
        next_url = resolve_next_url("admin.finance_manual_entry")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhum lançamento selecionado.", "warning")
            return redirect(next_url)
        entries = (
            FinancialEntry.query.filter(FinancialEntry.id.in_(ids))
            .order_by(FinancialEntry.id)
            .all()
        )
        if not entries:
            flash("Nenhum lançamento válido encontrado.", "warning")
            return redirect(next_url)
        if len(entries) != len(set(ids)):
            flash("Há lançamento(s) inválido(s) na seleção.", "danger")
            return redirect(next_url)
        if any(e.settled_at for e in entries):
            flash("A alteração em massa só pode ser aplicada em lançamentos pendentes.", "danger")
            return redirect(next_url)

        company_id_raw = (request.form.get("company_id") or "").strip()
        due_date_raw = (request.form.get("due_date") or "").strip()
        account_id_raw = (request.form.get("account_id") or "").strip()

        chosen_company = None
        if company_id_raw:
            try:
                cid = int(company_id_raw)
            except (ValueError, TypeError):
                flash("Empresa inválida.", "danger")
                return redirect(next_url)
            chosen_company = Company.query.get(cid)
            if not chosen_company:
                flash("Empresa inválida.", "danger")
                return redirect(next_url)

        chosen_due_date = None
        if due_date_raw:
            try:
                chosen_due_date = date.fromisoformat(due_date_raw)
            except ValueError:
                flash("Data inválida.", "danger")
                return redirect(next_url)

        chosen_account = None
        if account_id_raw:
            try:
                aid = int(account_id_raw)
            except (ValueError, TypeError):
                flash("Conta inválida.", "danger")
                return redirect(next_url)
            chosen_account = Account.query.get(aid)
            if not chosen_account or not chosen_account.is_active:
                flash("Conta inválida ou inativa.", "danger")
                return redirect(next_url)

        if not chosen_company and not chosen_due_date and not chosen_account:
            flash("Preencha ao menos um campo para alterar em massa.", "warning")
            return redirect(next_url)

        if chosen_account:
            if not chosen_company:
                flash(
                    "Para alterar a conta em massa, informe também a empresa.",
                    "danger",
                )
                return redirect(next_url)
            if chosen_account.company_id != chosen_company.id:
                flash("A conta selecionada deve pertencer à empresa informada.", "danger")
                return redirect(next_url)

        if chosen_company and not chosen_account:
            incompatible_existing_account = [
                e.id
                for e in entries
                if e.account_id and e.account and e.account.company_id != chosen_company.id
            ]
            if incompatible_existing_account:
                flash(
                    "Alguns registros têm conta de outra empresa. Informe uma conta compatível para concluir a alteração de empresa.",
                    "danger",
                )
                return redirect(next_url)

        changed = 0
        for entry in entries:
            touched = False
            if chosen_company and entry.company_id != chosen_company.id:
                entry.company_id = chosen_company.id
                touched = True
            if chosen_due_date and entry.due_date != chosen_due_date:
                entry.due_date = chosen_due_date
                touched = True
            if chosen_account and entry.account_id != chosen_account.id:
                entry.account_id = chosen_account.id
                touched = True
            if touched:
                changed += 1

        db.session.commit()
        flash(f"{changed} lançamento(s) atualizado(s) em massa.", "success")
        return redirect(next_url)

    # ---- Reabrir (voltar a pendente) ----
    @bp.post("/financeiro/lancamento/<int:entry_id>/reabrir")
    @login_required
    def finance_reopen_entry(entry_id: int):
        require_admin()
        entry = FinancialEntry.query.get_or_404(entry_id)
        entry.settled_at = None
        db.session.commit()
        flash("Lançamento reaberto (pendente).", "info")
        return _manual_entry_redirect()

    @bp.post("/financeiro/lancamento/bulk-reopen")
    @login_required
    def finance_bulk_reopen():
        require_admin()
        next_url = resolve_next_url("admin.finance_manual_entry")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhum lançamento selecionado.", "warning")
            return redirect(next_url)
        count = 0
        for entry_id in ids:
            entry = FinancialEntry.query.get(entry_id)
            if entry and entry.settled_at:
                entry.settled_at = None
                count += 1
        db.session.commit()
        flash(f"{count} lançamento(s) reaberto(s).", "info")
        return redirect(next_url)

    @bp.post("/financeiro/lancamento/<int:entry_id>/delete")
    @login_required
    def finance_delete_entry(entry_id: int):
        require_admin()
        next_url = resolve_next_url("admin.finance_manual_entry")
        entry = FinancialEntry.query.get_or_404(entry_id)
        if entry.settled_at:
            flash("Não é possível excluir lançamento quitado. Reabra-o antes.", "warning")
            return redirect(next_url)
        try:
            db.session.delete(entry)
            db.session.commit()
            flash("Lançamento excluído.", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)

    @bp.post("/financeiro/lancamento/bulk-delete")
    @login_required
    def finance_bulk_delete():
        require_admin()
        next_url = resolve_next_url("admin.finance_manual_entry")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhum lançamento selecionado.", "warning")
            return redirect(next_url)
        try:
            settled_ids = [
                e.id
                for e in FinancialEntry.query.filter(FinancialEntry.id.in_(ids))
                .filter(FinancialEntry.settled_at.isnot(None))
                .all()
            ]
            pending_ids = [x for x in ids if x not in settled_ids]
            count = 0
            if pending_ids:
                count = FinancialEntry.query.filter(FinancialEntry.id.in_(pending_ids)).delete(
                    synchronize_session=False
                )
            db.session.commit()
            if settled_ids and count:
                flash(
                    f"{count} lançamento(s) pendente(s) excluído(s). {len(settled_ids)} quitado(s) não foram excluídos.",
                    "warning",
                )
            elif settled_ids and not count:
                flash("Nenhum lançamento excluído: registros quitados não podem ser excluídos.", "warning")
            else:
                flash(f"{count} lançamento(s) excluído(s).", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)

    @bp.route("/financeiro/processamento/<int:batch_id>/relatorio.pdf")
    @login_required
    def finance_batch_report(batch_id: int):
        require_admin()
        batch = FinancialBatch.query.get_or_404(batch_id)
        entries = (
            FinancialEntry.query.filter_by(financial_batch_id=batch.id)
            .order_by(FinancialEntry.company_id, FinancialEntry.supplier_id)
            .all()
        )

        if canvas is None:
            flash(
                "Geração de PDF indisponível: instale o pacote 'reportlab' no ambiente.",
                "danger",
            )
            return _manual_entry_redirect()

        # Preparar dados agrupados: Empresa -> Cliente -> [motoboys]
        grouped: dict[str, dict[str, list[dict]]] = {}

        # Intervalo do mês para localizar contratos (para adiantamento/residual)
        month_start = date(batch.year, batch.month, 1)
        if batch.month == 12:
            month_end = date(batch.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(batch.year, batch.month + 1, 1) - timedelta(days=1)

        for e in entries:
            company_name = e.company.legal_name if e.company else "-"
            client_name = "-"
            motoboy_name = "-"
            pix_key = "-"

            if e.supplier:
                if e.supplier.type == SUPPLIER_CLIENT:
                    client_name = client_display_label(e.supplier)
                elif e.supplier.type == SUPPLIER_MOTOBOY:
                    motoboy_name = e.supplier.name
                    pix_key = e.supplier.bank_account_pix or "-"

                    # Para batches de adiantamento/residual, tentar descobrir o CLIENTE
                    # a partir do contrato de motoboy ativo no mês do batch.
                    if batch.batch_type in (
                        BATCH_TYPE_ADVANCE,
                        BATCH_TYPE_RESIDUAL,
                        BATCH_TYPE_MOTOBOY_DISTRATO,
                        BATCH_TYPE_ADVANCE_DISTRATO,
                        BATCH_TYPE_RESIDUAL_DISTRATO,
                    ):
                        try:
                            contract = (
                                Contract.query.filter(
                                    Contract.contract_type == CONTRACT_TYPE_MOTOBOY,
                                    Contract.supplier_id == e.supplier_id,
                                )
                                .filter(Contract.start_date <= month_end)
                                .filter(
                                    (Contract.end_date.is_(None))
                                    | (Contract.end_date >= month_start)
                                )
                                .first()
                            )
                            if contract and contract.other_supplier:
                                client_name = client_display_label(contract.other_supplier)
                        except Exception:
                            pass

            try:
                val = float(e.amount)
            except (TypeError, ValueError):
                val = 0.0

            comp_key = company_name or "-"
            cli_key = client_name or "-"
            grouped.setdefault(comp_key, {}).setdefault(cli_key, []).append(
                {
                    "motoboy": motoboy_name or "-",
                    "pix": pix_key or "-",
                    "amount": val,
                }
            )

        buf = BytesIO()
        pdf = canvas.Canvas(buf, pagesize=A4)
        width, height = A4

        # Cabeçalho
        tipo_map = {
            BATCH_TYPE_REVENUE: "Receita",
            BATCH_TYPE_PAYMENT: "Pagamento",
            BATCH_TYPE_ADVANCE: "Adiantamento",
            BATCH_TYPE_RESIDUAL: "Residual",
            BATCH_TYPE_MOTOBOY_DISTRATO: "Distrato (motoboy)",
            BATCH_TYPE_ADVANCE_DISTRATO: "Adiantamento (distrato)",
            BATCH_TYPE_RESIDUAL_DISTRATO: "Residual (distrato)",
        }
        month_names = (
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
        tipo = tipo_map.get(batch.batch_type, batch.batch_type)
        mes_label = f"{month_names[batch.month]} de {batch.year}"
        titulo = f"Relatório de {tipo}"

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(40, height - 40, titulo)

        pdf.setFont("Helvetica", 11)
        pdf.drawString(40, height - 60, f"Referência: {mes_label}")
        pdf.drawString(40, height - 75, f"Natureza: {batch.financial_nature.name}")
        pdf.drawString(
            40,
            height - 90,
            f"Data de cobrança: {batch.charge_date.strftime('%d/%m/%Y')}",
        )

        y = height - 120
        pdf.setFont("Helvetica", 10)

        def new_page():
            nonlocal y
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = height - 40

        total_geral = 0.0

        # Agrupado por Empresa, Cliente, com motoboys listados abaixo
        for company_name in sorted(grouped.keys()):
            if y < 80:
                new_page()
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawString(40, y, f"Empresa: {company_name}")
            y -= 18

            for client_name in sorted(grouped[company_name].keys()):
                if y < 70:
                    new_page()
                    pdf.setFont("Helvetica-Bold", 11)
                    pdf.drawString(40, y, f"Empresa: {company_name}")
                    y -= 18

                pdf.setFont("Helvetica-Bold", 10)
                pdf.drawString(60, y, f"Cliente: {client_name}")
                y -= 14

                # Cabeçalho da sub-tabela de motoboys (com linha inferior)
                pdf.setFont("Helvetica-Bold", 9)
                pdf.drawString(70, y, "Motoboy")
                pdf.drawString(260, y, "PIX")
                pdf.drawRightString(540, y, "Valor a pagar")
                # linha horizontal abaixo do cabeçalho
                pdf.line(68, y - 2, 540, y - 2)
                y -= 12

                pdf.setFont("Helvetica", 9)
                subtotal = 0.0
                row_index = 0
                for item in grouped[company_name][client_name]:
                    if y < 60:
                        new_page()
                        pdf.setFont("Helvetica-Bold", 11)
                        pdf.drawString(40, y, f"Empresa: {company_name}")
                        y -= 18
                        pdf.setFont("Helvetica-Bold", 10)
                        pdf.drawString(60, y, f"Cliente: {client_name}")
                        y -= 14
                        pdf.setFont("Helvetica-Bold", 9)
                        pdf.drawString(70, y, "Motoboy")
                        pdf.drawString(260, y, "PIX")
                        pdf.drawRightString(540, y, "Valor a pagar")
                        y -= 12
                        pdf.setFont("Helvetica", 9)

                    # Fundo listrado alternado (um pouco mais escuro dentro da área da tabela)
                    if row_index % 2 == 0:
                        pdf.setFillGray(0.92)
                        pdf.rect(68, y - 1, 472, 11, fill=1, stroke=0)
                        pdf.setFillGray(0.0)

                    pdf.drawString(70, y, (item["motoboy"] or "")[:30])
                    pdf.drawString(260, y, (item["pix"] or "")[:24])
                    val = item["amount"] or 0.0
                    subtotal += val
                    total_geral += val
                    pdf.drawRightString(
                        540,
                        y,
                        f"{val:,.2f}".replace(",", "X")
                        .replace(".", ",")
                        .replace("X", "."),
                    )
                    # linha horizontal separando as linhas da tabela
                    pdf.line(68, y - 2, 540, y - 2)
                    y -= 12
                    row_index += 1

                # Subtotal por cliente
                if y < 50:
                    new_page()
                pdf.setFont("Helvetica-Bold", 9)
                pdf.drawRightString(
                    540,
                    y,
                    f"Subtotal cliente: {subtotal:,.2f}"
                    .replace(",", "X")
                    .replace(".", ",")
                    .replace("X", "."),
                )
                y -= 18

            y -= 6

        # Total geral
        if y < 40:
            new_page()
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawRightString(
            540,
            y,
            f"Total geral: {total_geral:,.2f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", "."),
        )

        pdf.showPage()
        pdf.save()
        buf.seek(0)

        resp = make_response(buf.read())
        resp.headers["Content-Type"] = "application/pdf"
        resp.headers[
            "Content-Disposition"
        ] = f'inline; filename="processamento_{batch.id}.pdf"'
        return resp

    # ---- Transferência entre contas ----
    @bp.route("/financeiro/transferencia/form")
    @login_required
    def finance_transfer_form():
        require_admin()
        # Na transferência entre contas, exibe apenas naturezas do tipo "Ambas"
        natures = (
            FinancialNature.query.filter_by(is_active=True, kind="both")
            .order_by(FinancialNature.name)
            .all()
        )
        all_accounts = _all_accounts_for_transfer()
        return render_template(
            "admin/financeiro/_transfer_form_fragment.html",
            natures=natures,
            all_accounts=all_accounts,
            default_date=date.today().isoformat(),
            action_url=url_for("admin.finance_transfer_create"),
        )

    @bp.route("/financeiro/transferencia", methods=["POST"])
    @login_required
    def finance_transfer_create():
        require_admin()
        account_from_id = request.form.get("account_from_id")
        account_to_id = request.form.get("account_to_id")
        nature_id = request.form.get("financial_nature_id")
        transfer_date_str = request.form.get("transfer_date", "").strip()
        amount_str = request.form.get("amount", "").strip()

        if not account_from_id or not account_to_id or not nature_id or not transfer_date_str or not amount_str:
            flash("Preencha conta origem, conta destino, natureza, data e valor.", "danger")
            return _manual_entry_redirect()

        if account_from_id == account_to_id:
            flash("Contas de origem e destino devem ser diferentes.", "danger")
            return _manual_entry_redirect()

        try:
            transfer_date = date.fromisoformat(transfer_date_str)
        except ValueError:
            flash("Data inválida.", "danger")
            return _manual_entry_redirect()

        try:
            amount_val = float(amount_str.replace(",", "."))
            if amount_val <= 0:
                raise ValueError("Valor deve ser positivo")
        except (ValueError, TypeError):
            flash("Valor inválido.", "danger")
            return _manual_entry_redirect()

        nature = FinancialNature.query.get(int(nature_id))
        if not nature or not nature.is_active:
            flash("Natureza inválida ou inativa.", "danger")
            return _manual_entry_redirect()

        acc_from = Account.query.get(int(account_from_id))
        acc_to = Account.query.get(int(account_to_id))
        if not acc_from or not acc_from.is_active:
            flash("Conta origem inválida ou inativa.", "danger")
            return _manual_entry_redirect()
        if not acc_to or not acc_to.is_active:
            flash("Conta destino inválida ou inativa.", "danger")
            return _manual_entry_redirect()

        settled_dt = datetime.combine(transfer_date, time(0, 0))

        out_entry = FinancialEntry(
            company_id=acc_from.company_id,
            account_id=acc_from.id,
            financial_nature_id=nature.id,
            supplier_id=None,
            entry_type=ENTRY_PAYABLE,
            description=f"Transferência para {acc_to.name} ({acc_to.company.legal_name})",
            amount=amount_val,
            due_date=transfer_date,
            settled_at=settled_dt,
        )
        in_entry = FinancialEntry(
            company_id=acc_to.company_id,
            account_id=acc_to.id,
            financial_nature_id=nature.id,
            supplier_id=None,
            entry_type=ENTRY_RECEIVABLE,
            description=f"Transferência de {acc_from.name} ({acc_from.company.legal_name})",
            amount=amount_val,
            due_date=transfer_date,
            settled_at=settled_dt,
        )
        db.session.add(out_entry)
        db.session.add(in_entry)
        db.session.commit()
        flash("Transferência registrada. Dois lançamentos quitados foram criados.", "success")
        return _manual_entry_redirect()


def _add_months(d: date, months: int) -> date:
    """Retorna d + months (meses)."""
    if months == 0:
        return d
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, cal.monthrange(year, month)[1])
    return date(year, month, day)


def _create_entry(entry_type: str, list_route: str, label: str):
    company_id = request.form.get("company_id")
    account_id = request.form.get("account_id") or None
    description = request.form.get("description", "").strip()
    amount = request.form.get("amount")
    due_date_str = request.form.get("due_date", "").strip()
    nature_id = request.form.get("financial_nature_id")
    supplier_id = request.form.get("supplier_id")
    recurrence_str = request.form.get("recurrence", "").strip()

    if not description or not amount or not nature_id or not supplier_id:
        flash("Natureza, fornecedor, descrição e valor são obrigatórios.", "danger")
        return redirect(resolve_next_url(list_route))

    if account_id:
        acc = Account.query.get(int(account_id))
        if not acc or not acc.is_active:
            flash("Conta inválida ou inativa.", "danger")
            return redirect(resolve_next_url(list_route))
        company_id_int = acc.company_id
        account_id_int = int(account_id)
    else:
        if not company_id:
            flash("Informe a empresa ou selecione uma conta.", "danger")
            return redirect(resolve_next_url(list_route))
        company_id_int = int(company_id)
        account_id_int = None

    nature = FinancialNature.query.get(int(nature_id))
    if not nature or not nature.is_active:
        flash("Natureza inválida ou inativa.", "danger")
        return redirect(resolve_next_url(list_route))
    if nature.kind != entry_type:
        flash("A natureza selecionada não corresponde ao tipo (contas a pagar/receber).", "danger")
        return redirect(resolve_next_url(list_route))

    try:
        amount_val = float(amount.replace(",", "."))
        if amount_val <= 0:
            raise ValueError("Valor deve ser positivo")
    except (ValueError, TypeError):
        flash("Valor inválido.", "danger")
        return redirect(resolve_next_url(list_route))

    supplier = Supplier.query.get(int(supplier_id))
    if not supplier or not supplier.is_active:
        flash("Fornecedor inválido ou inativo.", "danger")
        return redirect(resolve_next_url(list_route))

    due_date = date.fromisoformat(due_date_str) if due_date_str else None
    if not due_date:
        flash("Data de vencimento é obrigatória.", "danger")
        return redirect(resolve_next_url(list_route))

    recurrence_count = 1
    if recurrence_str and recurrence_str.isdigit():
        recurrence_count = max(1, min(int(recurrence_str), 120))

    for i in range(recurrence_count):
        entry_due = _add_months(due_date, i)
        entry = FinancialEntry(
            company_id=company_id_int,
            account_id=account_id_int,
            financial_nature_id=int(nature_id),
            supplier_id=int(supplier_id),
            entry_type=entry_type,
            description=description,
            amount=amount_val,
            due_date=entry_due,
        )
        db.session.add(entry)
    db.session.commit()
    if recurrence_count > 1:
        flash(f"{recurrence_count} lançamentos cadastrados (recorrência mensal).", "success")
    else:
        flash(f"{label} cadastrada com sucesso.", "success")
    return redirect(resolve_next_url(list_route))


def _update_entry(entry: FinancialEntry):
    company_id = request.form.get("company_id")
    account_id = request.form.get("account_id") or None
    description = request.form.get("description", "").strip()
    amount = request.form.get("amount")
    due_date_str = request.form.get("due_date", "").strip()
    nature_id = request.form.get("financial_nature_id")
    entry_type = request.form.get("entry_type")
    supplier_id = request.form.get("supplier_id")

    if not description or not amount or not nature_id or not supplier_id:
        flash("Natureza, fornecedor, descrição e valor são obrigatórios.", "danger")
        return _manual_entry_redirect()

    if account_id:
        acc = Account.query.get(int(account_id))
        if not acc or not acc.is_active:
            flash("Conta inválida ou inativa.", "danger")
            return _manual_entry_redirect()
        company_id_int = acc.company_id
        entry.account_id = int(account_id)
    else:
        if not company_id:
            flash("Informe a empresa ou selecione uma conta.", "danger")
            return _manual_entry_redirect()
        company_id_int = int(company_id)
        entry.account_id = None

    nature = FinancialNature.query.get(int(nature_id))
    if not nature or not nature.is_active:
        flash("Natureza inválida ou inativa.", "danger")
        return _manual_entry_redirect()
    if nature.kind != entry_type:
        flash("A natureza selecionada não corresponde ao tipo (contas a pagar/receber).", "danger")
        return _manual_entry_redirect()

    try:
        amount_val = float(amount.replace(",", "."))
        if amount_val <= 0:
            raise ValueError("Valor deve ser positivo")
    except (ValueError, TypeError):
        flash("Valor inválido.", "danger")
        return _manual_entry_redirect()

    supplier = Supplier.query.get(int(supplier_id))
    if not supplier or not supplier.is_active:
        flash("Fornecedor inválido ou inativo.", "danger")
        return _manual_entry_redirect()

    due_date = date.fromisoformat(due_date_str) if due_date_str else None
    entry.company_id = company_id_int
    entry.financial_nature_id = int(nature_id)
    entry.supplier_id = int(supplier_id)
    entry.entry_type = entry_type
    entry.description = description
    entry.amount = amount_val
    entry.due_date = due_date
    db.session.commit()
    flash("Lançamento alterado com sucesso.", "success")
    return _manual_entry_redirect()
