"""Rotas de fardamentos: cadastro, estoque e movimentações."""
from collections import defaultdict

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.admin.auth_helpers import handle_delete_constraint_error, require_admin, resolve_next_url
from app.admin.list_pagination import ADMIN_LIST_PER_PAGE, SlicePagination, admin_list_page
from app.extensions import db
from app.filters import format_currency
from app.models import (
    ENTRY_PAYABLE,
    ENTRY_SUBTYPE_LABELS,
    EXIT_SUBTYPE_LABELS,
    MOVEMENT_ENTRY,
    MOVEMENT_EXIT,
    MOVEMENT_SUBTYPE_LABELS,
    UNIFORM_SIZES,
    FinancialEntry,
    Supplier,
    Uniform,
    UniformMovement,
)
from app.search_text import folded_icontains
from app.services.uniform_motoboy_balance import motoboy_uniform_balance_rows
from app.services.uniform_stock import (
    UniformStockError,
    create_uniform_movement,
    delete_uniform_movement,
)


def _payable_entry_search_label(entry: FinancialEntry) -> str:
    supplier = entry.supplier.name if entry.supplier else "Sem fornecedor"
    due = entry.due_date.strftime("%d/%m/%Y") if entry.due_date else "—"
    return (
        f"#{entry.id} — {supplier} — R$ {format_currency(entry.amount)} — venc. {due}"
    )


def _stock_matrix():
    """Linhas por nome de fardamento; colunas por tamanho."""
    rows_map: dict[str, dict[str, int]] = defaultdict(lambda: {s: 0 for s in UNIFORM_SIZES})
    totals_by_size = {s: 0 for s in UNIFORM_SIZES}
    grand_total = 0

    items = (
        Uniform.query.filter_by(is_active=True)
        .order_by(Uniform.name, Uniform.size)
        .all()
    )
    for u in items:
        qty = u.quantity or 0
        rows_map[u.name][u.size] = qty
        totals_by_size[u.size] += qty
        grand_total += qty

    stock_rows = [
        {"name": name, "sizes": sizes, "row_total": sum(sizes.values())}
        for name, sizes in sorted(rows_map.items())
    ]
    return stock_rows, totals_by_size, grand_total


