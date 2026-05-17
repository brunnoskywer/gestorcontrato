"""Helpers compartilhados para as rotas do admin (ex.: exigir usuário admin)."""
from flask import abort, flash, request, url_for
from flask_login import current_user

from app.extensions import db

ROLE_SOLICITANTE = "solicitante"
ROLE_MEMBRO = "membro"
ROLE_SUPERVISOR_LEGACY = "supervisor"


def normalized_role(user=None) -> str | None:
    """Normaliza role legado supervisor → solicitante."""
    u = user or current_user
    if not u or not getattr(u, "is_authenticated", False):
        return None
    role = getattr(u, "role", None)
    if role == ROLE_SUPERVISOR_LEGACY:
        return ROLE_SOLICITANTE
    return role


def is_solicitante() -> bool:
    return bool(
        current_user.is_authenticated
        and not current_user.is_admin
        and normalized_role() == ROLE_SOLICITANTE
    )


def is_membro() -> bool:
    return bool(
        current_user.is_authenticated
        and not current_user.is_admin
        and normalized_role() == ROLE_MEMBRO
    )


def is_request_staff() -> bool:
    """Administrador ou membro — resolve/rejeita solicitações e vê o sino."""
    return bool(current_user.is_authenticated and (current_user.is_admin or is_membro()))


def is_supervisor() -> bool:
    """Alias legado: perfil solicitante."""
    return is_solicitante()


def require_admin() -> None:
    """Aborta com 403 se o usuário não estiver autenticado ou não for admin."""
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


def require_staff() -> None:
    """Administrador ou membro."""
    if not current_user.is_authenticated:
        abort(403)
    if not is_request_staff():
        abort(403)


def require_request_module_access() -> None:
    """Solicitante, membro ou administrador."""
    if not current_user.is_authenticated:
        abort(403)
    if current_user.is_admin or is_membro() or is_solicitante():
        return
    abort(403)


def require_solicitante_or_admin() -> None:
    """Solicitante ou administrador (criação/edição de solicitações)."""
    if not current_user.is_authenticated:
        abort(403)
    if current_user.is_admin or is_solicitante():
        return
    abort(403)


def require_supervisor_or_admin() -> None:
    """Alias legado."""
    require_request_module_access()


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
