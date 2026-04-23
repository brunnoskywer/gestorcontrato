from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required

from app.admin.auth_helpers import require_admin
from app.services.cnpj_lookup import lookup_cnpj
from app.services.cep_lookup import lookup_cep


def register_routes(bp: Blueprint) -> None:
    @bp.get("/address/cep-lookup")
    @login_required
    def address_cep_lookup():
        require_admin()
        cep = (request.args.get("cep") or "").strip()
        ok, message, data = lookup_cep(
            cep,
            api_url=current_app.config.get("CEP_LOOKUP_URL", ""),
            api_key=current_app.config.get("CEP_LOOKUP_KEY", ""),
            timeout_seconds=float(current_app.config.get("CEP_LOOKUP_TIMEOUT_SECONDS", 6)),
        )
        return jsonify({"ok": ok, "message": message, "data": data})

    @bp.get("/address/cnpj-lookup")
    @login_required
    def address_cnpj_lookup():
        require_admin()
        cnpj = (request.args.get("cnpj") or "").strip()
        ok, message, data = lookup_cnpj(
            cnpj,
            api_url=current_app.config.get("OPENCNPJ_LOOKUP_URL", ""),
            timeout_seconds=float(current_app.config.get("OPENCNPJ_LOOKUP_TIMEOUT_SECONDS", 6)),
        )
        return jsonify({"ok": ok, "message": message, "data": data})
