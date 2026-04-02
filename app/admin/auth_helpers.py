"""Helpers compartilhados para as rotas do admin (ex.: exigir usuário admin)."""
from flask import abort, flash, request, url_for
from flask_login import current_user

from app.extensions import db


def require_admin() -> None:
    """Aborta com 403 se o usuário não estiver autenticado ou não for admin."""
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


def require_supervisor_or_admin() -> None:
    """Permite apenas usuários admin ou supervisor."""
    if not current_user.is_authenticated:
        abort(403)
    if not (current_user.is_admin or getattr(current_user, "role", None) == "supervisor"):
        abort(403)


def is_supervisor() -> bool:
    return bool(current_user.is_authenticated and getattr(current_user, "role", None) == "supervisor" and not current_user.is_admin)


def is_motoboy_user() -> bool:
    return bool(current_user.is_authenticated and getattr(current_user, "role", None) == "motoboy" and not current_user.is_admin)


def handle_delete_constraint_error() -> None:
    """Faz rollback e exibe mensagem quando exclusão falha por restrição de chave (dependência)."""
    db.session.rollback()
    flash(
        "Não é possível excluir: existe(m) registro(s) dependente(s) vinculado(s).",
        "error",
    )


def resolve_next_url(default_endpoint: str) -> str:
    """Resolve URL de retorno seguro (aba atual), com fallback para endpoint padrão."""
    next_url = request.form.get("next") or request.args.get("next")
    if next_url and isinstance(next_url, str) and next_url.startswith("/"):
        return next_url
    return url_for(default_endpoint)
