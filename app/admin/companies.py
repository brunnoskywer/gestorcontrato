"""Rotas de CRUD para Empresas (admin)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from app.admin.auth_helpers import require_admin, handle_delete_constraint_error
from app.extensions import db
from app.models import Company


def register_routes(bp: Blueprint) -> None:
    @bp.route("/companies/form")
    @login_required
    def companies_form_new():
        """Retorna apenas o HTML do formulário (modal) para criar."""
        require_admin()
        return render_template(
            "admin/companies/_form_fragment.html",
            company=None,
            action_url=url_for("admin.companies_create"),
        )

    @bp.route("/companies/<int:company_id>/form")
    @login_required
    def companies_form_edit(company_id: int):
        """Retorna apenas o HTML do formulário (modal) para editar."""
        require_admin()
        company = Company.query.get_or_404(company_id)
        return render_template(
            "admin/companies/_form_fragment.html",
            company=company,
            action_url=url_for("admin.companies_edit", company_id=company_id),
        )

    @bp.route("/companies")
    @login_required
    def companies_list():
        require_admin()
        name = request.args.get("name", "").strip()
        cnpj = request.args.get("cnpj", "").strip()

        query = Company.query
        if name:
            query = query.filter(Company.legal_name.ilike(f"%{name}%"))
        if cnpj:
            query = query.filter(Company.cnpj.ilike(f"%{cnpj}%"))

        companies = query.order_by(Company.legal_name).all()
        return render_template(
            "admin/companies/list.html",
            companies=companies,
            filters={"name": name, "cnpj": cnpj},
        )

    @bp.route("/companies/create", methods=["GET", "POST"])
    @login_required
    def companies_create():
        require_admin()
        if request.method == "POST":
            legal_name = request.form.get("legal_name", "").strip()
            trade_name = request.form.get("trade_name", "").strip()
            cnpj = request.form.get("cnpj", "").strip()
            partner_name = request.form.get("partner_name", "").strip()

            if not legal_name or not cnpj:
                flash("Razão social e CNPJ são obrigatórios.", "danger")
            else:
                company = Company(
                    legal_name=legal_name,
                    trade_name=trade_name or None,
                    cnpj=cnpj,
                    partner_name=partner_name or None,
                )
                db.session.add(company)
                db.session.commit()
                flash("Empresa criada com sucesso.", "success")
                return redirect(url_for("admin.companies_list"))

        return render_template("admin/companies/form.html", company=None)

    @bp.route("/companies/<int:company_id>/edit", methods=["GET", "POST"])
    @login_required
    def companies_edit(company_id: int):
        require_admin()
        company = Company.query.get_or_404(company_id)

        if request.method == "POST":
            company.legal_name = request.form.get("legal_name", "").strip()
            company.trade_name = request.form.get("trade_name", "").strip() or None
            company.cnpj = request.form.get("cnpj", "").strip()
            company.partner_name = request.form.get("partner_name", "").strip() or None

            if not company.legal_name or not company.cnpj:
                flash("Razão social e CNPJ são obrigatórios.", "danger")
            else:
                db.session.commit()
                flash("Empresa atualizada com sucesso.", "success")
                return redirect(url_for("admin.companies_list"))

        return render_template("admin/companies/form.html", company=company)

    @bp.post("/companies/<int:company_id>/delete")
    @login_required
    def companies_delete(company_id: int):
        require_admin()
        company = Company.query.get_or_404(company_id)
        try:
            db.session.delete(company)
            db.session.commit()
            flash("Empresa excluída.", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(url_for("admin.companies_list"))

    @bp.post("/companies/bulk-delete")
    @login_required
    def companies_bulk_delete():
        require_admin()
        next_url = request.form.get("next") or request.args.get("next") or url_for("admin.companies_list")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhuma empresa selecionada.", "warning")
            return redirect(next_url)
        try:
            count = Company.query.filter(Company.id.in_(ids)).delete(synchronize_session=False)
            db.session.commit()
            flash(f"{count} empresa(s) excluída(s).", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)
