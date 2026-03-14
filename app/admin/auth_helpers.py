"""Helpers compartilhados para as rotas do admin (ex.: exigir usuário admin)."""
from flask import abort, flash
from flask_login import current_user

from app.extensions import db


def require_admin() -> None:
    """Aborta com 403 se o usuário não estiver autenticado ou não for admin."""
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


def handle_delete_constraint_error() -> None:
    """Faz rollback e exibe mensagem quando exclusão falha por restrição de chave (dependência)."""
    db.session.rollback()
    flash(
        "Não é possível excluir: existe(m) registro(s) dependente(s) vinculado(s).",
        "error",
    )
