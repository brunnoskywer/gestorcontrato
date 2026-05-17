"""Módulo de solicitações (solicitante, membro e administrador)."""
from datetime import datetime

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app.admin.auth_helpers import (
    is_request_staff,
    is_solicitante,
    require_request_module_access,
    require_solicitante_or_admin,
    require_staff,
    resolve_next_url,
)
from app.admin.list_pagination import ADMIN_LIST_PER_PAGE, SlicePagination, admin_list_page
from app.admin.motoboy_contracts import _diarist_motoboys_for_select, _payable_natures_query
from app.extensions import db
from app.models import CONTRACT_TYPE_MOTOBOY, Company, Contract, SUPPLIER_CLIENT, Supplier
from app.models.requests import (
    REQUEST_STATUS_LABELS,
    REQUEST_STATUS_PENDING,
    REQUEST_TYPE_ABSENCE,
    REQUEST_TYPE_DISTRATO,
    REQUEST_TYPE_LABELS,
    REQUEST_TYPE_MOTOBOY_INCLUSION,
    REQUEST_TYPE_RELOCATION,
    REQUEST_TYPES,
    Request,
)
from app.models.supplier import client_display_label
from app.search_text import folded_icontains
from app.services.request_resolution import (
    execute_resolve,
    motoboy_from_payload,
    pending_requests_count,
    reject_request,
)
from app.services.requests import (
    active_motoboy_contracts_query,
    build_payload_from_form,
    clients_for_relocation_select,
    contract_to_api_dict,
    diarist_motoboys_for_form,
    diarist_motoboys_to_api,
    distinct_active_locations,
    list_date_range_from_request,
    list_filter_datetime_bounds,
    request_summary,
    validate_request_type,
)


def _require_own_or_admin(req: Request) -> None:
    if current_user.is_admin or is_request_staff():
        return
    if req.requester_id != current_user.id:
        abort(403)


def _require_pending(req: Request) -> bool:
    if req.status != REQUEST_STATUS_PENDING:
        flash("Somente solicitações pendentes podem ser alteradas ou excluídas.", "danger")
        return False
    return True


def _form_context(req: Request | None = None):
    payload = dict(req.payload) if req and req.payload else {}
    contract = None
    cid = payload.get("motoboy_contract_id")
    if cid:
        contract = Contract.query.get(int(cid))
    return {
        "req": req,
        "payload": payload,
        "request_types": REQUEST_TYPES,
        "request_type_labels": REQUEST_TYPE_LABELS,
        "locations": distinct_active_locations(),
        "clients": clients_for_relocation_select(),
        "diarist_motoboys": diarist_motoboys_for_form(contract),
        "selected_contract": contract,
    }


def _resolve_form_context(req: Request):
    payload = req.payload or {}
    ctx = {
        "req": req,
        "payload": payload,
        "action_url": url_for("admin.requests_resolve", request_id=req.id),
    }
    if req.request_type == REQUEST_TYPE_MOTOBOY_INCLUSION:
        ctx["motoboy"] = motoboy_from_payload(payload)
    elif req.request_type in (
        REQUEST_TYPE_DISTRATO,
        REQUEST_TYPE_RELOCATION,
        REQUEST_TYPE_ABSENCE,
    ):
        contract_id = payload.get("motoboy_contract_id")
        contract = (
            Contract.query.filter_by(
                id=int(contract_id), contract_type=CONTRACT_TYPE_MOTOBOY
            ).first()
            if contract_id
            else None
        )
        ctx["contract"] = contract
        if req.request_type == REQUEST_TYPE_DISTRATO:
            ctx["companies"] = Company.query.order_by(Company.legal_name).all()
            ctx["natures"] = _payable_natures_query().all()
            ctx["default_charge_date"] = datetime.utcnow().date().isoformat()
        elif req.request_type == REQUEST_TYPE_ABSENCE:
            ctx["diarist_motoboys"] = _diarist_motoboys_for_select(contract) if contract else []
            ctx["financial_natures"] = _payable_natures_query().all()
        elif req.request_type == REQUEST_TYPE_RELOCATION:
            ctx["clients"] = clients_for_relocation_select()
    return ctx


