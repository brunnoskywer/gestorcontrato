"""
Blueprint admin: rotas de gestão (empresas, clientes, motoboys, contratos, usuários).

As rotas são divididas por entidade em módulos separados; cada um registra
suas rotas no mesmo blueprint via register_routes(bp).
"""
from flask import Blueprint

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

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")

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
