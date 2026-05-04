"""CRUD for Clients: uses Supplier with type=client."""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app.admin.auth_helpers import require_admin, handle_delete_constraint_error, resolve_next_url
from app.admin.list_pagination import ADMIN_LIST_PER_PAGE, admin_list_page
from app.constants.brazil_ufs import is_valid_uf
from app.extensions import db
from app.models import Company, Supplier, SUPPLIER_CLIENT
from app.models.supplier import client_display_label
from app.search_text import folded_icontains


def register_routes(bp: Blueprint) -> None:
    @bp.route("/clients/form")
    @login_required
    def clients_form_new():
        require_admin()
        companies = Company.query.order_by(Company.legal_name).all()
        return render_template(
            "admin/clients/_form_fragment.html",
            client=None,
            companies=companies,
            action_url=url_for("admin.clients_create"),
        )

    @bp.route("/clients/<int:client_id>/form")
    @login_required
    def clients_form_edit(client_id: int):
        require_admin()
        client = Supplier.query.filter_by(id=client_id, type=SUPPLIER_CLIENT).first_or_404()
        companies = Company.query.order_by(Company.legal_name).all()
        return render_template(
            "admin/clients/_form_fragment.html",
            client=client,
            companies=companies,
            action_url=url_for("admin.clients_edit", client_id=client_id),
        )

    @bp.route("/clients")
    @login_required
    def clients_list():
        require_admin()
        name = request.args.get("name", "").strip()
        cnpj = request.args.get("cnpj", "").strip()

        query = Supplier.query.filter_by(type=SUPPLIER_CLIENT)
        if name:
            query = query.filter(
                or_(
                    folded_icontains(Supplier.legal_name, name),
                    folded_icontains(Supplier.name, name),
                    folded_icontains(Supplier.trade_name, name),
                )
            )
        if cnpj:
            query = query.filter(folded_icontains(Supplier.document, cnpj))

        pagination = query.order_by(
            func.coalesce(Supplier.trade_name, Supplier.legal_name, Supplier.name)
        ).paginate(page=admin_list_page(), per_page=ADMIN_LIST_PER_PAGE, error_out=False)
        companies = Company.query.order_by(Company.legal_name).all()
        return render_template(
            "admin/clients/list.html",
            clients=pagination.items,
            pagination=pagination,
            companies=companies,
            filters={"name": name, "cnpj": cnpj},
        )

    @bp.get("/clients/search")
    @login_required
    def clients_search():
        """Search clients (suppliers with type=client) for autocomplete."""
        require_admin()
        term = request.args.get("q", "").strip()
        if len(term) < 3:
            return jsonify([])

        query = (
            Supplier.query.filter_by(type=SUPPLIER_CLIENT, is_active=True)
            .filter(
                or_(
                    folded_icontains(Supplier.legal_name, term),
                    folded_icontains(Supplier.name, term),
                    folded_icontains(Supplier.trade_name, term),
                )
            )
            .order_by(func.coalesce(Supplier.trade_name, Supplier.legal_name, Supplier.name))
        )
        results = query.limit(20).all()
        payload = [
            {
                "id": c.id,
                "label": client_display_label(c),
                "secondary": c.document or "",
            }
            for c in results
        ]
        return jsonify(payload)

    @bp.route("/clients/create", methods=["GET", "POST"])
    @login_required
    def clients_create():
        require_admin()
        companies = Company.query.order_by(Company.legal_name).all()

        if request.method == "POST":
            legal_name = request.form.get("legal_name", "").strip()
            trade_name = request.form.get("trade_name", "").strip()
            cnpj = request.form.get("cnpj", "").strip()
            cep = request.form.get("cep", "").strip()
            address = request.form.get("address", "").strip()
            street = request.form.get("street", "").strip()
            neighborhood = request.form.get("neighborhood", "").strip()
            city = request.form.get("city", "").strip()
            state = (request.form.get("state") or "").strip().upper()
            contact_name = request.form.get("contact_name", "").strip()
            email = request.form.get("email", "").strip()
            billing_company_id = request.form.get("billing_company_id") or None
            notes = request.form.get("notes", "").strip()

            if not legal_name or not cnpj:
                flash("Razão social e CNPJ são obrigatórios.", "danger")
            elif not street or not neighborhood or not city or not is_valid_uf(state):
                flash("Preencha rua, bairro, cidade e UF válidos do cliente.", "danger")
            else:
                client = Supplier(
                    name=legal_name,
                    document=cnpj,
                    type=SUPPLIER_CLIENT,
                    is_active=True,
                    legal_name=legal_name,
                    trade_name=trade_name or None,
                    address=address or None,
                    cep=cep or None,
                    street=street,
                    neighborhood=neighborhood,
                    city=city,
                    state=state,
                    contact_name=contact_name or None,
                    email=email or None,
                    billing_company_id=billing_company_id,
                    notes=notes or None,
                )
                db.session.add(client)
                db.session.commit()
                flash("Cliente criado com sucesso.", "success")
                return redirect(resolve_next_url("admin.clients_list"))

        return render_template(
            "admin/clients/form.html",
            client=None,
            companies=companies,
        )

    @bp.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
    @login_required
    def clients_edit(client_id: int):
        require_admin()
        client = Supplier.query.filter_by(id=client_id, type=SUPPLIER_CLIENT).first_or_404()
        companies = Company.query.order_by(Company.legal_name).all()

        if request.method == "POST":
            legal_name = request.form.get("legal_name", "").strip()
            trade_name = request.form.get("trade_name", "").strip()
            cnpj = request.form.get("cnpj", "").strip()
            cep = request.form.get("cep", "").strip()
            address = request.form.get("address", "").strip()
            street = request.form.get("street", "").strip()
            neighborhood = request.form.get("neighborhood", "").strip()
            city = request.form.get("city", "").strip()
            state = (request.form.get("state") or "").strip().upper()
            contact_name = request.form.get("contact_name", "").strip()
            email = request.form.get("email", "").strip()
            billing_company_id = request.form.get("billing_company_id") or None
            notes = request.form.get("notes", "").strip()

            if not legal_name or not cnpj:
                flash("Razão social e CNPJ são obrigatórios.", "danger")
                db.session.rollback()
            elif not street or not neighborhood or not city or not is_valid_uf(state):
                flash("Preencha rua, bairro, cidade e UF válidos do cliente.", "danger")
                db.session.rollback()
            else:
                client.name = legal_name
                client.document = cnpj
                client.legal_name = legal_name
                client.trade_name = trade_name or None
                client.address = address or None
                client.cep = cep or None
                client.street = street
                client.neighborhood = neighborhood
                client.city = city
                client.state = state
                client.contact_name = contact_name or None
                client.email = email or None
                client.billing_company_id = billing_company_id
                client.notes = notes or None
                db.session.commit()
                flash("Cliente atualizado com sucesso.", "success")
                return redirect(resolve_next_url("admin.clients_list"))

        return render_template(
            "admin/clients/form.html",
            client=client,
            companies=companies,
        )

    @bp.post("/clients/<int:client_id>/delete")
    @login_required
    def clients_delete(client_id: int):
        require_admin()
        next_url = resolve_next_url("admin.clients_list")
        client = Supplier.query.filter_by(id=client_id, type=SUPPLIER_CLIENT).first_or_404()
        try:
            db.session.delete(client)
            db.session.commit()
            flash("Cliente excluído.", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)

    @bp.post("/clients/bulk-delete")
    @login_required
    def clients_bulk_delete():
        require_admin()
        next_url = resolve_next_url("admin.clients_list")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhum cliente selecionado.", "warning")
            return redirect(next_url)
        try:
            count = (
                Supplier.query.filter(
                    Supplier.id.in_(ids),
                    Supplier.type == SUPPLIER_CLIENT,
                ).delete(synchronize_session=False)
            )
            db.session.commit()
            flash(f"{count} cliente(s) excluído(s).", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)