def register_routes(bp: Blueprint) -> None:
    @bp.route("/requests")
    @login_required
    def requests_list():
        require_request_module_access()
        date_from, date_to, _ = list_date_range_from_request()
        start_dt, end_dt = list_filter_datetime_bounds(date_from, date_to)

        q = Request.query.options(joinedload(Request.requester))
        if is_solicitante():
            q = q.filter(Request.requester_id == current_user.id)

        q = q.filter(
            Request.created_at >= start_dt,
            Request.created_at <= end_dt,
        )

        req_type = request.args.get("request_type", "").strip()
        if req_type in REQUEST_TYPES:
            q = q.filter(Request.request_type == req_type)

        status = request.args.get("status", "").strip()
        if status in REQUEST_STATUS_LABELS:
            q = q.filter(Request.status == status)

        rows = q.order_by(Request.created_at.desc()).all()
        list_rows = [{"req": r, "summary": request_summary(r)} for r in rows]
        pagination = SlicePagination(list_rows, admin_list_page(), ADMIN_LIST_PER_PAGE)

        _resolve_base = url_for("admin.requests_resolve_form", request_id=999999)
        _reject_base = url_for("admin.requests_reject_form", request_id=999999)

        staff = is_request_staff()
        return render_template(
            "admin/requests/list.html",
            rows=pagination.items,
            pagination=pagination,
            filters={
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "request_type": req_type,
                "status": status,
            },
            request_type_labels=REQUEST_TYPE_LABELS,
            status_labels=REQUEST_STATUS_LABELS,
            show_requester_column=staff or current_user.is_admin,
            is_solicitante_user=is_solicitante(),
            is_request_staff_user=staff,
            resolve_url_template=_resolve_base.replace("999999", "{id}") if staff else None,
            reject_url_template=_reject_base.replace("999999", "{id}") if staff else None,
        )

    @bp.get("/requests/api/pending-count")
    @login_required
    def requests_pending_count_api():
        require_request_module_access()
        if not is_request_staff():
            return jsonify({"count": 0})
        return jsonify({"count": pending_requests_count()})

    @bp.route("/requests/nova/form")
    @login_required
    def requests_form_new():
        require_solicitante_or_admin()
        ctx = _form_context()
        return render_template(
            "admin/requests/_form_fragment.html",
            action_url=url_for("admin.requests_create"),
            **ctx,
        )

    @bp.route("/requests/<int:request_id>/form")
    @login_required
    def requests_form_edit(request_id: int):
        require_solicitante_or_admin()
        req = Request.query.get_or_404(request_id)
        _require_own_or_admin(req)
        if not req.is_pending:
            flash("Somente solicitações pendentes podem ser editadas.", "warning")
            return redirect(url_for("admin.requests_list"))
        ctx = _form_context(req)
        return render_template(
            "admin/requests/_form_fragment.html",
            action_url=url_for("admin.requests_edit", request_id=request_id),
            **ctx,
        )

    @bp.route("/requests/<int:request_id>/resolve/form")
    @login_required
    def requests_resolve_form(request_id: int):
        require_staff()
        req = Request.query.get_or_404(request_id)
        if not req.is_pending:
            return (
                '<p class="text-danger small mb-0">Somente solicitações pendentes podem ser resolvidas.</p>',
                400,
            )
        ctx = _resolve_form_context(req)
        templates = {
            REQUEST_TYPE_MOTOBOY_INCLUSION: "admin/requests/resolve_motoboy.html",
            REQUEST_TYPE_DISTRATO: "admin/requests/resolve_distrato.html",
            REQUEST_TYPE_RELOCATION: "admin/requests/resolve_relocation.html",
            REQUEST_TYPE_ABSENCE: "admin/requests/resolve_absence.html",
        }
        tpl = templates.get(req.request_type)
        if not tpl:
            return '<p class="text-danger small mb-0">Tipo não suportado.</p>', 400
        return render_template(tpl, **ctx)

    @bp.route("/requests/<int:request_id>/resolve", methods=["POST"])
    @login_required
    def requests_resolve(request_id: int):
        require_staff()
        req = Request.query.get_or_404(request_id)
        ok, msg = execute_resolve(req)
        if ok:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("Erro ao salvar. Tente novamente.", "danger")
            else:
                flash(msg, "success")
        else:
            db.session.rollback()
            flash(msg, "danger")
        return redirect(resolve_next_url("admin.requests_list"))

    @bp.route("/requests/<int:request_id>/reject/form")
    @login_required
    def requests_reject_form(request_id: int):
        require_staff()
        req = Request.query.get_or_404(request_id)
        if not req.is_pending:
            return (
                '<p class="text-danger small mb-0">Somente solicitações pendentes podem ser rejeitadas.</p>',
                400,
            )
        return render_template(
            "admin/requests/_reject_form_fragment.html",
            req=req,
            action_url=url_for("admin.requests_reject", request_id=request_id),
        )

    @bp.route("/requests/<int:request_id>/reject", methods=["POST"])
    @login_required
    def requests_reject(request_id: int):
        require_staff()
        req = Request.query.get_or_404(request_id)
        if not req.is_pending:
            flash("Somente solicitações pendentes podem ser rejeitadas.", "danger")
            return redirect(resolve_next_url("admin.requests_list"))
        reason = (request.form.get("rejection_reason") or "").strip()
        if not reason:
            flash("Informe o motivo da rejeição.", "danger")
            return redirect(resolve_next_url("admin.requests_list"))
        reject_request(req, reason)
        db.session.commit()
        flash("Solicitação rejeitada.", "success")
        return redirect(resolve_next_url("admin.requests_list"))

    @bp.route("/requests", methods=["POST"])
    @login_required
    def requests_create():
        require_solicitante_or_admin()
        request_type = request.form.get("request_type", "").strip()
        if not request_type:
            flash("Selecione o tipo de solicitação.", "danger")
            return redirect(resolve_next_url("admin.requests_list"))
        if not validate_request_type(request_type):
            flash("Tipo de solicitação inválido.", "danger")
            return redirect(resolve_next_url("admin.requests_list"))

        payload = build_payload_from_form(request_type)
        req = Request(
            requester_id=current_user.id,
            request_type=request_type,
            status=REQUEST_STATUS_PENDING,
            payload=payload,
        )
        db.session.add(req)
        db.session.commit()
        flash("Solicitação registrada com sucesso.", "success")
        return redirect(resolve_next_url("admin.requests_list"))

    @bp.route("/requests/<int:request_id>", methods=["POST"])
    @login_required
    def requests_edit(request_id: int):
        require_solicitante_or_admin()
        req = Request.query.get_or_404(request_id)
        _require_own_or_admin(req)
        if not _require_pending(req):
            return redirect(resolve_next_url("admin.requests_list"))

        request_type = request.form.get("request_type", "").strip()
        if request_type != req.request_type:
            flash("O tipo da solicitação não pode ser alterado.", "danger")
            return redirect(resolve_next_url("admin.requests_list"))

        req.payload = build_payload_from_form(request_type)
        req.updated_at = datetime.utcnow()
        db.session.commit()
        flash("Solicitação atualizada.", "success")
        return redirect(resolve_next_url("admin.requests_list"))

    @bp.route("/requests/<int:request_id>/delete", methods=["POST"])
    @login_required
    def requests_delete(request_id: int):
        require_solicitante_or_admin()
        req = Request.query.get_or_404(request_id)
        _require_own_or_admin(req)
        if not _require_pending(req):
            return redirect(resolve_next_url("admin.requests_list"))
        db.session.delete(req)
        db.session.commit()
        flash("Solicitação excluída.", "success")
        return redirect(resolve_next_url("admin.requests_list"))

    @bp.route("/requests/bulk-delete", methods=["POST"])
    @login_required
    def requests_bulk_delete():
        require_solicitante_or_admin()
        ids = request.form.getlist("ids")
        if not ids:
            flash("Nenhuma solicitação selecionada.", "warning")
            return redirect(resolve_next_url("admin.requests_list"))

        q = Request.query.filter(
            Request.id.in_(ids),
            Request.status == REQUEST_STATUS_PENDING,
        )
        if is_solicitante():
            q = q.filter(Request.requester_id == current_user.id)

        deleted = 0
        for req in q.all():
            db.session.delete(req)
            deleted += 1
        db.session.commit()
        if deleted:
            flash(f"{deleted} solicitação(ões) excluída(s).", "success")
        else:
            flash("Nenhuma solicitação pendente elegível para exclusão.", "warning")
        return redirect(resolve_next_url("admin.requests_list"))

    @bp.get("/requests/api/locations")
    @login_required
    def requests_locations_api():
        require_solicitante_or_admin()
        return jsonify(distinct_active_locations())

    @bp.get("/requests/api/motoboy-contracts")
    @login_required
    def requests_motoboy_contracts_api():
        require_solicitante_or_admin()
        location = request.args.get("location", "").strip()
        contracts = active_motoboy_contracts_query(location or None).all()
        return jsonify([contract_to_api_dict(c) for c in contracts])

    @bp.get("/requests/api/motoboy-contract/<int:contract_id>")
    @login_required
    def requests_motoboy_contract_api(contract_id: int):
        require_solicitante_or_admin()
        contract = Contract.query.options(
            joinedload(Contract.supplier),
            joinedload(Contract.other_supplier),
        ).get_or_404(contract_id)
        return jsonify(contract_to_api_dict(contract))

    @bp.get("/requests/api/diarist-motoboys")
    @login_required
    def requests_diarist_motoboys_api():
        require_solicitante_or_admin()
        contract_id = request.args.get("contract_id", type=int)
        if not contract_id:
            return jsonify([])
        contract = Contract.query.options(joinedload(Contract.supplier)).get_or_404(
            contract_id
        )
        return jsonify(diarist_motoboys_to_api(contract))

    @bp.get("/requests/api/clients-search")
    @login_required
    def requests_clients_search():
        require_solicitante_or_admin()
        from sqlalchemy import func, or_

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
        return jsonify(
            [
                {
                    "id": c.id,
                    "label": client_display_label(c),
                    "secondary": c.document or "",
                }
                for c in results
            ]
        )
