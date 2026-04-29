"""CRUD for Motoboy contracts: uses Contract with contract_type=motoboy."""
import calendar
from datetime import date
from typing import Optional, Tuple

from flask import Blueprint, Response, current_app, flash, make_response, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename
from flask_login import current_user, login_required

from app.admin.auth_helpers import (
    require_admin,
    handle_delete_constraint_error,
    require_supervisor_or_admin,
    is_supervisor,
    resolve_next_url,
)
from app.admin.list_pagination import ADMIN_LIST_PER_PAGE, admin_list_page
from app.extensions import db
from app.models import (
    Company,
    Contract,
    ContractAbsence,
    ContractAttachment,
    CONTRACT_ATTACHMENT_KIND_LABELS_PT,
    CONTRACT_ATTACHMENT_KIND_ORDER,
    CONTRACT_TYPE_MOTOBOY,
    FinancialBatch,
    FinancialEntry,
    FinancialNature,
    Supplier,
    SUPPLIER_CLIENT,
    SUPPLIER_MOTOBOY,
    MOTOBOY_TERMINATED_STATUSES,
    BATCH_TYPE_MOTOBOY_DISTRATO,
    motoboy_supplier_operational,
)
from app.models.financial_entry import ENTRY_PAYABLE
from app.services.contract_attachment_storage import (
    delete_attachment_files_for_contract_ids,
    describe_storage_miss,
    resolve_stored_file_for_download,
    store_motoboy_contract_upload,
    stored_file_is_present,
)
from app.services.motoboy_contract_finance import motoboy_contract_in_processing_scope
from app.services.motoboy_distrato import compute_motoboy_distrato_net
from app.services.motoboy_contract_pdf import build_motoboy_contract_pdf
from app.services.motoboy_distrato_pdf import build_motoboy_distrato_pdf
from app.utils import parse_decimal_form
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased


def _billing_company_id_for_motoboy_contract(contract: Contract):
    if contract.other_supplier and contract.other_supplier.billing_company_id:
        return contract.other_supplier.billing_company_id
    if contract.supplier and contract.supplier.billing_company_id:
        return contract.supplier.billing_company_id
    return None


def _payable_natures_query():
    return (
        FinancialNature.query.filter(
            FinancialNature.is_active.is_(True),
            FinancialNature.kind.in_(["payable", "both"]),
        )
        .order_by(FinancialNature.name)
    )


def _delete_unsettled_payable(entry_id):
    if not entry_id:
        return
    entry = FinancialEntry.query.get(entry_id)
    if entry and entry.settled_at is None:
        db.session.delete(entry)


def _format_attachment_bytes(num: Optional[int]) -> str:
    if num is None:
        return "—"
    if num < 1024:
        return f"{num} B"
    if num < 1024 * 1024:
        return f"{num / 1024:.1f} KB"
    return f"{num / (1024 * 1024):.1f} MB"


def _motoboy_attachment_modal_rows(contract: Contract):
    by_kind = {a.kind: a for a in contract.attachments.all()}
    rows = []
    for kind in CONTRACT_ATTACHMENT_KIND_ORDER:
        att = by_kind.get(kind)
        rows.append(
            {
                "label": CONTRACT_ATTACHMENT_KIND_LABELS_PT[kind],
                "attachment": att,
                "original_filename": att.original_filename if att else "—",
                "size_display": _format_attachment_bytes(att.file_size if att else None),
                "created_at": att.created_at if att else None,
                "file_missing": bool(att and not stored_file_is_present(att.storage_relpath)),
            }
        )
    return rows


def _motoboys_for_contract_select(contract: Optional[Contract] = None):
    rows = (
        Supplier.query.filter_by(type=SUPPLIER_MOTOBOY)
        .filter(~Supplier.status.in_(MOTOBOY_TERMINATED_STATUSES))
        .order_by(Supplier.name)
        .all()
    )
    if contract and contract.supplier_id:
        cur = contract.supplier
        if cur and cur.type == SUPPLIER_MOTOBOY and cur.id not in {m.id for m in rows}:
            return [cur] + rows
    return rows


def _diarist_motoboys_for_select(contract: Contract, absence: Optional[ContractAbsence] = None):
    """Diaristas ativos do mesmo UF do titular; na edição inclui o atual se não estiver na lista."""
    titular = contract.supplier
    uf = (titular.state or "").strip().upper() if titular else ""
    q = (
        Supplier.query.filter_by(type=SUPPLIER_MOTOBOY, is_active=True, is_diarist=True)
        .filter(~Supplier.status.in_(MOTOBOY_TERMINATED_STATUSES))
    )
    if uf:
        q = q.filter(func.upper(Supplier.state) == uf)
    rows = q.order_by(Supplier.name).all()
    if absence and absence.substitute_supplier_id:
        current = absence.substitute_supplier
        if current and current.id not in {m.id for m in rows}:
            return [current] + rows
    return rows


def _render_motoboy_contract_form(
    contract: Optional[Contract],
    motoboys,
    clients,
    action_url: str,
):
    is_modal_request = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.headers.get("Turbo-Frame") == "main-content"
    )
    template = (
        "admin/motoboy_contracts/_form_fragment.html"
        if is_modal_request
        else "admin/motoboy_contracts/form.html"
    )
    return render_template(
        template,
        contract=contract,
        motoboys=motoboys,
        clients=clients,
        action_url=action_url,
    )


