"""
Blueprint admin: rotas de gestão (empresas, clientes, motoboys, contratos, usuários).

As rotas são divididas por entidade em módulos separados; cada um registra
suas rotas no mesmo blueprint via register_routes(bp).
"""
from flask import Blueprint, abort, request
from flask_login import current_user

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

_SUPERVISOR_ALLOWED_ENDPOINTS = frozenset(
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
        "admin.requests_clients_search",
    }
)


@admin_bp.before_request
def _restrict_supervisor_to_requests():
    if not current_user.is_authenticated:
        return None
    if current_user.is_admin:
        return None
    if getattr(current_user, "role", None) != "supervisor":
        return None
    endpoint = request.endpoint or ""
    if endpoint not in _SUPERVISOR_ALLOWED_ENDPOINTS:
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
