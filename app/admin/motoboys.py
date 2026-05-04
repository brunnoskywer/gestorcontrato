"""CRUD for Motoboys: uses Supplier with type=motoboy."""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from app.admin.auth_helpers import require_admin, handle_delete_constraint_error, resolve_next_url
from app.admin.list_pagination import ADMIN_LIST_PER_PAGE, admin_list_page
from app.constants.brazil_ufs import is_valid_uf
from app.extensions import db
from app.models import (
    Supplier,
    SUPPLIER_MOTOBOY,
    MOTOBOY_STATUS_ACTIVE,
    MOTOBOY_STATUS_PENDING,
    MOTOBOY_STATUS_TERMINATED,
    MOTOBOY_TERMINATED_STATUSES,
)
from app.search_text import folded_icontains

_ALLOWED_MOTOBOY_STATUS = frozenset(
    {MOTOBOY_STATUS_ACTIVE, MOTOBOY_STATUS_PENDING, MOTOBOY_STATUS_TERMINATED}
)


def _normalize_motoboy_status(raw: str | None) -> str:
    s = (raw or MOTOBOY_STATUS_ACTIVE).strip().lower()
    if s == "inactive":
        return MOTOBOY_STATUS_TERMINATED
    if s in _ALLOWED_MOTOBOY_STATUS:
        return s
    return MOTOBOY_STATUS_ACTIVE


def _render_motoboy_form(motoboy, action_url: str):
    # Quando o formulário é aberto em modal, precisamos retornar só o fragmento.
    # Se retornar página completa aqui, o modal fica "quebrado" visualmente.
    is_modal_request = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.headers.get("Turbo-Frame") == "main-content"
    )
    if is_modal_request:
        return render_template(
            "admin/motoboys/_form_fragment.html",
            motoboy=motoboy,
            action_url=action_url,
        )
    return render_template("admin/motoboys/form.html", motoboy=motoboy)