def _resolve_substitute_amount_from_form(
    contract: Contract, substitute_id: Optional[int]
) -> Tuple[Optional[float], Optional[str]]:
    """
    Valor da conta a pagar do diarista a partir do formulário.
    Se o campo vier vazio, usa o valor de falta do contrato (quando existir).
    """
    if not substitute_id:
        return None, None
    raw = (request.form.get("substitute_amount") or "").strip()
    parsed = parse_decimal_form(raw) if raw else None
    if raw and parsed is None:
        return None, "Valor do pagamento ao diarista inválido."
    if parsed is not None:
        if parsed <= 0:
            return None, "O valor para o diarista deve ser maior que zero."
        return parsed, None
    if contract.missing_value is not None:
        return float(contract.missing_value), None
    return None, "Informe o valor a pagar ao diarista ou cadastre o valor de falta no contrato."


def _effective_substitute_pay_amount(
    contract: Contract, absence: ContractAbsence
) -> Optional[float]:
    """Valor usado no lançamento a pagar (registro novo ou legado sem substitute_amount)."""
    if absence.substitute_amount is not None:
        try:
            return float(absence.substitute_amount)
        except (TypeError, ValueError):
            return None
    if contract.missing_value is not None:
        try:
            return float(contract.missing_value)
        except (TypeError, ValueError):
            return None
    return None


def _sync_absence_substitute_payable(contract: Contract, absence: ContractAbsence) -> Tuple[bool, Optional[str]]:
    """
    Cria/atualiza/remove conta a pagar conforme motoboy diarista (substitute_supplier_id) e natureza.
    Retorna (ok, mensagem_erro).
    """
    sub_id = absence.substitute_supplier_id
    nature_id = absence.financial_nature_id

    if not sub_id:
        _delete_unsettled_payable(absence.payable_entry_id)
        absence.payable_entry_id = None
        absence.financial_nature_id = None
        return True, None

    if not nature_id:
        return False, "Com motoboy diarista (quem cobriu), a natureza financeira é obrigatória."

    sub = Supplier.query.filter_by(id=sub_id, type=SUPPLIER_MOTOBOY).first()
    if not sub or not sub.is_diarist or not motoboy_supplier_operational(sub):
        return False, "O motoboy que recebe a conta a pagar deve ser diarista ativo (não encerrado) no cadastro."

    pay_amount = _effective_substitute_pay_amount(contract, absence)
    if pay_amount is None or pay_amount <= 0:
        return (
            False,
            "Defina o valor a pagar ao diarista ou o valor de falta no contrato para gerar a conta a pagar.",
        )

    company_id = _billing_company_id_for_motoboy_contract(contract)
    if not company_id:
        return False, "Não foi possível determinar a empresa (faturamento do cliente ou do motoboy titular)."

    desc = (
        f"Diarista cobriu falta {absence.absence_date.strftime('%d/%m/%Y')} — "
        f"titular {contract.supplier.name}"
    )
    ref = f"contract_absence:{absence.id}"

    if absence.payable_entry_id:
        pe = FinancialEntry.query.get(absence.payable_entry_id)
        if pe:
            if pe.settled_at is not None:
                return True, None
            pe.company_id = company_id
            pe.financial_nature_id = nature_id
            pe.entry_type = ENTRY_PAYABLE
            pe.description = desc
            pe.amount = pay_amount
            pe.due_date = absence.absence_date
            pe.supplier_id = sub_id
            pe.reference = ref
            return True, None

    entry = FinancialEntry(
        company_id=company_id,
        account_id=None,
        financial_nature_id=nature_id,
        entry_type=ENTRY_PAYABLE,
        description=desc,
        amount=pay_amount,
        due_date=absence.absence_date,
        reference=ref,
        supplier_id=sub_id,
    )
    db.session.add(entry)
    db.session.flush()
    absence.payable_entry_id = entry.id
    return True, None


