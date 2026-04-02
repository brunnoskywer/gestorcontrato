"""CRUD for Client contracts: uses Contract with contract_type=client."""
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from app.admin.auth_helpers import require_admin, handle_delete_constraint_error, resolve_next_url
from app.extensions import db
from app.models import Contract, CONTRACT_TYPE_CLIENT, FinancialNature, Supplier, SUPPLIER_CLIENT
from app.utils import parse_decimal_form
from sqlalchemy import or_


def register_routes(bp: Blueprint) -> None:
    def _revenue_natures():
        return (
            FinancialNature.query.filter(
                FinancialNature.is_active.is_(True),
                FinancialNature.kind.in_(["receivable", "both"]),
            )
            .order_by(FinancialNature.name)
            .all()
        )

    @bp.route("/client-contracts/form")
    @login_required
    def client_contracts_form_new():
        require_admin()
        clients = Supplier.query.filter_by(type=SUPPLIER_CLIENT).order_by(Supplier.legal_name, Supplier.name).all()
        natures = _revenue_natures()
        return render_template(
            "admin/client_contracts/_form_fragment.html",
            contract=None,
            clients=clients,
            natures=natures,
            action_url=url_for("admin.client_contracts_create"),
        )

    @bp.route("/client-contracts/<int:contract_id>/form")
    @login_required
    def client_contracts_form_edit(contract_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_CLIENT).first_or_404()
        clients = Supplier.query.filter_by(type=SUPPLIER_CLIENT).order_by(Supplier.legal_name, Supplier.name).all()
        natures = _revenue_natures()
        return render_template(
            "admin/client_contracts/_form_fragment.html",
            contract=contract,
            clients=clients,
            natures=natures,
            action_url=url_for("admin.client_contracts_edit", contract_id=contract_id),
        )

    @bp.route("/client-contracts")
    @login_required
    def client_contracts_list():
        require_admin()
        client_name = request.args.get("client_name", "").strip()

        query = Contract.query.filter_by(contract_type=CONTRACT_TYPE_CLIENT).join(Supplier, Contract.supplier_id == Supplier.id)
        if client_name:
            query = query.filter(
                or_(
                    Supplier.legal_name.ilike(f"%{client_name}%"),
                    Supplier.name.ilike(f"%{client_name}%"),
                )
            )
        contracts = query.order_by(Contract.start_date.desc()).all()
        return render_template(
            "admin/client_contracts/list.html",
            contracts=contracts,
            filters={"client_name": client_name},
        )

    @bp.route("/client-contracts/create", methods=["GET", "POST"])
    @login_required
    def client_contracts_create():
        require_admin()
        clients = Supplier.query.filter_by(type=SUPPLIER_CLIENT).order_by(Supplier.legal_name, Supplier.name).all()

        if request.method == "POST":
            client_id = request.form.get("client_id")
            start_date_str = request.form.get("start_date", "")
            end_date_str = request.form.get("end_date", "")
            contract_value = parse_decimal_form(request.form.get("contract_value"))
            motoboy_quantity = request.form.get("motoboy_quantity") or None

            if not client_id or not start_date_str:
                flash("Cliente e data de início são obrigatórios.", "danger")
            else:
                start_date_val = date.fromisoformat(start_date_str)
                end_date_val = date.fromisoformat(end_date_str) if end_date_str else None
                contract = Contract(
                    supplier_id=int(client_id),
                    contract_type=CONTRACT_TYPE_CLIENT,
                    start_date=start_date_val,
                    end_date=end_date_val,
                    contract_value=contract_value,
                    motoboy_quantity=int(motoboy_quantity) if motoboy_quantity else None,
                )
                db.session.add(contract)
                db.session.commit()
                flash("Client contract created successfully.", "success")
                return redirect(url_for("admin.client_contracts_list"))

        return render_template(
            "admin/client_contracts/form.html",
            contract=None,
            clients=clients,
        )

    @bp.route("/client-contracts/<int:contract_id>/edit", methods=["GET", "POST"])
    @login_required
    def client_contracts_edit(contract_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_CLIENT).first_or_404()
        clients = Supplier.query.filter_by(type=SUPPLIER_CLIENT).order_by(Supplier.legal_name, Supplier.name).all()

        if request.method == "POST":
            client_id = request.form.get("client_id")
            start_date_str = request.form.get("start_date", "")
            end_date_str = request.form.get("end_date", "")
            contract_value = parse_decimal_form(request.form.get("contract_value"))
            motoboy_quantity = request.form.get("motoboy_quantity") or None
            revenue_financial_nature_id = request.form.get("revenue_financial_nature_id") or None

            if not client_id or not start_date_str:
                flash("Cliente e data de início são obrigatórios.", "danger")
            else:
                contract.supplier_id = int(client_id)
                contract.start_date = date.fromisoformat(start_date_str)
                contract.end_date = date.fromisoformat(end_date_str) if end_date_str else None
                contract.contract_value = contract_value
                contract.motoboy_quantity = int(motoboy_quantity) if motoboy_quantity else None
                contract.revenue_financial_nature_id = int(revenue_financial_nature_id) if revenue_financial_nature_id else None
                db.session.commit()
                flash("Contrato de cliente atualizado com sucesso.", "success")
                return redirect(url_for("admin.client_contracts_list"))

        natures = _revenue_natures()
        return render_template(
            "admin/client_contracts/form.html",
            contract=contract,
            clients=clients,
            natures=natures,
        )

    @bp.post("/client-contracts/<int:contract_id>/delete")
    @login_required
    def client_contracts_delete(contract_id: int):
        require_admin()
        next_url = resolve_next_url("admin.client_contracts_list")
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_CLIENT).first_or_404()
        try:
            db.session.delete(contract)
            db.session.commit()
            flash("Contrato de cliente excluído.", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)

    @bp.post("/client-contracts/bulk-delete")
    @login_required
    def client_contracts_bulk_delete():
        require_admin()
        next_url = request.form.get("next") or request.args.get("next") or url_for("admin.client_contracts_list")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhum contrato selecionado.", "warning")
            return redirect(next_url)
        try:
            count = (
                Contract.query.filter(
                    Contract.id.in_(ids),
                    Contract.contract_type == CONTRACT_TYPE_CLIENT,
                ).delete(synchronize_session=False)
            )
            db.session.commit()
            flash(f"{count} contrato(s) excluído(s).", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)