def register_routes(bp: Blueprint) -> None:
    @bp.route("/motoboys/form")
    @login_required
    def motoboys_form_new():
        require_admin()
        return render_template(
            "admin/motoboys/_form_fragment.html",
            motoboy=None,
            action_url=url_for("admin.motoboys_create"),
        )

    @bp.route("/motoboys/<int:motoboy_id>/form")
    @login_required
    def motoboys_form_edit(motoboy_id: int):
        require_admin()
        motoboy = Supplier.query.filter_by(id=motoboy_id, type=SUPPLIER_MOTOBOY).first_or_404()
        return render_template(
            "admin/motoboys/_form_fragment.html",
            motoboy=motoboy,
            action_url=url_for("admin.motoboys_edit", motoboy_id=motoboy_id),
        )

    @bp.route("/motoboys")
    @login_required
    def motoboys_list():
        require_admin()
        name = request.args.get("name", "").strip()
        cpf = request.args.get("cpf", "").strip()

        query = Supplier.query.filter_by(type=SUPPLIER_MOTOBOY)
        if name:
            query = query.filter(folded_icontains(Supplier.name, name))
        if cpf:
            query = query.filter(folded_icontains(Supplier.document, cpf))

        pagination = query.order_by(Supplier.name).paginate(
            page=admin_list_page(), per_page=ADMIN_LIST_PER_PAGE, error_out=False
        )
        return render_template(
            "admin/motoboys/list.html",
            motoboys=pagination.items,
            pagination=pagination,
            filters={"name": name, "cpf": cpf},
        )

    @bp.get("/motoboys/search")
    @login_required
    def motoboys_search():
        """Search motoboys (suppliers with type=motoboy) for autocomplete."""
        require_admin()
        term = request.args.get("q", "").strip()
        if len(term) < 3:
            return jsonify([])

        query = (
            Supplier.query.filter_by(type=SUPPLIER_MOTOBOY)
            .filter(~Supplier.status.in_(MOTOBOY_TERMINATED_STATUSES))
            .filter(folded_icontains(Supplier.name, term))
            .order_by(Supplier.name)
        )
        results = query.limit(20).all()
        payload = [
            {
                "id": m.id,
                "label": m.name,
                "secondary": m.document or "",
            }
            for m in results
        ]
        return jsonify(payload)

    @bp.route("/motoboys/create", methods=["GET", "POST"])
    @login_required
    def motoboys_create():
        require_admin()
        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            cpf = request.form.get("cpf", "").strip()
            cnpj = request.form.get("cnpj", "").strip()
            cep = request.form.get("cep", "").strip()
            address = request.form.get("address", "").strip()
            street = request.form.get("street", "").strip()
            neighborhood = request.form.get("neighborhood", "").strip()
            city = request.form.get("city", "").strip()
            state = (request.form.get("state") or "").strip().upper()
            reference_contact = request.form.get("reference_contact", "").strip()
            bike_plate = request.form.get("bike_plate", "").strip()
            bank_account_pix = request.form.get("bank_account_pix", "").strip()
            status = _normalize_motoboy_status(request.form.get("status"))
            contact_phone = request.form.get("contact_phone", "").strip()
            notes = request.form.get("notes", "").strip()
            is_diarist = request.form.get("is_diarist") == "1"

            if not full_name or not cpf:
                flash("Nome completo e CPF são obrigatórios.", "danger")
            elif not street or not neighborhood or not city or not is_valid_uf(state):
                flash("Preencha rua, bairro, cidade e UF válidos do motoboy.", "danger")
            else:
                motoboy = Supplier(
                    name=full_name,
                    document=cpf,
                    type=SUPPLIER_MOTOBOY,
                    is_active=status not in MOTOBOY_TERMINATED_STATUSES,
                    address=address or None,
                    cep=cep or None,
                    street=street,
                    neighborhood=neighborhood,
                    city=city,
                    state=state,
                    reference_contact=reference_contact or None,
                    bike_plate=bike_plate or None,
                    bank_account_pix=bank_account_pix or None,
                    document_secondary=cnpj or None,
                    status=status,
                    contact_phone=contact_phone or None,
                    notes=notes or None,
                    is_diarist=is_diarist,
                )
                db.session.add(motoboy)
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    flash("Não foi possível salvar o motoboy.", "danger")
                else:
                    flash("Motoboy criado com sucesso.", "success")
                    return redirect(resolve_next_url("admin.motoboys_list"))

        return _render_motoboy_form(
            motoboy=None,
            action_url=url_for("admin.motoboys_create"),
        )

    @bp.route("/motoboys/<int:motoboy_id>/edit", methods=["GET", "POST"])
    @login_required
    def motoboys_edit(motoboy_id: int):
        require_admin()
        motoboy = Supplier.query.filter_by(id=motoboy_id, type=SUPPLIER_MOTOBOY).first_or_404()

        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            cpf = request.form.get("cpf", "").strip()
            cnpj = request.form.get("cnpj", "").strip()
            cep = request.form.get("cep", "").strip()
            address = request.form.get("address", "").strip()
            street = request.form.get("street", "").strip()
            neighborhood = request.form.get("neighborhood", "").strip()
            city = request.form.get("city", "").strip()
            state = (request.form.get("state") or "").strip().upper()
            reference_contact = request.form.get("reference_contact", "").strip()
            bike_plate = request.form.get("bike_plate", "").strip()
            bank_account_pix = request.form.get("bank_account_pix", "").strip()
            status = _normalize_motoboy_status(request.form.get("status"))
            contact_phone = request.form.get("contact_phone", "").strip()
            notes = request.form.get("notes", "").strip()
            is_diarist = request.form.get("is_diarist") == "1"

            if not full_name or not cpf:
                flash("Nome completo e CPF são obrigatórios.", "danger")
                db.session.rollback()
            elif not street or not neighborhood or not city or not is_valid_uf(state):
                flash("Preencha rua, bairro, cidade e UF válidos do motoboy.", "danger")
                db.session.rollback()
            else:
                motoboy.name = full_name
                motoboy.document = cpf
                motoboy.address = address or None
                motoboy.cep = cep or None
                motoboy.street = street
                motoboy.neighborhood = neighborhood
                motoboy.city = city
                motoboy.state = state
                motoboy.reference_contact = reference_contact or None
                motoboy.bike_plate = bike_plate or None
                motoboy.bank_account_pix = bank_account_pix or None
                motoboy.document_secondary = cnpj or None
                motoboy.status = status
                motoboy.is_active = status not in MOTOBOY_TERMINATED_STATUSES
                motoboy.contact_phone = contact_phone or None
                motoboy.notes = notes or None
                motoboy.is_diarist = is_diarist
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    flash("Não foi possível atualizar o motoboy.", "danger")
                else:
                    flash("Motoboy atualizado com sucesso.", "success")
                    return redirect(resolve_next_url("admin.motoboys_list"))

        return _render_motoboy_form(
            motoboy=motoboy,
            action_url=url_for("admin.motoboys_edit", motoboy_id=motoboy_id),
        )

    @bp.post("/motoboys/<int:motoboy_id>/delete")
    @login_required
    def motoboys_delete(motoboy_id: int):
        require_admin()
        next_url = resolve_next_url("admin.motoboys_list")
        motoboy = Supplier.query.filter_by(id=motoboy_id, type=SUPPLIER_MOTOBOY).first_or_404()
        try:
            db.session.delete(motoboy)
            db.session.commit()
            flash("Motoboy excluído.", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)

    @bp.post("/motoboys/<int:motoboy_id>/encerrar")
    @login_required
    def motoboys_encerrar(motoboy_id: int):
        require_admin()
        motoboy = Supplier.query.filter_by(id=motoboy_id, type=SUPPLIER_MOTOBOY).first_or_404()
        if motoboy.status in MOTOBOY_TERMINATED_STATUSES:
            flash("Este motoboy já está encerrado.", "warning")
            return redirect(resolve_next_url("admin.motoboys_list"))
        motoboy.status = MOTOBOY_STATUS_TERMINATED
        motoboy.is_active = False
        db.session.commit()
        flash("Motoboy encerrado. Ele deixa de aparecer em contratos, faltas e financeiro.", "info")
        return redirect(resolve_next_url("admin.motoboys_list"))

    @bp.post("/motoboys/<int:motoboy_id>/ativar")
    @login_required
    def motoboys_ativar(motoboy_id: int):
        require_admin()
        motoboy = Supplier.query.filter_by(id=motoboy_id, type=SUPPLIER_MOTOBOY).first_or_404()
        if motoboy.status not in MOTOBOY_TERMINATED_STATUSES:
            flash("Este motoboy já está ativo (não encerrado).", "warning")
            return redirect(resolve_next_url("admin.motoboys_list"))
        motoboy.status = MOTOBOY_STATUS_ACTIVE
        motoboy.is_active = True
        db.session.commit()
        flash("Motoboy ativado novamente.", "success")
        return redirect(resolve_next_url("admin.motoboys_list"))

    @bp.post("/motoboys/bulk-delete")
    @login_required
    def motoboys_bulk_delete():
        require_admin()
        next_url = resolve_next_url("admin.motoboys_list")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhum motoboy selecionado.", "warning")
            return redirect(next_url)
        try:
            count = (
                Supplier.query.filter(
                    Supplier.id.in_(ids),
                    Supplier.type == SUPPLIER_MOTOBOY,
                ).delete(synchronize_session=False)
            )
            db.session.commit()
            flash(f"{count} motoboy(s) excluído(s).", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)
