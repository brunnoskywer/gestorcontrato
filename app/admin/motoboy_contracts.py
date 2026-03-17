"""CRUD for Motoboy contracts: uses Contract with contract_type=motoboy."""
import calendar
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.admin.auth_helpers import require_admin, handle_delete_constraint_error, require_supervisor_or_admin, is_supervisor
from app.extensions import db
from app.models import Contract, ContractAbsence, CONTRACT_TYPE_MOTOBOY, Supplier, SUPPLIER_CLIENT, SUPPLIER_MOTOBOY
from app.utils import parse_decimal_form
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased


def register_routes(bp: Blueprint) -> None:
    @bp.route("/motoboy-contracts/form")
    @login_required
    def motoboy_contracts_form_new():
        require_admin()
        motoboys = Supplier.query.filter_by(type=SUPPLIER_MOTOBOY).order_by(Supplier.name).all()
        clients = Supplier.query.filter_by(type=SUPPLIER_CLIENT).order_by(Supplier.legal_name, Supplier.name).all()
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
        motoboys = Supplier.query.filter_by(type=SUPPLIER_MOTOBOY).order_by(Supplier.name).all()
        clients = Supplier.query.filter_by(type=SUPPLIER_CLIENT).order_by(Supplier.legal_name, Supplier.name).all()
        return render_template(
            "admin/motoboy_contracts/_form_fragment.html",
            contract=contract,
            motoboys=motoboys,
            clients=clients,
            action_url=url_for("admin.motoboy_contracts_edit", contract_id=contract_id),
        )

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
                )
            )
        contracts = query.order_by(Contract.start_date.desc()).all()

        return render_template(
            "admin/motoboy_contracts/list.html",
            contracts=contracts,
            filters={"motoboy_name": motoboy_name, "client_name": client_name},
        )

    @bp.route("/motoboy-contracts/create", methods=["GET", "POST"])
    @login_required
    def motoboy_contracts_create():
        require_admin()
        motoboys = Supplier.query.filter_by(type=SUPPLIER_MOTOBOY).order_by(Supplier.name).all()
        clients = Supplier.query.filter_by(type=SUPPLIER_CLIENT).order_by(Supplier.legal_name, Supplier.name).all()

        if request.method == "POST":
            motoboy_id = request.form.get("motoboy_id")
            client_id = request.form.get("client_id") or None
            start_date_str = request.form.get("start_date", "")
            end_date_str = request.form.get("end_date", "")
            location = request.form.get("location", "").strip()
            service_value = parse_decimal_form(request.form.get("service_value"))
            bonus_value = parse_decimal_form(request.form.get("bonus_value"))
            missing_value = parse_decimal_form(request.form.get("missing_value"))
            advance_value = parse_decimal_form(request.form.get("advance_value"))

            if not motoboy_id or not start_date_str:
                flash("Motoboy e data de início são obrigatórios.", "danger")
            else:
                start_date_val = date.fromisoformat(start_date_str)
                end_date_val = date.fromisoformat(end_date_str) if end_date_str else None
                contract = Contract(
                    supplier_id=int(motoboy_id),
                    contract_type=CONTRACT_TYPE_MOTOBOY,
                    other_supplier_id=int(client_id) if client_id else None,
                    start_date=start_date_val,
                    end_date=end_date_val,
                    location=location or None,
                    service_value=service_value,
                    bonus_value=bonus_value,
                    missing_value=missing_value,
                    advance_value=advance_value,
                )
                db.session.add(contract)
                db.session.commit()
                flash("Contrato de motoboy criado com sucesso.", "success")
                return redirect(url_for("admin.motoboy_contracts_list"))

        return render_template(
            "admin/motoboy_contracts/form.html",
            contract=None,
            motoboys=motoboys,
            clients=clients,
        )

    @bp.route("/motoboy-contracts/<int:contract_id>/edit", methods=["GET", "POST"])
    @login_required
    def motoboy_contracts_edit(contract_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        motoboys = Supplier.query.filter_by(type=SUPPLIER_MOTOBOY).order_by(Supplier.name).all()
        clients = Supplier.query.filter_by(type=SUPPLIER_CLIENT).order_by(Supplier.legal_name, Supplier.name).all()

        if request.method == "POST":
            contract.supplier_id = int(request.form.get("motoboy_id"))
            contract.other_supplier_id = int(request.form.get("client_id")) if request.form.get("client_id") else None
            start_date_str = request.form.get("start_date", "")
            end_date_str = request.form.get("end_date", "")
            contract.location = request.form.get("location", "").strip() or None
            contract.service_value = parse_decimal_form(request.form.get("service_value"))
            contract.bonus_value = parse_decimal_form(request.form.get("bonus_value"))
            contract.missing_value = parse_decimal_form(request.form.get("missing_value"))
            contract.advance_value = parse_decimal_form(request.form.get("advance_value"))

            if not contract.supplier_id or not start_date_str:
                flash("Motoboy e data de início são obrigatórios.", "danger")
            else:
                contract.start_date = date.fromisoformat(start_date_str)
                contract.end_date = date.fromisoformat(end_date_str) if end_date_str else None
                db.session.commit()
                flash("Contrato de motoboy atualizado com sucesso.", "success")
                return redirect(url_for("admin.motoboy_contracts_list"))

        return render_template(
            "admin/motoboy_contracts/form.html",
            contract=contract,
            motoboys=motoboys,
            clients=clients,
        )

    @bp.route("/motoboy-contracts/<int:contract_id>/falta/form")
    @login_required
    def motoboy_contract_falta_form(contract_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        return render_template(
            "admin/motoboy_contracts/_falta_form_fragment.html",
            contract=contract,
            action_url=url_for("admin.motoboy_contract_falta_create", contract_id=contract_id),
            default_date=date.today().isoformat(),
        )

    @bp.route("/motoboy-contracts/<int:contract_id>/falta", methods=["POST"])
    @login_required
    def motoboy_contract_falta_create(contract_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        absence_date_str = request.form.get("absence_date", "").strip()
        justification = request.form.get("justification", "").strip()
        substitute_name = request.form.get("substitute_name", "").strip()
        substitute_document = request.form.get("substitute_document", "").strip()
        substitute_pix = request.form.get("substitute_pix", "").strip()
        amount_val = parse_decimal_form(request.form.get("substitute_amount"))
        if not absence_date_str or not justification:
            flash("Dia e justificativa são obrigatórios.", "danger")
            return redirect(url_for("admin.motoboy_contracts_list"))
        try:
            absence_date = date.fromisoformat(absence_date_str)
        except ValueError:
            flash("Data inválida.", "danger")
            return redirect(url_for("admin.motoboy_contracts_list"))
        existing = ContractAbsence.query.filter_by(
            contract_id=contract_id,
            absence_date=absence_date,
        ).first()
        if existing:
            flash("Já existe uma falta registrada para este contrato nesta data.", "danger")
            return redirect(url_for("admin.motoboy_contracts_list"))
        absence = ContractAbsence(
            contract_id=contract_id,
            absence_date=absence_date,
            justification=justification,
            substitute_name=substitute_name or None,
            substitute_document=substitute_document or None,
            substitute_pix=substitute_pix or None,
            substitute_amount=amount_val,
        )
        db.session.add(absence)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Já existe uma falta registrada para este contrato nesta data.", "danger")
            return redirect(url_for("admin.motoboy_contracts_list"))
        flash("Falta registrada com sucesso.", "success")
        return redirect(url_for("admin.motoboy_contracts_list"))

    @bp.route("/motoboy-contracts/<int:contract_id>/falta/<int:absence_id>/form")
    @login_required
    def motoboy_contract_falta_edit_form(contract_id: int, absence_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        absence = ContractAbsence.query.filter_by(
            id=absence_id, contract_id=contract_id
        ).first_or_404()
        return render_template(
            "admin/motoboy_contracts/_falta_edit_fragment.html",
            contract=contract,
            absence=absence,
            action_url=url_for("admin.motoboy_contract_falta_update", contract_id=contract_id, absence_id=absence_id),
        )

    @bp.route("/motoboy-contracts/<int:contract_id>/falta/<int:absence_id>", methods=["POST"])
    @login_required
    def motoboy_contract_falta_update(contract_id: int, absence_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        absence = ContractAbsence.query.filter_by(
            id=absence_id, contract_id=contract_id
        ).first_or_404()
        absence_date_str = request.form.get("absence_date", "").strip()
        justification = request.form.get("justification", "").strip()
        substitute_name = request.form.get("substitute_name", "").strip()
        substitute_document = request.form.get("substitute_document", "").strip()
        substitute_pix = request.form.get("substitute_pix", "").strip()
        if not absence_date_str or not justification:
            flash("Data e justificativa são obrigatórios.", "danger")
            return redirect(url_for("admin.motoboy_contracts_list"))
        try:
            absence_date = date.fromisoformat(absence_date_str)
        except ValueError:
            flash("Data inválida.", "danger")
            return redirect(url_for("admin.motoboy_contracts_list"))
        other = ContractAbsence.query.filter_by(
            contract_id=contract_id,
            absence_date=absence_date,
        ).filter(ContractAbsence.id != absence_id).first()
        if other:
            flash("Já existe outra falta para este contrato nesta data.", "danger")
            return redirect(url_for("admin.motoboy_contracts_list"))
        absence.absence_date = absence_date
        absence.justification = justification
        absence.substitute_name = substitute_name or None
        absence.substitute_document = substitute_document or None
        absence.substitute_pix = substitute_pix or None
        absence.substitute_amount = parse_decimal_form(request.form.get("substitute_amount"))
        db.session.commit()
        flash("Falta atualizada com sucesso.", "success")
        return redirect(url_for("admin.motoboy_contracts_list"))

    @bp.post("/motoboy-contracts/<int:contract_id>/falta/<int:absence_id>/delete")
    @login_required
    def motoboy_contract_falta_delete(contract_id: int, absence_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        absence = ContractAbsence.query.filter_by(
            id=absence_id, contract_id=contract_id
        ).first_or_404()
        db.session.delete(absence)
        db.session.commit()
        flash("Falta excluída.", "info")
        return redirect(url_for("admin.motoboy_contracts_list"))

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
        weeks_raw = calendar.monthcalendar(year, month)
        # Sunday first: reorder each week to [Sun, Mon, ..., Sat]
        weekdays = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
        weeks = []
        for w in weeks_raw:
            weeks.append([(w[6], w[6] in absence_days if w[6] else False), (w[0], w[0] in absence_days if w[0] else False), (w[1], w[1] in absence_days if w[1] else False), (w[2], w[2] in absence_days if w[2] else False), (w[3], w[3] in absence_days if w[3] else False), (w[4], w[4] in absence_days if w[4] else False), (w[5], w[5] in absence_days if w[5] else False)])
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

    @bp.post("/motoboy-contracts/<int:contract_id>/delete")
    @login_required
    def motoboy_contracts_delete(contract_id: int):
        require_admin()
        contract = Contract.query.filter_by(id=contract_id, contract_type=CONTRACT_TYPE_MOTOBOY).first_or_404()
        try:
            db.session.delete(contract)
            db.session.commit()
            flash("Contrato de motoboy excluído.", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(url_for("admin.motoboy_contracts_list"))

    @bp.post("/motoboy-contracts/bulk-delete")
    @login_required
    def motoboy_contracts_bulk_delete():
        require_admin()
        next_url = request.form.get("next") or request.args.get("next") or url_for("admin.motoboy_contracts_list")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhum contrato selecionado.", "warning")
            return redirect(next_url)
        try:
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
