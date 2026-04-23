"""Rotas de CRUD para Empresas (admin)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from app.admin.auth_helpers import require_admin, handle_delete_constraint_error, resolve_next_url
from app.constants.brazil_ufs import is_valid_uf
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
            cep = request.form.get("cep", "").strip()
            partner_name = request.form.get("partner_name", "").strip()
            address = request.form.get("address", "").strip()
            street = request.form.get("street", "").strip()
            neighborhood = request.form.get("neighborhood", "").strip()
            city = request.form.get("city", "").strip()
            state = (request.form.get("state") or "").strip().upper()
            allow_contract_generation = request.form.get("allow_contract_generation") == "1"

            if not legal_name or not cnpj:
                flash("Razão social e CNPJ são obrigatórios.", "danger")
            elif not street or not neighborhood or not city or not is_valid_uf(state):
                flash("Preencha rua, bairro, cidade e UF válidos da empresa.", "danger")
            else:
                company = Company(
                    legal_name=legal_name,
                    trade_name=trade_name or None,
                    cnpj=cnpj,
                    partner_name=partner_name or None,
                    address=address or None,
                    cep=cep or None,
                    street=street,
                    neighborhood=neighborhood,
                    city=city,
                    state=state,
                    allow_contract_generation=allow_contract_generation,
                )
                db.session.add(company)
                db.session.commit()
                flash("Empresa criada com sucesso.", "success")
                return redirect(resolve_next_url("admin.companies_list"))

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
            company.cep = request.form.get("cep", "").strip() or None
            company.partner_name = request.form.get("partner_name", "").strip() or None
            company.address = request.form.get("address", "").strip() or None
            company.street = request.form.get("street", "").strip()
            company.neighborhood = request.form.get("neighborhood", "").strip()
            company.city = request.form.get("city", "").strip()
            company.state = (request.form.get("state") or "").strip().upper()
            company.allow_contract_generation = request.form.get("allow_contract_generation") == "1"

            if not company.legal_name or not company.cnpj:
                flash("Razão social e CNPJ são obrigatórios.", "danger")
                db.session.rollback()
            elif (
                not company.street
                or not company.neighborhood
                or not company.city
                or not is_valid_uf(company.state)
            ):
                flash("Preencha rua, bairro, cidade e UF válidos da empresa.", "danger")
                db.session.rollback()
            else:
                db.session.commit()
                flash("Empresa atualizada com sucesso.", "success")
                return redirect(resolve_next_url("admin.companies_list"))

        return render_template("admin/companies/form.html", company=company)

    @bp.post("/companies/<int:company_id>/delete")
    @login_required
    def companies_delete(company_id: int):
        require_admin()
        next_url = resolve_next_url("admin.companies_list")
        company = Company.query.get_or_404(company_id)
        try:
            db.session.delete(company)
            db.session.commit()
            flash("Empresa excluída.", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)

    @bp.post("/companies/bulk-delete")
    @login_required
    def companies_bulk_delete():
        require_admin()
        next_url = resolve_next_url("admin.companies_list")
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
