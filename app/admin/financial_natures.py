"""Rotas de CRUD para Naturezas Financeiras."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from app.admin.auth_helpers import require_admin, handle_delete_constraint_error, resolve_next_url
from app.extensions import db
from app.models import FinancialNature


def register_routes(bp: Blueprint) -> None:
    @bp.route("/financial-natures/form")
    @login_required
    def financial_natures_form_new():
        require_admin()
        return render_template(
            "admin/financial_natures/_form_fragment.html",
            nature=None,
            action_url=url_for("admin.financial_natures_create"),
        )

    @bp.route("/financial-natures/<int:nature_id>/form")
    @login_required
    def financial_natures_form_edit(nature_id: int):
        require_admin()
        nature = FinancialNature.query.get_or_404(nature_id)
        return render_template(
            "admin/financial_natures/_form_fragment.html",
            nature=nature,
            action_url=url_for("admin.financial_natures_edit", nature_id=nature_id),
        )

    @bp.route("/financial-natures")
    @login_required
    def financial_natures_list():
        require_admin()
        name = request.args.get("name", "").strip()

        query = FinancialNature.query
        if name:
            query = query.filter(FinancialNature.name.ilike(f"%{name}%"))

        natures = query.order_by(FinancialNature.name).all()
        return render_template(
            "admin/financial_natures/list.html",
            natures=natures,
            filters={"name": name},
        )

    @bp.route("/financial-natures/create", methods=["GET", "POST"])
    @login_required
    def financial_natures_create():
        require_admin()
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            kind = request.form.get("kind", "payable").strip() or "payable"
            is_active = request.form.get("is_active") == "on"
            if not name:
                flash("Nome da natureza é obrigatório.", "danger")
            elif kind not in ("payable", "receivable", "both"):
                flash("Tipo da natureza deve ser Contas a pagar, Contas a receber ou Ambas.", "danger")
            else:
                nature = FinancialNature(name=name, kind=kind, is_active=is_active)
                db.session.add(nature)
                db.session.commit()
                flash("Natureza financeira criada com sucesso.", "success")
                return redirect(url_for("admin.financial_natures_list"))

        return render_template("admin/financial_natures/form.html", nature=None)

    @bp.route("/financial-natures/<int:nature_id>/edit", methods=["GET", "POST"])
    @login_required
    def financial_natures_edit(nature_id: int):
        require_admin()
        nature = FinancialNature.query.get_or_404(nature_id)
        if request.method == "POST":
            nature.name = request.form.get("name", "").strip()
            kind = request.form.get("kind", "payable").strip() or "payable"
            nature.is_active = request.form.get("is_active") == "on"
            if not nature.name:
                flash("Nome da natureza é obrigatório.", "danger")
            elif kind not in ("payable", "receivable", "both"):
                flash("Tipo da natureza deve ser Contas a pagar, Contas a receber ou Ambas.", "danger")
            else:
                nature.kind = kind
                db.session.commit()
                flash("Natureza financeira atualizada com sucesso.", "success")
                return redirect(url_for("admin.financial_natures_list"))

        return render_template("admin/financial_natures/form.html", nature=nature)

    @bp.post("/financial-natures/<int:nature_id>/delete")
    @login_required
    def financial_natures_delete(nature_id: int):
        require_admin()
        next_url = resolve_next_url("admin.financial_natures_list")
        nature = FinancialNature.query.get_or_404(nature_id)
        try:
            db.session.delete(nature)
            db.session.commit()
            flash("Natureza financeira excluída.", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)

    @bp.post("/financial-natures/bulk-delete")
    @login_required
    def financial_natures_bulk_delete():
        require_admin()
        next_url = request.form.get("next") or request.args.get("next") or url_for("admin.financial_natures_list")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhuma natureza selecionada.", "warning")
            return redirect(next_url)
        try:
            count = FinancialNature.query.filter(FinancialNature.id.in_(ids)).delete(synchronize_session=False)
            db.session.commit()
            flash(f"{count} natureza(s) excluída(s).", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)

