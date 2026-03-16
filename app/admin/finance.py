"""Rotas do módulo Financeiro: contas a pagar, a receber, despesa e lançamento manual."""
import calendar as cal
from datetime import date, datetime, time, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.admin.auth_helpers import require_admin, handle_delete_constraint_error
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
    Contract,
    CONTRACT_TYPE_CLIENT,
)


def _companies_with_accounts():
    return Company.query.order_by(Company.legal_name).all()


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
            return redirect(url_for("admin.finance_manual_entry"))
        entry_type = request.form.get("entry_type")
        if entry_type not in (ENTRY_PAYABLE, ENTRY_RECEIVABLE):
            flash("Tipo de lançamento inválido.", "danger")
            return redirect(url_for("admin.finance_manual_entry"))
        return _update_entry(entry)

    @bp.route("/financeiro/lancamento/create", methods=["POST"])
    @login_required
    def finance_entry_create():
        require_admin()
        entry_type = request.form.get("entry_type")
        if entry_type not in (ENTRY_PAYABLE, ENTRY_RECEIVABLE):
            flash("Tipo de lançamento inválido.", "danger")
            return redirect(url_for("admin.finance_manual_entry"))
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
        supplier_name = request.args.get("supplier_name", "").strip()
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
            # padrão: primeiro dia do mês até hoje
            today = date.today()
            date_from_filter = today.replace(day=1)
            date_to_filter = today
            date_from_str = date_from_filter.isoformat()
            date_to_str = date_to_filter.isoformat()

        query = FinancialEntry.query.outerjoin(Supplier)
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
        if supplier_name:
            query = query.filter(Supplier.name.ilike(f"%{supplier_name}%"))
        if status == "pending":
            query = query.filter(FinancialEntry.settled_at.is_(None))
        elif status == "settled":
            query = query.filter(FinancialEntry.settled_at.isnot(None))

        entries = query.order_by(
            FinancialEntry.due_date.desc().nullslast(), FinancialEntry.id.desc()
        ).all()
        return render_template(
            "admin/financeiro/manual_entry.html",
            companies=companies,
            natures=natures,
            entries=entries,
            filters={
                "date_from": date_from_str,
                "date_to": date_to_str,
                "company_id": company_id,
                "entry_type": entry_type,
                "supplier_type": supplier_type,
                "supplier_name": supplier_name,
                "status": status,
            },
        )

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
            q = q.filter(FinancialBatch.batch_type == BATCH_TYPE_PAYMENT)
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
            action_url=url_for("admin.finance_revenue_process"),
            next_url=next_url,
        )

    @bp.post("/financeiro/receitas/processar")
    @login_required
    def finance_revenue_process():
        require_admin()
        next_url = request.form.get("next") or url_for("admin.finance_manual_entry")
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
            batch_type=BATCH_TYPE_REVENUE,
            year=year,
            month=month,
        ).first()
        if existing:
            flash("Já existe um processamento de receitas para este mês/ano.", "warning")
            return redirect(next_url)

        contracts = (
            Contract.query.filter(Contract.contract_type == CONTRACT_TYPE_CLIENT)
            .filter(Contract.start_date <= month_end)
            .filter((Contract.end_date.is_(None)) | (Contract.end_date >= month_start))
            .all()
        )

        created = 0
        skipped_no_company = 0
        skipped_no_nature = 0
        batch = None

        for c in contracts:
            if not c.contract_value:
                continue
            # Natureza vem do cadastro do contrato do cliente
            nature = c.revenue_financial_nature if c.revenue_financial_nature_id else None
            if not nature or not nature.is_active or nature.kind not in ("receivable", "both"):
                skipped_no_nature += 1
                continue
            # Usar a empresa associada ao cliente para emissão de nota (billing_company_id)
            company_id = None
            if c.supplier and c.supplier.billing_company_id:
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
                    created_by_id=getattr(current_user, "id", None),
                )
                db.session.add(batch)
                db.session.flush()

            eff_start = max(c.start_date, month_start)
            eff_end = min(c.end_date or month_end, month_end)
            days_in_month = (month_end - month_start).days + 1
            effective_days = (eff_end - eff_start).days + 1
            proportion = effective_days / days_in_month if days_in_month > 0 else 1
            amount = float(c.contract_value) * proportion

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
            else:
                flash("Nenhuma receita foi gerada para os contratos vigentes no período.", "warning")
        else:
            db.session.commit()
            msg = f"{created} lançamento(s) de receita gerado(s)."
            if skipped_no_company:
                msg += f" {skipped_no_company} contrato(s) ignorado(s): cliente sem empresa para emissão de nota."
            if skipped_no_nature:
                msg += f" {skipped_no_nature} contrato(s) ignorado(s): sem natureza financeira de receita."
            flash(msg, "success" if not (skipped_no_company or skipped_no_nature) else "warning")

        return redirect(next_url)

    @bp.post("/financeiro/processamentos/<int:batch_id>/delete")
    @login_required
    def finance_batch_delete(batch_id: int):
        require_admin()
        next_url = request.form.get("next") or url_for("admin.finance_manual_entry")
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
        next_url = request.form.get("next") or url_for("admin.finance_manual_entry")
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
        suggested_charge_date = _suggest_charge_date(default_year, default_month)
        return render_template(
            "admin/financeiro/_advance_process_form_fragment.html",
            default_year=default_year,
            default_month=default_month,
            suggested_charge_date=suggested_charge_date.isoformat(),
            action_url=url_for("admin.finance_advance_process"),
            next_url=next_url,
        )

    @bp.post("/financeiro/adiantamentos/processar")
    @login_required
    def finance_advance_process():
        require_admin()
        next_url = request.form.get("next") or url_for("admin.finance_manual_entry")
        flash("Processamento de adiantamentos em desenvolvimento.", "info")
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
        return render_template(
            "admin/financeiro/_residual_process_form_fragment.html",
            default_year=default_year,
            default_month=default_month,
            suggested_charge_date=suggested_charge_date.isoformat(),
            action_url=url_for("admin.finance_residual_process"),
            next_url=next_url,
        )

    @bp.post("/financeiro/residual/processar")
    @login_required
    def finance_residual_process():
        require_admin()
        next_url = request.form.get("next") or url_for("admin.finance_manual_entry")
        flash("Processamento residual em desenvolvimento.", "info")
        return redirect(next_url)

    # ---- Aprovar (definir data de baixa) ----
    @bp.route("/financeiro/lancamento/<int:entry_id>/aprovar/form")
    @login_required
    def finance_approve_entry_form(entry_id: int):
        require_admin()
        entry = FinancialEntry.query.get_or_404(entry_id)
        if entry.settled_at:
            flash("Lançamento já quitado.", "warning")
            return redirect(url_for("admin.finance_manual_entry"))
        return render_template(
            "admin/financeiro/_approve_form_fragment.html",
            entry=entry,
            action_url=url_for("admin.finance_approve_entry", entry_id=entry_id),
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
            return redirect(url_for("admin.finance_manual_entry"))
        try:
            settled_date = date.fromisoformat(settled_date_str)
        except ValueError:
            flash("Data de baixa inválida.", "danger")
            return redirect(url_for("admin.finance_manual_entry"))
        entry.settled_at = datetime.combine(settled_date, time(0, 0))
        account_id = request.form.get("account_id", "").strip()
        if account_id:
            try:
                aid = int(account_id)
                acc = Account.query.get(aid)
                if acc and acc.company_id == entry.company_id and acc.is_active:
                    entry.account_id = aid
                else:
                    entry.account_id = None
            except (ValueError, TypeError):
                entry.account_id = None
        else:
            entry.account_id = None
        db.session.commit()
        flash("Lançamento aprovado (quitado).", "success")
        next_url = request.form.get("next") or url_for("admin.finance_manual_entry")
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
        next_url = request.form.get("next") or request.referrer or url_for("admin.finance_manual_entry")
        return redirect(next_url)

    @bp.post("/financeiro/lancamento/bulk-reopen")
    @login_required
    def finance_bulk_reopen():
        require_admin()
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhum lançamento selecionado.", "warning")
            return redirect(url_for("admin.finance_manual_entry"))
        count = 0
        for entry_id in ids:
            entry = FinancialEntry.query.get(entry_id)
            if entry and entry.settled_at:
                entry.settled_at = None
                count += 1
        db.session.commit()
        flash(f"{count} lançamento(s) reaberto(s).", "info")
        return redirect(url_for("admin.finance_manual_entry"))

    @bp.post("/financeiro/lancamento/<int:entry_id>/delete")
    @login_required
    def finance_delete_entry(entry_id: int):
        require_admin()
        entry = FinancialEntry.query.get_or_404(entry_id)
        try:
            db.session.delete(entry)
            db.session.commit()
            flash("Lançamento excluído.", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(url_for("admin.finance_manual_entry"))

    @bp.post("/financeiro/lancamento/bulk-delete")
    @login_required
    def finance_bulk_delete():
        require_admin()
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhum lançamento selecionado.", "warning")
            return redirect(url_for("admin.finance_manual_entry"))
        try:
            count = FinancialEntry.query.filter(FinancialEntry.id.in_(ids)).delete(synchronize_session=False)
            db.session.commit()
            flash(f"{count} lançamento(s) excluído(s).", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(url_for("admin.finance_manual_entry"))

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
            return redirect(url_for("admin.finance_manual_entry"))

        if account_from_id == account_to_id:
            flash("Contas de origem e destino devem ser diferentes.", "danger")
            return redirect(url_for("admin.finance_manual_entry"))

        try:
            transfer_date = date.fromisoformat(transfer_date_str)
        except ValueError:
            flash("Data inválida.", "danger")
            return redirect(url_for("admin.finance_manual_entry"))

        try:
            amount_val = float(amount_str.replace(",", "."))
            if amount_val <= 0:
                raise ValueError("Valor deve ser positivo")
        except (ValueError, TypeError):
            flash("Valor inválido.", "danger")
            return redirect(url_for("admin.finance_manual_entry"))

        nature = FinancialNature.query.get(int(nature_id))
        if not nature or not nature.is_active:
            flash("Natureza inválida ou inativa.", "danger")
            return redirect(url_for("admin.finance_manual_entry"))

        acc_from = Account.query.get(int(account_from_id))
        acc_to = Account.query.get(int(account_to_id))
        if not acc_from or not acc_from.is_active:
            flash("Conta origem inválida ou inativa.", "danger")
            return redirect(url_for("admin.finance_manual_entry"))
        if not acc_to or not acc_to.is_active:
            flash("Conta destino inválida ou inativa.", "danger")
            return redirect(url_for("admin.finance_manual_entry"))

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
        return redirect(url_for("admin.finance_manual_entry"))


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
        return redirect(url_for(list_route))

    if account_id:
        acc = Account.query.get(int(account_id))
        if not acc or not acc.is_active:
            flash("Conta inválida ou inativa.", "danger")
            return redirect(url_for(list_route))
        company_id_int = acc.company_id
        account_id_int = int(account_id)
    else:
        if not company_id:
            flash("Informe a empresa ou selecione uma conta.", "danger")
            return redirect(url_for(list_route))
        company_id_int = int(company_id)
        account_id_int = None

    nature = FinancialNature.query.get(int(nature_id))
    if not nature or not nature.is_active:
        flash("Natureza inválida ou inativa.", "danger")
        return redirect(url_for(list_route))
    if nature.kind != entry_type:
        flash("A natureza selecionada não corresponde ao tipo (contas a pagar/receber).", "danger")
        return redirect(url_for(list_route))

    try:
        amount_val = float(amount.replace(",", "."))
        if amount_val <= 0:
            raise ValueError("Valor deve ser positivo")
    except (ValueError, TypeError):
        flash("Valor inválido.", "danger")
        return redirect(url_for(list_route))

    supplier = Supplier.query.get(int(supplier_id))
    if not supplier or not supplier.is_active:
        flash("Fornecedor inválido ou inativo.", "danger")
        return redirect(url_for(list_route))

    due_date = date.fromisoformat(due_date_str) if due_date_str else None
    if not due_date:
        flash("Data de vencimento é obrigatória.", "danger")
        return redirect(url_for(list_route))

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
    return redirect(url_for(list_route))


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
        return redirect(url_for("admin.finance_manual_entry"))

    if account_id:
        acc = Account.query.get(int(account_id))
        if not acc or not acc.is_active:
            flash("Conta inválida ou inativa.", "danger")
            return redirect(url_for("admin.finance_manual_entry"))
        company_id_int = acc.company_id
        entry.account_id = int(account_id)
    else:
        if not company_id:
            flash("Informe a empresa ou selecione uma conta.", "danger")
            return redirect(url_for("admin.finance_manual_entry"))
        company_id_int = int(company_id)
        entry.account_id = None

    nature = FinancialNature.query.get(int(nature_id))
    if not nature or not nature.is_active:
        flash("Natureza inválida ou inativa.", "danger")
        return redirect(url_for("admin.finance_manual_entry"))
    if nature.kind != entry_type:
        flash("A natureza selecionada não corresponde ao tipo (contas a pagar/receber).", "danger")
        return redirect(url_for("admin.finance_manual_entry"))

    try:
        amount_val = float(amount.replace(",", "."))
        if amount_val <= 0:
            raise ValueError("Valor deve ser positivo")
    except (ValueError, TypeError):
        flash("Valor inválido.", "danger")
        return redirect(url_for("admin.finance_manual_entry"))

    supplier = Supplier.query.get(int(supplier_id))
    if not supplier or not supplier.is_active:
        flash("Fornecedor inválido ou inativo.", "danger")
        return redirect(url_for("admin.finance_manual_entry"))

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
    return redirect(url_for("admin.finance_manual_entry"))
