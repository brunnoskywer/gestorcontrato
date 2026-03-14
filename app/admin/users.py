"""Rotas de CRUD para Usuários (admin)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.admin.auth_helpers import require_admin
from app.extensions import db
from app.models import User


def register_routes(bp: Blueprint) -> None:
    @bp.route("/users/form")
    @login_required
    def users_form_new():
        require_admin()
        return render_template(
            "admin/users/_form_fragment.html",
            user=None,
            action_url=url_for("admin.users_create"),
        )

    @bp.route("/users/<int:user_id>/form")
    @login_required
    def users_form_edit(user_id: int):
        require_admin()
        user = User.query.get_or_404(user_id)
        return render_template(
            "admin/users/_form_fragment.html",
            user=user,
            action_url=url_for("admin.users_edit", user_id=user_id),
        )

    @bp.route("/users")
    @login_required
    def users_list():
        require_admin()
        email = request.args.get("email", "").strip().lower()
        name = request.args.get("name", "").strip()

        query = User.query
        if email:
            query = query.filter(User.email.ilike(f"%{email}%"))
        if name:
            query = query.filter(User.name.ilike(f"%{name}%"))

        users = query.order_by(User.email).all()
        return render_template(
            "admin/users/list.html",
            users=users,
            filters={"email": email, "name": name},
        )

    @bp.route("/users/create", methods=["GET", "POST"])
    @login_required
    def users_create():
        require_admin()
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            name = request.form.get("name", "").strip()
            password = request.form.get("password", "")
            is_admin = bool(request.form.get("is_admin"))

            if not email or not password or not name:
                flash("Nome, e-mail e senha são obrigatórios.", "danger")
            else:
                user = User.query.filter_by(email=email).first()
                if user:
                    flash("Já existe um usuário com este e-mail.", "danger")
                else:
                    user = User(email=email, name=name, is_admin=is_admin)
                    user.set_password(password)
                    db.session.add(user)
                    db.session.commit()
                    flash("Usuário criado com sucesso.", "success")
                    return redirect(url_for("admin.users_list"))

        return render_template("admin/users/form.html", user=None)

    @bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
    @login_required
    def users_edit(user_id: int):
        require_admin()
        user = User.query.get_or_404(user_id)

        if request.method == "POST":
            user.email = request.form.get("email", "").strip().lower()
            user.name = request.form.get("name", "").strip()
            is_admin = bool(request.form.get("is_admin"))
            is_active = bool(request.form.get("is_active"))
            password = request.form.get("password", "")

            user.is_admin = is_admin
            user.is_active = is_active
            if password:
                user.set_password(password)

            if not user.email or not user.name:
                flash("Name and email are required.", "danger")
            else:
                db.session.commit()
                flash("Usuário atualizado com sucesso.", "success")
                return redirect(url_for("admin.users_list"))

        return render_template("admin/users/form.html", user=user)

    @bp.post("/users/<int:user_id>/delete")
    @login_required
    def users_delete(user_id: int):
        require_admin()
        if current_user.id == user_id:
            flash("Você não pode excluir a si mesmo.", "danger")
            return redirect(url_for("admin.users_list"))

        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        flash("Usuário excluído.", "info")
        return redirect(url_for("admin.users_list"))

    @bp.post("/users/bulk-delete")
    @login_required
    def users_bulk_delete():
        require_admin()
        ids = request.form.getlist("ids", type=int)
        if not ids:
            flash("No user selected.", "warning")
            return redirect(url_for("admin.users_list"))
        ids_to_delete = [i for i in ids if i != current_user.id]
        if current_user.id in ids:
            flash("Você não pode excluir a si mesmo.", "warning")
        count = 0
        if ids_to_delete:
            count = User.query.filter(User.id.in_(ids_to_delete)).delete(synchronize_session=False)
            db.session.commit()
        if count:
            flash(f"{count} usuário(s) excluído(s).", "info")
        return redirect(url_for("admin.users_list"))
