"""Rotas de CRUD para Contas (vinculadas à empresa)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from app.admin.auth_helpers import require_admin, handle_delete_constraint_error, resolve_next_url
from app.extensions import db
from app.models import Account, Company


def register_routes(bp: Blueprint) -> None:
    @bp.route("/accounts/form")
    @login_required
    def accounts_form_new():
        require_admin()
        companies = Company.query.order_by(Company.legal_name).all()
        return render_template(
            "admin/accounts/_form_fragment.html",
            account=None,
            companies=companies,
            action_url=url_for("admin.accounts_create"),
        )

    @bp.route("/accounts/<int:account_id>/form")
    @login_required
    def accounts_form_edit(account_id: int):
        require_admin()
        account = Account.query.get_or_404(account_id)
        companies = Company.query.order_by(Company.legal_name).all()
        return render_template(
            "admin/accounts/_form_fragment.html",
            account=account,
            companies=companies,
            action_url=url_for("admin.accounts_edit", account_id=account_id),
        )

    @bp.route("/accounts")
    @login_required
    def accounts_list():
        require_admin()
        company_id = request.args.get("company_id", type=int)
        name = request.args.get("name", "").strip()

        query = Account.query
        if company_id:
            query = query.filter(Account.company_id == company_id)
        if name:
            query = query.filter(Account.name.ilike(f"%{name}%"))

        accounts = query.join(Company).order_by(Company.legal_name, Account.name).all()
        companies = Company.query.order_by(Company.legal_name).all()
        return render_template(
            "admin/accounts/list.html",
            accounts=accounts,
            companies=companies,
            filters={"company_id": company_id, "name": name},
        )

    @bp.route("/accounts/create", methods=["GET", "POST"])
    @login_required
    def accounts_create():
        require_admin()
        companies = Company.query.order_by(Company.legal_name).all()
        if request.method == "POST":
            company_id = request.form.get("company_id")
            name = request.form.get("name", "").strip()
            bank_name = request.form.get("bank_name", "").strip()
            agency = request.form.get("agency", "").strip()
            account_number = request.form.get("account_number", "").strip()
            pix_key = request.form.get("pix_key", "").strip()
            is_active = request.form.get("is_active") == "on"

            if not company_id or not name:
                flash("Empresa e nome da conta são obrigatórios.", "danger")
            else:
                account = Account(
                    company_id=int(company_id),
                    name=name,
                    bank_name=bank_name or None,
                    agency=agency or None,
                    account_number=account_number or None,
                    pix_key=pix_key or None,
                    is_active=is_active,
                )
                db.session.add(account)
                db.session.commit()
                flash("Conta criada com sucesso.", "success")
                return redirect(url_for("admin.accounts_list"))

        return render_template("admin/accounts/form.html", account=None, companies=companies)

    @bp.route("/accounts/<int:account_id>/edit", methods=["GET", "POST"])
    @login_required
    def accounts_edit(account_id: int):
        require_admin()
        account = Account.query.get_or_404(account_id)
        companies = Company.query.order_by(Company.legal_name).all()
        if request.method == "POST":
            account.company_id = int(request.form.get("company_id", account.company_id))
            account.name = request.form.get("name", "").strip()
            account.bank_name = request.form.get("bank_name", "").strip() or None
            account.agency = request.form.get("agency", "").strip() or None
            account.account_number = request.form.get("account_number", "").strip() or None
            account.pix_key = request.form.get("pix_key", "").strip() or None
            account.is_active = request.form.get("is_active") == "on"

            if not account.name:
                flash("Nome da conta é obrigatório.", "danger")
            else:
                db.session.commit()
                flash("Conta atualizada com sucesso.", "success")
                return redirect(url_for("admin.accounts_list"))

        return render_template("admin/accounts/form.html", account=account, companies=companies)

    @bp.post("/accounts/<int:account_id>/delete")
    @login_required
    def accounts_delete(account_id: int):
        require_admin()
        next_url = resolve_next_url("admin.accounts_list")
        account = Account.query.get_or_404(account_id)
        try:
            db.session.delete(account)
            db.session.commit()
            flash("Conta excluída.", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)

    @bp.post("/accounts/bulk-delete")
    @login_required
    def accounts_bulk_delete():
        require_admin()
        next_url = request.form.get("next") or request.args.get("next") or url_for("admin.accounts_list")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhuma conta selecionada.", "warning")
            return redirect(next_url)
        try:
            count = Account.query.filter(Account.id.in_(ids)).delete(synchronize_session=False)
            db.session.commit()
            flash(f"{count} conta(s) excluída(s).", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)
