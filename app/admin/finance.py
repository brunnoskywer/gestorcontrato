"""Rotas do módulo Financeiro: contas a pagar, a receber, despesa e lançamento manual."""
import calendar as cal
from datetime import date, datetime, time

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
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
)


def _companies_with_accounts():
    return Company.query.order_by(Company.legal_name).all()


def _financial_natures():
    return FinancialNature.query.filter_by(is_active=True).order_by(FinancialNature.name).all()


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
            },
        )

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
        natures = _financial_natures()
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
