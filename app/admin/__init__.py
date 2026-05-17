"""
Blueprint admin: rotas de gestão (empresas, clientes, motoboys, contratos, usuários).

As rotas são divididas por entidade em módulos separados; cada um registra
suas rotas no mesmo blueprint via register_routes(bp).
"""
from flask import Blueprint, abort, request
from flask_login import current_user

from .auth_helpers import ROLE_MEMBRO, ROLE_SOLICITANTE, ROLE_SUPERVISOR_LEGACY, normalized_role
from .companies import register_routes as register_companies
from .clients import register_routes as register_clients
from .motoboys import register_routes as register_motoboys
from .accounts import register_routes as register_accounts
from .motoboy_contracts import register_routes as register_motoboy_contracts
from .client_contracts import register_routes as register_client_contracts
from .finance import register_routes as register_finance
from .financial_natures import register_routes as register_financial_natures
from .suppliers import register_routes as register_suppliers
from .users import register_routes as register_users
from .cep_lookup import register_routes as register_cep_lookup
from .uniforms import register_routes as register_uniforms
from .requests import register_routes as register_requests

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")

_SOLICITANTE_ALLOWED_ENDPOINTS = frozenset(
    {
        "admin.requests_list",
        "admin.requests_form_new",
        "admin.requests_form_edit",
        "admin.requests_create",
        "admin.requests_edit",
        "admin.requests_delete",
        "admin.requests_bulk_delete",
        "admin.requests_locations_api",
        "admin.requests_motoboy_contracts_api",
        "admin.requests_motoboy_contract_api",
        "admin.requests_diarist_motoboys_api",
        "admin.requests_clients_search",
        "admin.requests_pending_count_api",
    }
)

_MEMBRO_ALLOWED_ENDPOINTS = frozenset(
    {
        "admin.requests_list",
        "admin.requests_resolve_form",
        "admin.requests_resolve",
        "admin.requests_reject_form",
        "admin.requests_reject",
        "admin.requests_pending_count_api",
    }
)


@admin_bp.before_request
def _restrict_role_to_allowed_endpoints():
    if not current_user.is_authenticated:
        return None
    if current_user.is_admin:
        return None
    role = normalized_role()
    endpoint = request.endpoint or ""
    if role in (ROLE_SOLICITANTE, ROLE_SUPERVISOR_LEGACY):
        if endpoint not in _SOLICITANTE_ALLOWED_ENDPOINTS:
            abort(403)
    elif role == ROLE_MEMBRO:
        if endpoint not in _MEMBRO_ALLOWED_ENDPOINTS:
            abort(403)
    return None


register_companies(admin_bp)
register_clients(admin_bp)
register_motoboys(admin_bp)
register_accounts(admin_bp)
register_motoboy_contracts(admin_bp)
register_client_contracts(admin_bp)
register_finance(admin_bp)
register_financial_natures(admin_bp)
register_suppliers(admin_bp)
register_users(admin_bp)
register_cep_lookup(admin_bp)
register_uniforms(admin_bp)
register_requests(admin_bp)
