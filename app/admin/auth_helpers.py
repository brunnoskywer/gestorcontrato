"""Helpers compartilhados para as rotas do admin (ex.: exigir usuário admin)."""
from flask import abort
from flask_login import current_user


def require_admin() -> None:
    """Aborta com 403 se o usuário não estiver autenticado ou não for admin."""
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)
