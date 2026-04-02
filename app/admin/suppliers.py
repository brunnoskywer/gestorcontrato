"""Rotas de CRUD para Fornecedores (Supplier)."""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from app.admin.auth_helpers import require_admin, handle_delete_constraint_error, resolve_next_url
from app.extensions import db
from app.models import Supplier, SUPPLIER_CLIENT, SUPPLIER_SUPPLIER, SUPPLIER_MOTOBOY


def register_routes(bp: Blueprint) -> None:
    @bp.route("/suppliers")
    @login_required
    def suppliers_list():
        """Lista apenas fornecedores do tipo 'fornecedor', abstraindo clientes e motoboys."""
        require_admin()
        name = request.args.get("name", "").strip()

        query = Supplier.query.filter(Supplier.type == SUPPLIER_SUPPLIER)
        if name:
            query = query.filter(Supplier.name.ilike(f"%{name}%"))

        suppliers = query.order_by(Supplier.name).all()
        return render_template(
            "admin/suppliers/list.html",
            suppliers=suppliers,
            filters={"name": name},
        )

    @bp.route("/suppliers/form")
    @login_required
    def suppliers_form_new():
        require_admin()
        return render_template(
            "admin/suppliers/_form_fragment.html",
            supplier=None,
            action_url=url_for("admin.suppliers_create"),
        )

    @bp.route("/suppliers/<int:supplier_id>/form")
    @login_required
    def suppliers_form_edit(supplier_id: int):
        require_admin()
        supplier = Supplier.query.get_or_404(supplier_id)
        return render_template(
            "admin/suppliers/_form_fragment.html",
            supplier=supplier,
            action_url=url_for("admin.suppliers_edit", supplier_id=supplier_id),
        )

    @bp.route("/suppliers/create", methods=["GET", "POST"])
    @login_required
    def suppliers_create():
        require_admin()
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            document = request.form.get("document", "").strip() or None
            is_active = request.form.get("is_active") == "on"
            if not name:
                flash("Nome é obrigatório.", "danger")
            else:
                supplier = Supplier(
                    name=name,
                    document=document,
                    type=SUPPLIER_SUPPLIER,
                    is_active=is_active,
                )
                db.session.add(supplier)
                db.session.commit()
                flash("Fornecedor criado com sucesso.", "success")
                return redirect(url_for("admin.suppliers_list"))
        return render_template("admin/suppliers/form.html", supplier=None)

    @bp.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
    @login_required
    def suppliers_edit(supplier_id: int):
        require_admin()
        supplier = Supplier.query.get_or_404(supplier_id)
        if request.method == "POST":
            supplier.name = request.form.get("name", "").strip()
            supplier.document = request.form.get("document", "").strip() or None
            supplier.is_active = request.form.get("is_active") == "on"
            if not supplier.name:
                flash("Nome é obrigatório.", "danger")
            else:
                db.session.commit()
                flash("Fornecedor atualizado com sucesso.", "success")
                return redirect(url_for("admin.suppliers_list"))
        return render_template("admin/suppliers/form.html", supplier=supplier)

    @bp.post("/suppliers/<int:supplier_id>/delete")
    @login_required
    def suppliers_delete(supplier_id: int):
        require_admin()
        next_url = resolve_next_url("admin.suppliers_list")
        supplier = Supplier.query.get_or_404(supplier_id)
        try:
            db.session.delete(supplier)
            db.session.commit()
            flash("Fornecedor excluído.", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)

    @bp.post("/suppliers/bulk-delete")
    @login_required
    def suppliers_bulk_delete():
        require_admin()
        next_url = resolve_next_url("admin.suppliers_list")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhum fornecedor selecionado.", "warning")
            return redirect(next_url)
        try:
            count = Supplier.query.filter(Supplier.id.in_(ids)).delete(synchronize_session=False)
            db.session.commit()
            flash(f"{count} fornecedor(es) excluído(s).", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)

    @bp.get("/suppliers/search")
    @login_required
    def suppliers_search():
        """Busca rápida de fornecedores, com filtro por tipo e parte do nome."""
        require_admin()
        term = request.args.get("q", "").strip()
        supplier_type = request.args.get("type", "").strip()
        if len(term) < 3:
            return jsonify([])

        query = Supplier.query.filter(Supplier.is_active.is_(True))
        if supplier_type in (SUPPLIER_CLIENT, SUPPLIER_SUPPLIER, SUPPLIER_MOTOBOY):
            query = query.filter(Supplier.type == supplier_type)
        if term:
            query = query.filter(Supplier.name.ilike(f"%{term}%"))

        items = query.order_by(Supplier.name).limit(20).all()
        return jsonify(
            [
                {
                    "id": s.id,
                    "label": s.name,
                    "secondary": s.document or "",
                }
                for s in items
            ]
        )