def register_routes(bp: Blueprint) -> None:
    @bp.route("/fardamentos/estoque")
    @login_required
    def uniforms_stock_list():
        require_admin()
        name = request.args.get("name", "").strip()
        stock_rows, totals_by_size, grand_total = _stock_matrix()

        if name:
            stock_rows = [
                r for r in stock_rows if name.upper() in r["name"].upper()
            ]

        return render_template(
            "admin/uniforms/stock.html",
            stock_rows=stock_rows,
            totals_by_size=totals_by_size,
            grand_total=grand_total,
            sizes=UNIFORM_SIZES,
            filters={"name": name},
        )

    @bp.route("/fardamentos/motoboys")
    @login_required
    def uniforms_motoboy_balance_list():
        require_admin()
        motoboy_name = request.args.get("motoboy_name", "").strip()
        all_rows = motoboy_uniform_balance_rows(motoboy_name=motoboy_name)
        grand_total = sum(r["total"] for r in all_rows)
        pagination = SlicePagination(all_rows, admin_list_page(), ADMIN_LIST_PER_PAGE)
        return render_template(
            "admin/uniforms/motoboys_balance.html",
            motoboy_rows=pagination.items,
            pagination=pagination,
            grand_total=grand_total,
            filters={"motoboy_name": motoboy_name},
        )

    @bp.route("/fardamentos")
    @login_required
    def uniforms_list():
        require_admin()
        name = request.args.get("name", "").strip()
        size = request.args.get("size", "").strip()

        query = Uniform.query
        if name:
            query = query.filter(folded_icontains(Uniform.name, name))
        if size and size in UNIFORM_SIZES:
            query = query.filter(Uniform.size == size)

        pagination = query.order_by(Uniform.name, Uniform.size).paginate(
            page=admin_list_page(), per_page=ADMIN_LIST_PER_PAGE, error_out=False
        )
        return render_template(
            "admin/uniforms/list.html",
            uniforms=pagination.items,
            pagination=pagination,
            sizes=UNIFORM_SIZES,
            filters={"name": name, "size": size},
        )

    @bp.route("/fardamentos/form")
    @login_required
    def uniforms_form_new():
        require_admin()
        return render_template(
            "admin/uniforms/_form_fragment.html",
            uniform=None,
            sizes=UNIFORM_SIZES,
            action_url=url_for("admin.uniforms_create"),
        )

    @bp.route("/fardamentos/<int:uniform_id>/form")
    @login_required
    def uniforms_form_edit(uniform_id: int):
        require_admin()
        uniform = Uniform.query.get_or_404(uniform_id)
        return render_template(
            "admin/uniforms/_form_fragment.html",
            uniform=uniform,
            sizes=UNIFORM_SIZES,
            action_url=url_for("admin.uniforms_edit", uniform_id=uniform_id),
        )

    @bp.route("/fardamentos/create", methods=["POST"])
    @login_required
    def uniforms_create():
        require_admin()
        name = request.form.get("name", "").strip()
        size = request.form.get("size", "").strip()
        is_active = request.form.get("is_active") == "on"

        if not name:
            flash("Descrição do fardamento é obrigatória.", "danger")
            return redirect(resolve_next_url("admin.uniforms_list"))
        if size not in UNIFORM_SIZES:
            flash("Selecione um tamanho válido.", "danger")
            return redirect(resolve_next_url("admin.uniforms_list"))

        uniform = Uniform(name=name, size=size, is_active=is_active, quantity=0)
        db.session.add(uniform)
        try:
            db.session.commit()
            flash("Fardamento cadastrado com sucesso.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Já existe cadastro para esta descrição e tamanho.", "danger")
        return redirect(resolve_next_url("admin.uniforms_list"))

    @bp.route("/fardamentos/<int:uniform_id>/edit", methods=["POST"])
    @login_required
    def uniforms_edit(uniform_id: int):
        require_admin()
        uniform = Uniform.query.get_or_404(uniform_id)
        name = request.form.get("name", "").strip()
        size = request.form.get("size", "").strip()
        is_active = request.form.get("is_active") == "on"

        if not name:
            flash("Descrição do fardamento é obrigatória.", "danger")
            return redirect(resolve_next_url("admin.uniforms_list"))
        if size not in UNIFORM_SIZES:
            flash("Selecione um tamanho válido.", "danger")
            return redirect(resolve_next_url("admin.uniforms_list"))

        uniform.name = name
        uniform.size = size
        uniform.is_active = is_active
        try:
            db.session.commit()
            flash("Fardamento atualizado com sucesso.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Já existe cadastro para esta descrição e tamanho.", "danger")
        return redirect(resolve_next_url("admin.uniforms_list"))

    @bp.post("/fardamentos/<int:uniform_id>/delete")
    @login_required
    def uniforms_delete(uniform_id: int):
        require_admin()
        next_url = resolve_next_url("admin.uniforms_list")
        uniform = Uniform.query.get_or_404(uniform_id)
        if (uniform.quantity or 0) > 0:
            flash("Não é possível excluir item com saldo em estoque.", "warning")
            return redirect(next_url)
        if uniform.movements.count() > 0:
            flash("Não é possível excluir item com movimentações registradas.", "warning")
            return redirect(next_url)
        try:
            db.session.delete(uniform)
            db.session.commit()
            flash("Fardamento excluído.", "info")
        except IntegrityError:
            handle_delete_constraint_error()
        return redirect(next_url)

    @bp.post("/fardamentos/bulk-delete")
    @login_required
    def uniforms_bulk_delete():
        require_admin()
        next_url = resolve_next_url("admin.uniforms_list")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhum item selecionado.", "warning")
            return redirect(next_url)
        deleted = 0
        for uniform in Uniform.query.filter(Uniform.id.in_(ids)).all():
            if (uniform.quantity or 0) > 0 or uniform.movements.count() > 0:
                continue
            db.session.delete(uniform)
            deleted += 1
        db.session.commit()
        flash(f"{deleted} fardamento(s) excluído(s).", "info")
        return redirect(next_url)

    @bp.route("/fardamentos/movimentacoes")
    @login_required
    def uniform_movements_list():
        require_admin()
        uniform_id = request.args.get("uniform_id", type=int)
        direction = request.args.get("direction", "").strip()
        subtype = request.args.get("subtype", "").strip()

        query = UniformMovement.query.join(Uniform)
        if uniform_id:
            query = query.filter(UniformMovement.uniform_id == uniform_id)
        if direction in (MOVEMENT_ENTRY, MOVEMENT_EXIT):
            query = query.filter(UniformMovement.direction == direction)
        if subtype:
            query = query.filter(UniformMovement.subtype == subtype)

        pagination = query.order_by(UniformMovement.created_at.desc()).paginate(
            page=admin_list_page(), per_page=ADMIN_LIST_PER_PAGE, error_out=False
        )
        uniforms_for_filter = (
            Uniform.query.filter_by(is_active=True)
            .order_by(Uniform.name, Uniform.size)
            .all()
        )
        subtype_choices = sorted(MOVEMENT_SUBTYPE_LABELS.items(), key=lambda x: x[1])
        return render_template(
            "admin/uniforms/movements_list.html",
            movements=pagination.items,
            pagination=pagination,
            uniforms_for_filter=uniforms_for_filter,
            subtype_choices=subtype_choices,
            filters={
                "uniform_id": uniform_id or "",
                "direction": direction,
                "subtype": subtype,
            },
        )

    @bp.route("/fardamentos/movimentacoes/form")
    @login_required
    def uniform_movements_form_new():
        require_admin()
        uniforms = (
            Uniform.query.filter_by(is_active=True)
            .order_by(Uniform.name, Uniform.size)
            .all()
        )
        return render_template(
            "admin/uniforms/_movement_form_fragment.html",
            uniforms=uniforms,
            action_url=url_for("admin.uniform_movements_create"),
            entry_subtypes=ENTRY_SUBTYPE_LABELS,
            exit_subtypes=EXIT_SUBTYPE_LABELS,
        )

    @bp.route("/fardamentos/movimentacoes/create", methods=["POST"])
    @login_required
    def uniform_movements_create():
        require_admin()
        uniform_id = request.form.get("uniform_id", type=int)
        direction = request.form.get("direction", "").strip()
        subtype = request.form.get("subtype", "").strip()
        quantity = request.form.get("quantity", type=int)
        motoboy_id = request.form.get("motoboy_id", type=int) or None
        financial_entry_id = request.form.get("financial_entry_id", type=int) or None
        notes = request.form.get("notes", "").strip()

        uniform = Uniform.query.get(uniform_id) if uniform_id else None
        if not uniform:
            flash("Selecione o fardamento.", "danger")
            return redirect(resolve_next_url("admin.uniform_movements_list"))

        try:
            create_uniform_movement(
                uniform,
                direction=direction,
                subtype=subtype,
                quantity=quantity or 0,
                motoboy_id=motoboy_id,
                financial_entry_id=financial_entry_id,
                notes=notes,
            )
            db.session.commit()
            flash("Movimentação registrada com sucesso.", "success")
        except UniformStockError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        except Exception:
            db.session.rollback()
            flash("Erro ao registrar movimentação.", "danger")

        return redirect(resolve_next_url("admin.uniform_movements_list"))

    @bp.post("/fardamentos/movimentacoes/bulk-delete")
    @login_required
    def uniform_movements_bulk_delete():
        require_admin()
        next_url = resolve_next_url("admin.uniform_movements_list")
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("Nenhuma movimentação selecionada.", "warning")
            return redirect(next_url)

        deleted = 0
        errors: list[str] = []
        for movement in (
            UniformMovement.query.filter(UniformMovement.id.in_(ids))
            .order_by(UniformMovement.id)
            .all()
        ):
            try:
                delete_uniform_movement(movement)
                deleted += 1
            except UniformStockError as exc:
                errors.append(f"#{movement.id}: {exc}")

        if deleted:
            db.session.commit()
        else:
            db.session.rollback()

        if deleted:
            flash(f"{deleted} movimentação(ões) excluída(s).", "info")
        if errors:
            flash(" ".join(errors[:3]) + (" …" if len(errors) > 3 else ""), "danger")

        return redirect(next_url)

    @bp.get("/fardamentos/payables-search")
    @login_required
    def payables_search():
        """Busca contas a pagar para vincular à entrada por compra."""
        require_admin()
        term = request.args.get("q", "").strip()
        if len(term) < 3:
            return jsonify([])

        query = (
            FinancialEntry.query.options(joinedload(FinancialEntry.supplier))
            .filter_by(entry_type=ENTRY_PAYABLE)
        )
        if term.isdigit():
            query = query.filter(FinancialEntry.id == int(term))
        else:
            query = query.outerjoin(Supplier, FinancialEntry.supplier_id == Supplier.id).filter(
                or_(
                    folded_icontains(FinancialEntry.description, term),
                    folded_icontains(FinancialEntry.reference, term),
                    folded_icontains(Supplier.name, term),
                )
            )

        entries = query.order_by(FinancialEntry.due_date.desc(), FinancialEntry.id.desc()).limit(20).all()
        return jsonify(
            [
                {
                    "id": e.id,
                    "label": _payable_entry_search_label(e),
                    "secondary": e.description[:80] if e.description else "",
                }
                for e in entries
            ]
        )

    @bp.get("/fardamentos/uniforms-search")
    @login_required
    def uniforms_search():
        require_admin()
        q = request.args.get("q", "").strip()
        if len(q) < 1:
            return jsonify([])
        query = Uniform.query.filter_by(is_active=True)
        if q:
            query = query.filter(folded_icontains(Uniform.name, q))
        items = query.order_by(Uniform.name, Uniform.size).limit(20).all()
        return jsonify(
            [
                {
                    "id": u.id,
                    "label": u.display_label,
                    "secondary": f"Estoque: {u.quantity or 0}",
                }
                for u in items
            ]
        )