def register_routes(bp: Blueprint) -> None:
    @bp.route("/motoboy-contracts/form")
    @login_required
    def motoboy_contracts_form_new():
        require_admin()
        motoboys = _motoboys_for_contract_select()
        clients = Supplier.query.filter_by(type=SUPPLIER_CLIENT).order_by(
            func.coalesce(Supplier.trade_name, Supplier.legal_name, Supplier.name)
        ).all()
        return render_template(
            "admin/motoboy_contracts/_form_fragment.html",
            contract=None,
            motoboys=motoboys,
            clients=clients,
            action_url=url_for("admin.motoboy_contracts_create"),
        )

    @bp.route("/motoboy-contracts/<int:contract_id>/form")
    @login_required
    def motoboy_contracts_form_edit(contract_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        motoboys = _motoboys_for_contract_select(contract)
        clients = Supplier.query.filter_by(type=SUPPLIER_CLIENT).order_by(
            func.coalesce(Supplier.trade_name, Supplier.legal_name, Supplier.name)
        ).all()
        return render_template(
            "admin/motoboy_contracts/_form_fragment.html",
            contract=contract,
            motoboys=motoboys,
            clients=clients,
            action_url=url_for("admin.motoboy_contracts_edit", contract_id=contract_id),
        )

    @bp.route("/motoboy-contracts/<int:contract_id>/attachments/form")
    @login_required
    def motoboy_contract_attachments_form(contract_id: int):
        require_supervisor_or_admin()
        contract = Contract.query.filter_by(
            id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY
        ).first_or_404()
        kind_choices = [
            (k, CONTRACT_ATTACHMENT_KIND_LABELS_PT[k]) for k in CONTRACT_ATTACHMENT_KIND_ORDER
        ]
        return render_template(
            "admin/motoboy_contracts/_attachments_fragment.html",
            contract=contract,
            attachment_rows=_motoboy_attachment_modal_rows(contract),
            kind_choices=kind_choices,
            upload_url=url_for(
                "admin.motoboy_contract_attachment_upload", contract_id=contract_id
            ),
            can_upload=bool(getattr(current_user, "is_admin", False)),
        )

    @bp.post("/motoboy-contracts/<int:contract_id>/attachments")
    @login_required
    def motoboy_contract_attachment_upload(contract_id: int):
        require_admin()
        contract = Contract.query.filter_by(
            id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY
        ).first_or_404()
        kind = (request.form.get("kind") or "").strip()
        file_storage = request.files.get("file")
        try:
            store_motoboy_contract_upload(contract, kind, file_storage)
            db.session.commit()
            flash("Anexo salvo com sucesso.", "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        return redirect(resolve_next_url("admin.motoboy_contracts_list"))

    @bp.route(
        "/motoboy-contracts/<int:contract_id>/attachments/<int:attachment_id>/download"
    )
    @login_required
    def motoboy_contract_attachment_download(contract_id: int, attachment_id: int):
        require_supervisor_or_admin()
        Contract.query.filter_by(
            id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY
        ).first_or_404()
        att = ContractAttachment.query.filter_by(
            id=attachment_id, contract_id=contract_id
        ).first_or_404()
        path = resolve_stored_file_for_download(att.storage_relpath)
        if path is None:
            info = describe_storage_miss(att.storage_relpath)
            current_app.logger.warning(
                "Anexo de contrato sem arquivo no disco: contract_id=%s attachment_id=%s relpath=%s reason=%s root=%s expected=%s",
                contract_id,
                attachment_id,
                att.storage_relpath,
                info.get("reason"),
                info.get("upload_root"),
                info.get("expected_path"),
            )
            return render_template(
                "admin/attachment_missing.html",
                original_filename=att.original_filename,
                storage_relpath=att.storage_relpath,
                upload_root=info.get("upload_root"),
                back_url=url_for("admin.motoboy_contracts_list"),
            ), 404
        dl_name = secure_filename(att.original_filename) or "anexo"
        return send_file(
            path,
            mimetype=att.content_type or "application/octet-stream",
            as_attachment=False,
            download_name=dl_name,
        )

    @bp.post(
        "/motoboy-contracts/<int:contract_id>/attachments/<int:attachment_id>/delete"
    )
    @login_required
    def motoboy_contract_attachment_delete(contract_id: int, attachment_id: int):
        require_admin()
        Contract.query.filter_by(
            id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY
        ).first_or_404()
        att = ContractAttachment.query.filter_by(
            id=attachment_id, contract_id=contract_id
        ).first_or_404()
        db.session.delete(att)
        db.session.commit()
        flash("Anexo excluído.", "info")
        return redirect(resolve_next_url("admin.motoboy_contracts_list"))

    @bp.route("/motoboy-contracts")
    @login_required
    def motoboy_contracts_list():
        require_supervisor_or_admin()
        motoboy_name = request.args.get("motoboy_name", "").strip()
        client_name = request.args.get("client_name", "").strip()

        SupplierMotoboy = aliased(Supplier)
        SupplierClient = aliased(Supplier)
        query = (
            Contract.query.filter_by(contract_type=CONTRACT_TYPE_MOTOBOY)
            .join(SupplierMotoboy, Contract.supplier_id == SupplierMotoboy.id)
            .outerjoin(SupplierClient, Contract.other_supplier_id == SupplierClient.id)
        )
        if motoboy_name:
            query = query.filter(SupplierMotoboy.name.ilike(f"%{motoboy_name}%"))
        if client_name:
            query = query.filter(
                or_(
                    SupplierClient.legal_name.ilike(f"%{client_name}%"),
                    SupplierClient.name.ilike(f"%{client_name}%"),
                    SupplierClient.trade_name.ilike(f"%{client_name}%"),
                )
            )
        pagination = query.order_by(Contract.start_date.desc()).paginate(
            page=admin_list_page(), per_page=ADMIN_LIST_PER_PAGE, error_out=False
        )

        return render_template(
            "admin/motoboy_contracts/list.html",
            contracts=pagination.items,
            pagination=pagination,
            filters={"motoboy_name": motoboy_name, "client_name": client_name},
        )

    @bp.route("/motoboy-contracts/create", methods=["GET", "POST"])
    @login_required
    def motoboy_contracts_create():
        require_admin()
        motoboys = _motoboys_for_contract_select()
        clients = Supplier.query.filter_by(type=SUPPLIER_CLIENT).order_by(
            func.coalesce(Supplier.trade_name, Supplier.legal_name, Supplier.name)
        ).all()

        if request.method == "POST":
            motoboy_id = request.form.get("motoboy_id")
            client_id_raw = (request.form.get("client_id") or "").strip()
            start_date_str = request.form.get("start_date", "")
            end_date_str = request.form.get("end_date", "")
            location = request.form.get("location", "").strip()
            service_value = parse_decimal_form(request.form.get("service_value"))
            bonus_value = parse_decimal_form(request.form.get("bonus_value"))
            missing_value = parse_decimal_form(request.form.get("missing_value"))
            advance_value = parse_decimal_form(request.form.get("advance_value"))
            is_blocked = request.form.get("is_blocked") == "1"

            if not motoboy_id or not start_date_str:
                flash("Motoboy e data de início são obrigatórios.", "danger")
            elif not client_id_raw:
                flash("Cliente é obrigatório no contrato de motoboy.", "danger")
            else:
                try:
                    client_pk = int(client_id_raw)
                except ValueError:
                    flash("Cliente inválido.", "danger")
                else:
                    client_row = Supplier.query.filter_by(id=client_pk, type=SUPPLIER_CLIENT).first()
                    if not client_row:
                        flash("Selecione um cliente válido (cadastro de cliente).", "danger")
                    else:
                        mb = Supplier.query.filter_by(id=int(motoboy_id), type=SUPPLIER_MOTOBOY).first()
                        if not mb:
                            flash("Motoboy inválido.", "danger")
                        elif not motoboy_supplier_operational(mb):
                            flash(
                                "Não é possível criar contrato para motoboy encerrado no cadastro.",
                                "danger",
                            )
                        if (
                            mb
                            and motoboy_supplier_operational(mb)
                        ):
                            start_date_val = date.fromisoformat(start_date_str)
                            end_date_val = date.fromisoformat(end_date_str) if end_date_str else None
                            contract = Contract(
                                supplier_id=int(motoboy_id),
                                contract_type=CONTRACT_TYPE_MOTOBOY,
                                other_supplier_id=client_pk,
                                start_date=start_date_val,
                                end_date=end_date_val,
                                location=location or None,
                                service_value=service_value,
                                bonus_value=bonus_value,
                                missing_value=missing_value,
                                advance_value=advance_value,
                                is_blocked=is_blocked,
                            )
                            db.session.add(contract)
                            db.session.commit()
                            flash("Contrato de motoboy criado com sucesso.", "success")
                            return redirect(resolve_next_url("admin.motoboy_contracts_list"))

        return _render_motoboy_contract_form(
            contract=None,
            motoboys=motoboys,
            clients=clients,
            action_url=url_for("admin.motoboy_contracts_create"),
        )

    @bp.route("/motoboy-contracts/<int:contract_id>/edit", methods=["GET", "POST"])
    @login_required
    def motoboy_contracts_edit(contract_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        motoboys = _motoboys_for_contract_select(contract)
        clients = Supplier.query.filter_by(type=SUPPLIER_CLIENT).order_by(
            func.coalesce(Supplier.trade_name, Supplier.legal_name, Supplier.name)
        ).all()

        if request.method == "POST":
            contract.supplier_id = int(request.form.get("motoboy_id"))
            client_id_raw = (request.form.get("client_id") or "").strip()
            start_date_str = request.form.get("start_date", "")
            end_date_str = request.form.get("end_date", "")
            contract.location = request.form.get("location", "").strip() or None
            contract.service_value = parse_decimal_form(request.form.get("service_value"))
            contract.bonus_value = parse_decimal_form(request.form.get("bonus_value"))
            contract.missing_value = parse_decimal_form(request.form.get("missing_value"))
            contract.advance_value = parse_decimal_form(request.form.get("advance_value"))
            contract.is_blocked = request.form.get("is_blocked") == "1"

            if not contract.supplier_id or not start_date_str:
                flash("Motoboy e data de início são obrigatórios.", "danger")
            elif not client_id_raw:
                flash("Cliente é obrigatório no contrato de motoboy.", "danger")
            else:
                try:
                    client_pk = int(client_id_raw)
                except ValueError:
                    flash("Cliente inválido.", "danger")
                else:
                    client_row = Supplier.query.filter_by(id=client_pk, type=SUPPLIER_CLIENT).first()
                    if not client_row:
                        flash("Selecione um cliente válido (cadastro de cliente).", "danger")
                    else:
                        mb = Supplier.query.filter_by(
                            id=contract.supplier_id, type=SUPPLIER_MOTOBOY
                        ).first()
                        if not mb:
                            flash("Motoboy inválido.", "danger")
                        else:
                            contract.other_supplier_id = client_pk
                            contract.start_date = date.fromisoformat(start_date_str)
                            contract.end_date = (
                                date.fromisoformat(end_date_str) if end_date_str else None
                            )
                            db.session.commit()
                            flash("Contrato de motoboy atualizado com sucesso.", "success")
                            return redirect(resolve_next_url("admin.motoboy_contracts_list"))

        return _render_motoboy_contract_form(
            contract=contract,
            motoboys=motoboys,
            clients=clients,
            action_url=url_for("admin.motoboy_contracts_edit", contract_id=contract_id),
        )

    @bp.route("/motoboy-contracts/<int:contract_id>/falta/form")
    @login_required
    def motoboy_contract_falta_form(contract_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        diarist_motoboys = _diarist_motoboys_for_select(contract)
        financial_natures = _payable_natures_query().all()
        return render_template(
            "admin/motoboy_contracts/_falta_form_fragment.html",
            contract=contract,
            action_url=url_for("admin.motoboy_contract_falta_create", contract_id=contract_id),
            default_date=date.today().isoformat(),
            diarist_motoboys=diarist_motoboys,
            financial_natures=financial_natures,
        )

    @bp.route("/motoboy-contracts/<int:contract_id>/falta", methods=["POST"])
    @login_required
    def motoboy_contract_falta_create(contract_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        if not motoboy_contract_in_processing_scope(contract):
            flash(
                "Não é possível registrar falta: contrato bloqueado ou motoboy encerrado no cadastro.",
                "danger",
            )
            return redirect(resolve_next_url("admin.motoboy_contracts_list"))
        absence_date_str = request.form.get("absence_date", "").strip()
        justification = request.form.get("justification", "").strip()

        def _parse_id(name):
            raw = (request.form.get(name) or "").strip()
            if not raw:
                return None
            try:
                return int(raw)
            except ValueError:
                return None

        substitute_id = _parse_id("substitute_supplier_id")
        nature_id = _parse_id("financial_nature_id")

        if not absence_date_str or not justification:
            flash("Dia e justificativa são obrigatórios.", "danger")
            return redirect(resolve_next_url("admin.motoboy_contracts_list"))
        try:
            absence_date = date.fromisoformat(absence_date_str)
        except ValueError:
            flash("Data inválida.", "danger")
            return redirect(resolve_next_url("admin.motoboy_contracts_list"))

        if substitute_id:
            if not nature_id:
                flash("Com motoboy diarista (quem cobriu), a natureza financeira é obrigatória.", "danger")
                return redirect(resolve_next_url("admin.motoboy_contracts_list"))
            sub = Supplier.query.filter_by(id=substitute_id, type=SUPPLIER_MOTOBOY).first()
            if not sub or not sub.is_diarist or not motoboy_supplier_operational(sub):
                flash(
                    "O motoboy selecionado deve ser diarista ativo (não encerrado) no cadastro.",
                    "danger",
                )
                return redirect(resolve_next_url("admin.motoboy_contracts_list"))
            tit = contract.supplier
            if tit and sub:
                uf_t = (tit.state or "").strip().upper()
                uf_s = (sub.state or "").strip().upper()
                if uf_t and uf_s and uf_t != uf_s:
                    flash("O diarista deve ser do mesmo estado (UF) do motoboy titular.", "danger")
                    return redirect(resolve_next_url("admin.motoboy_contracts_list"))
        else:
            nature_id = None

        resolved_substitute_amount, amt_err = _resolve_substitute_amount_from_form(
            contract, substitute_id
        )
        if amt_err:
            flash(amt_err, "danger")
            return redirect(resolve_next_url("admin.motoboy_contracts_list"))

        existing = ContractAbsence.query.filter_by(
            contract_id=contract_id,
            absence_date=absence_date,
        ).first()
        if existing:
            flash("Já existe uma falta registrada para este contrato nesta data.", "danger")
            return redirect(resolve_next_url("admin.motoboy_contracts_list"))
        absence = ContractAbsence(
            contract_id=contract_id,
            absence_date=absence_date,
            justification=justification,
            substitute_supplier_id=substitute_id,
            financial_nature_id=nature_id,
            substitute_name=None,
            substitute_document=None,
            substitute_pix=None,
            substitute_amount=resolved_substitute_amount,
        )
        db.session.add(absence)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            flash("Já existe uma falta registrada para este contrato nesta data.", "danger")
            return redirect(resolve_next_url("admin.motoboy_contracts_list"))

        ok, err = _sync_absence_substitute_payable(contract, absence)
        if not ok:
            db.session.rollback()
            flash(err or "Não foi possível gerar a conta a pagar.", "danger")
            return redirect(resolve_next_url("admin.motoboy_contracts_list"))

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Já existe uma falta registrada para este contrato nesta data.", "danger")
            return redirect(resolve_next_url("admin.motoboy_contracts_list"))
        flash("Falta registrada com sucesso.", "success")
        if substitute_id:
            flash("Conta a pagar gerada para o motoboy diarista (quem cobriu).", "info")
        return redirect(resolve_next_url("admin.motoboy_contracts_list"))

    @bp.route("/motoboy-contracts/<int:contract_id>/falta/<int:absence_id>/form")
    @login_required
    def motoboy_contract_falta_edit_form(contract_id: int, absence_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        absence = ContractAbsence.query.filter_by(
            id=absence_id, contract_id=contract_id
        ).first_or_404()
        diarist_motoboys = _diarist_motoboys_for_select(contract, absence)
        financial_natures = _payable_natures_query().all()
        return render_template(
            "admin/motoboy_contracts/_falta_edit_fragment.html",
            contract=contract,
            absence=absence,
            action_url=url_for("admin.motoboy_contract_falta_update", contract_id=contract_id, absence_id=absence_id),
            diarist_motoboys=diarist_motoboys,
            financial_natures=financial_natures,
        )

    @bp.route("/motoboy-contracts/<int:contract_id>/falta/<int:absence_id>", methods=["POST"])
    @login_required
    def motoboy_contract_falta_update(contract_id: int, absence_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        if not motoboy_contract_in_processing_scope(contract):
            flash(
                "Não é possível alterar falta: contrato bloqueado ou motoboy encerrado no cadastro.",
                "danger",
            )
            return redirect(resolve_next_url("admin.motoboy_contracts_list"))
        absence = ContractAbsence.query.filter_by(
            id=absence_id, contract_id=contract_id
        ).first_or_404()
        absence_date_str = request.form.get("absence_date", "").strip()
        justification = request.form.get("justification", "").strip()

        def _parse_id(name):
            raw = (request.form.get(name) or "").strip()
            if not raw:
                return None
            try:
                return int(raw)
            except ValueError:
                return None

        substitute_id = _parse_id("substitute_supplier_id")
        nature_id = _parse_id("financial_nature_id")

        if not absence_date_str or not justification:
            flash("Data e justificativa são obrigatórios.", "danger")
            return redirect(resolve_next_url("admin.motoboy_contracts_list"))
        try:
            absence_date = date.fromisoformat(absence_date_str)
        except ValueError:
            flash("Data inválida.", "danger")
            return redirect(resolve_next_url("admin.motoboy_contracts_list"))

        settled_payable = None
        if absence.payable_entry_id:
            settled_payable = FinancialEntry.query.get(absence.payable_entry_id)

        if settled_payable and settled_payable.settled_at is not None:
            substitute_id = absence.substitute_supplier_id
            nature_id = absence.financial_nature_id
        else:
            if substitute_id:
                if not nature_id:
                    flash("Com motoboy diarista (quem cobriu), a natureza financeira é obrigatória.", "danger")
                    return redirect(resolve_next_url("admin.motoboy_contracts_list"))
                sub = Supplier.query.filter_by(id=substitute_id, type=SUPPLIER_MOTOBOY).first()
                if not sub or not sub.is_diarist or not motoboy_supplier_operational(sub):
                    flash(
                        "O motoboy selecionado deve ser diarista ativo (não encerrado) no cadastro.",
                        "danger",
                    )
                    return redirect(resolve_next_url("admin.motoboy_contracts_list"))
                tit = contract.supplier
                if tit and sub:
                    uf_t = (tit.state or "").strip().upper()
                    uf_s = (sub.state or "").strip().upper()
                    if uf_t and uf_s and uf_t != uf_s:
                        flash("O diarista deve ser do mesmo estado (UF) do motoboy titular.", "danger")
                        return redirect(resolve_next_url("admin.motoboy_contracts_list"))
            else:
                nature_id = None

            resolved_substitute_amount, amt_err = _resolve_substitute_amount_from_form(
                contract, substitute_id
            )
            if amt_err:
                flash(amt_err, "danger")
                return redirect(resolve_next_url("admin.motoboy_contracts_list"))

        other = ContractAbsence.query.filter_by(
            contract_id=contract_id,
            absence_date=absence_date,
        ).filter(ContractAbsence.id != absence_id).first()
        if other:
            flash("Já existe outra falta para este contrato nesta data.", "danger")
            return redirect(resolve_next_url("admin.motoboy_contracts_list"))
        absence.absence_date = absence_date
        absence.justification = justification
        absence.substitute_supplier_id = substitute_id
        absence.financial_nature_id = nature_id
        if not (settled_payable and settled_payable.settled_at):
            absence.substitute_amount = resolved_substitute_amount

        ok, err = _sync_absence_substitute_payable(contract, absence)
        if not ok:
            db.session.rollback()
            flash(err or "Não foi possível atualizar a conta a pagar.", "danger")
            return redirect(resolve_next_url("admin.motoboy_contracts_list"))

        db.session.commit()
        flash("Falta atualizada com sucesso.", "success")
        return redirect(resolve_next_url("admin.motoboy_contracts_list"))

    @bp.post("/motoboy-contracts/<int:contract_id>/falta/<int:absence_id>/delete")
    @login_required
    def motoboy_contract_falta_delete(contract_id: int, absence_id: int):
        require_admin()
        next_url = resolve_next_url("admin.motoboy_contracts_list")
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        absence = ContractAbsence.query.filter_by(
            id=absence_id, contract_id=contract_id
        ).first_or_404()
        _delete_unsettled_payable(absence.payable_entry_id)
        db.session.delete(absence)
        db.session.commit()
        flash("Falta excluída.", "info")
        return redirect(next_url)

    @bp.route("/motoboy-contracts/<int:contract_id>/calendar")
    @login_required
    def motoboy_contract_calendar(contract_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        month_param = request.args.get("month", "").strip()
        try:
            if month_param:
                year, month = map(int, month_param.split("-"))
                if month < 1 or month > 12:
                    raise ValueError("invalid month")
                current = date(year, month, 1)
            else:
                current = date.today().replace(day=1)
        except (ValueError, AttributeError):
            current = date.today().replace(day=1)
        year, month = current.year, current.month
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        absences = (
            ContractAbsence.query.filter(
                ContractAbsence.contract_id == contract_id,
                ContractAbsence.absence_date >= current,
                ContractAbsence.absence_date <= month_end,
            )
            .order_by(ContractAbsence.absence_date)
            .all()
        )
        absence_days = {a.absence_date.day for a in absences}
        absences_by_day = {a.absence_date.day: a for a in absences}
        # Semanas começando no domingo (cabeçalho Dom–Sáb). monthcalendar() é Seg–Dom;
        # só rotacionar w[6] pra frente quebra a ordem (coloca o domingo *final* da semana ISO na 1ª coluna).
        cal_sun = calendar.Calendar(firstweekday=calendar.SUNDAY)
        weeks_raw = cal_sun.monthdayscalendar(year, month)
        weekdays = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
        weeks = [
            [(d, d in absence_days if d else False) for d in w]
            for w in weeks_raw
        ]
        prev_month = date(year - 1, 12, 1) if month == 1 else date(year, month - 1, 1)
        next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        _MONTH_NAMES = ("", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")
        return render_template(
            "admin/motoboy_contracts/_calendar_fragment.html",
            contract=contract,
            current=current,
            year=year,
            month=month,
            month_name=_MONTH_NAMES[month],
            weekdays=weekdays,
            weeks=weeks,
            absences=absences,
            absences_by_day=absences_by_day,
            calendar_url=url_for("admin.motoboy_contract_calendar", contract_id=contract_id),
            prev_month_arg=prev_month.strftime("%Y-%m"),
            next_month_arg=next_month.strftime("%Y-%m"),
            contract_id=contract_id,
        )

    @bp.route("/motoboy-contracts/<int:contract_id>/distrato/form")
    @login_required
    def motoboy_contract_distrato_form(contract_id: int):
        require_admin()
        contract = Contract.query.filter_by(
            id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY
        ).first_or_404()
        next_url = request.args.get("next") or url_for("admin.motoboy_contracts_list")
        if not (isinstance(next_url, str) and next_url.startswith("/")):
            next_url = url_for("admin.motoboy_contracts_list")
        if contract.end_date is None:
            return Response(
                '<p class="text-danger small mb-0">Cadastre a <strong>data de distrato</strong> no contrato antes de gerar o lançamento.</p>',
                mimetype="text/html; charset=utf-8",
            )
        natures = _payable_natures_query().all()
        companies = Company.query.order_by(Company.legal_name).all()
        return render_template(
            "admin/motoboy_contracts/_distrato_form_fragment.html",
            contract=contract,
            companies=companies,
            natures=natures,
            action_url=url_for(
                "admin.motoboy_contract_distrato_create", contract_id=contract_id
            ),
            next_url=next_url,
            default_charge_date=date.today().isoformat(),
        )

    @bp.post("/motoboy-contracts/<int:contract_id>/distrato")
    @login_required
    def motoboy_contract_distrato_create(contract_id: int):
        require_admin()
        next_url = resolve_next_url("admin.motoboy_contracts_list")
        contract = Contract.query.filter_by(
            id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY
        ).first_or_404()
        charge_date_str = (request.form.get("charge_date") or "").strip()
        nature_id = request.form.get("financial_nature_id", type=int)
        company_id = request.form.get("company_id", type=int)

        if not contract.end_date:
            flash("Cadastre a data de distrato no contrato.", "danger")
            return redirect(next_url)
        if not charge_date_str or not nature_id or not company_id:
            flash("Data de cobrança, natureza financeira e empresa são obrigatórios.", "danger")
            return redirect(next_url)
        try:
            charge_date = date.fromisoformat(charge_date_str)
        except ValueError:
            flash("Data de cobrança inválida.", "danger")
            return redirect(next_url)

        nature = FinancialNature.query.get(nature_id)
        if (
            not nature
            or not nature.is_active
            or nature.kind not in ("payable", "both")
        ):
            flash("Natureza financeira inválida ou inativa.", "danger")
            return redirect(next_url)
        company = Company.query.get(company_id)
        if not company:
            flash("Empresa inválida.", "danger")
            return redirect(next_url)

        if contract.supplier and not motoboy_supplier_operational(contract.supplier):
            flash("Motoboy encerrado no cadastro.", "danger")
            return redirect(next_url)

        net, err = compute_motoboy_distrato_net(contract)
        batch_type = BATCH_TYPE_MOTOBOY_DISTRATO

        if err:
            flash(err, "danger")
            return redirect(next_url)
        if net is None:
            flash("Não foi possível calcular o valor do distrato.", "danger")
            return redirect(next_url)

        year, month = contract.end_date.year, contract.end_date.month
        desc = f"Distrato contrato motoboy #{contract.id} - {year}-{month:02d}"

        if FinancialEntry.query.filter_by(description=desc).first():
            flash("Já existe um lançamento com esta descrição para este contrato e período.", "warning")
            return redirect(next_url)

        client_supplier_id = contract.other_supplier_id
        batch = FinancialBatch.query.filter_by(
            batch_type=batch_type,
            year=year,
            month=month,
            financial_nature_id=nature_id,
            client_supplier_id=client_supplier_id,
            company_id=company_id,
        ).first()
        if batch is None:
            batch = FinancialBatch(
                batch_type=batch_type,
                year=year,
                month=month,
                financial_nature_id=nature_id,
                charge_date=charge_date,
                company_id=company_id,
                client_supplier_id=client_supplier_id,
                created_by_id=getattr(current_user, "id", None),
            )
            db.session.add(batch)
            db.session.flush()

        entry = FinancialEntry(
            company_id=company_id,
            account_id=None,
            financial_nature_id=nature_id,
            supplier_id=contract.supplier_id,
            entry_type=ENTRY_PAYABLE,
            description=desc,
            amount=net,
            due_date=charge_date,
            settled_at=None,
            reference=None,
            financial_batch_id=batch.id,
        )
        db.session.add(entry)
        db.session.commit()
        flash("Lançamento de distrato gerado com sucesso.", "success")
        return redirect(next_url)

    @bp.route("/motoboy-contracts/<int:contract_id>/contract/form")
    @login_required
    def motoboy_contract_print_form(contract_id: int):
        require_admin()
        next_url = request.args.get("next") or url_for("admin.motoboy_contracts_list")
        contract = Contract.query.filter_by(
            id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY
        ).first_or_404()
        if contract.end_date is not None:
            return Response(
                '<p class="text-danger small mb-0">A geração só é permitida para contrato vigente (sem data de distrato).</p>',
                mimetype="text/html; charset=utf-8",
            )
        companies = (
            Company.query.filter(Company.allow_contract_generation.is_(True))
            .order_by(Company.legal_name)
            .all()
        )
        if not companies:
            return Response(
                '<p class="text-danger small mb-0">Nenhuma empresa está habilitada para geração de contrato. Ative em Empresas → Permite geração de contrato?.</p>',
                mimetype="text/html; charset=utf-8",
            )
        return render_template(
            "admin/motoboy_contracts/_print_contract_form_fragment.html",
            contract=contract,
            companies=companies,
            action_url=url_for("admin.motoboy_contract_print_pdf", contract_id=contract_id),
            next_url=next_url,
            default_signed_date=date.today().isoformat(),
        )

    @bp.post("/motoboy-contracts/<int:contract_id>/contract/pdf")
    @login_required
    def motoboy_contract_print_pdf(contract_id: int):
        require_admin()
        next_url = resolve_next_url("admin.motoboy_contracts_list")
        contract = Contract.query.filter_by(
            id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY
        ).first_or_404()
        if contract.end_date is not None:
            flash("A geração do contrato só é permitida para contrato vigente (sem data de distrato).", "danger")
            return redirect(next_url)
        company_id = request.form.get("company_id", type=int)
        if not company_id:
            flash("Selecione a empresa para gerar o contrato.", "danger")
            return redirect(next_url)
        signed_date_raw = (request.form.get("signed_date") or "").strip()
        if not signed_date_raw:
            flash("Informe a data do contrato.", "danger")
            return redirect(next_url)
        try:
            signed_date = date.fromisoformat(signed_date_raw)
        except ValueError:
            flash("Data do contrato inválida.", "danger")
            return redirect(next_url)
        company = Company.query.get(company_id)
        if not company:
            flash("Empresa inválida.", "danger")
            return redirect(next_url)
        if not company.allow_contract_generation:
            flash("Esta empresa não está habilitada para geração de contrato.", "danger")
            return redirect(next_url)

        def _endereco_estruturado_ok(ent) -> bool:
            if not ent:
                return False
            return (
                bool((ent.street or "").strip())
                and bool((ent.neighborhood or "").strip())
                and bool((ent.city or "").strip())
                and bool((ent.state or "").strip())
            )

        if not _endereco_estruturado_ok(company):
            flash("Preencha rua, bairro, cidade e UF da empresa antes de gerar o contrato.", "danger")
            return redirect(next_url)
        if not _endereco_estruturado_ok(contract.supplier):
            flash("Preencha rua, bairro, cidade e UF do motoboy antes de gerar o contrato.", "danger")
            return redirect(next_url)
        if not contract.supplier.document_secondary:
            flash("Preencha o CNPJ do motoboy (campo CNPJ no cadastro) antes de gerar o contrato.", "danger")
            return redirect(next_url)
        try:
            pdf_bytes = build_motoboy_contract_pdf(contract, company, signed_date)
        except RuntimeError:
            flash("Geração de PDF indisponível: instale o pacote 'reportlab' no ambiente.", "danger")
            return redirect(next_url)

        filename = f"contrato_motoboy_{contract.id}.pdf"
        resp = make_response(pdf_bytes)
        resp.headers["Content-Type"] = "application/pdf"
        resp.headers["Content-Disposition"] = f'inline; filename="{filename}"'
        return resp

    @bp.route("/motoboy-contracts/<int:contract_id>/distrato/print/form")
    @login_required
    def motoboy_contract_distrato_print_form(contract_id: int):
        require_admin()
        next_url = request.args.get("next") or url_for("admin.motoboy_contracts_list")
        contract = Contract.query.filter_by(
            id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY
        ).first_or_404()
        if contract.end_date is None:
            return Response(
                '<p class="text-danger small mb-0">A impressão do distrato só é permitida quando a '
                "<strong>data de distrato</strong> estiver preenchida no contrato.</p>",
                mimetype="text/html; charset=utf-8",
            )
        companies = (
            Company.query.filter(Company.allow_contract_generation.is_(True))
            .order_by(Company.legal_name)
            .all()
        )
        if not companies:
            return Response(
                '<p class="text-danger small mb-0">Nenhuma empresa está habilitada para geração de contrato/distrato. '
                "Ative em Empresas → Permite geração de contrato?.</p>",
                mimetype="text/html; charset=utf-8",
            )
        return render_template(
            "admin/motoboy_contracts/_distrato_print_form_fragment.html",
            contract=contract,
            companies=companies,
            action_url=url_for(
                "admin.motoboy_contract_distrato_print_pdf", contract_id=contract_id
            ),
            next_url=next_url,
            default_document_date=date.today().isoformat(),
        )

    @bp.post("/motoboy-contracts/<int:contract_id>/distrato/print/pdf")
    @login_required
    def motoboy_contract_distrato_print_pdf(contract_id: int):
        require_admin()
        next_url = resolve_next_url("admin.motoboy_contracts_list")
        contract = Contract.query.filter_by(
            id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY
        ).first_or_404()
        if contract.end_date is None:
            flash(
                "A impressão do distrato só é permitida quando a data de distrato estiver preenchida.",
                "danger",
            )
            return redirect(next_url)
        company_id = request.form.get("company_id", type=int)
        if not company_id:
            flash("Selecione a empresa para gerar o distrato em PDF.", "danger")
            return redirect(next_url)
        document_date_raw = (request.form.get("document_date") or "").strip()
        if not document_date_raw:
            flash("Informe a data do documento (assinatura do distrato).", "danger")
            return redirect(next_url)
        try:
            document_date = date.fromisoformat(document_date_raw)
        except ValueError:
            flash("Data do documento inválida.", "danger")
            return redirect(next_url)
        company = Company.query.get(company_id)
        if not company:
            flash("Empresa inválida.", "danger")
            return redirect(next_url)
        if not company.allow_contract_generation:
            flash("Esta empresa não está habilitada para geração de contrato/distrato.", "danger")
            return redirect(next_url)

        if not contract.supplier.document_secondary:
            flash(
                "Preencha o CNPJ do motoboy (campo CNPJ no cadastro) antes de gerar o distrato.",
                "danger",
            )
            return redirect(next_url)
        try:
            pdf_bytes = build_motoboy_distrato_pdf(contract, company, document_date)
        except RuntimeError:
            flash(
                "Geração de PDF indisponível: instale o pacote 'reportlab' no ambiente.",
                "danger",
            )
            return redirect(next_url)

        filename = f"distrato_motoboy_{contract.id}.pdf"
        resp = make_response(pdf_bytes)
        resp.headers["Content-Type"] = "application/pdf"
        resp.headers["Content-Disposition"] = f'inline; filename="{filename}"'
        return resp

    @bp.post("/motoboy-contracts/<int:contract_id>/delete")
    @login_required
    def motoboy_contracts_delete(contract_id: int):
        require_admin()
        next_url = resolve_next_url("admin.motoboy_contracts_list")
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        try:
            db.session.delete(contract)
            db.session.commit()
            flash("Contrato de motoboy excluído.", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)

    @bp.post("/motoboy-contracts/bulk-delete")
    @login_required
    def motoboy_contracts_bulk_delete():
        require_admin()
        next_url = resolve_next_url("admin.motoboy_contracts_list")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhum contrato selecionado.", "warning")
            return redirect(next_url)
        try:
            delete_attachment_files_for_contract_ids(ids)
            # Delete related absences first (bulk delete does not trigger ORM cascade)
            ContractAbsence.query.filter(ContractAbsence.contract_id.in_(ids)).delete(
                synchronize_session=False
            )
            count = (
                Contract.query.filter(
                    Contract.id.in_(ids),
                    Contract.contract_type == CONTRACT_TYPE_MOTOBOY,
                ).delete(synchronize_session=False)
            )
            db.session.commit()
            flash(f"{count} contrato(s) excluído(s).", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)
