from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.extensions import db
from app.models import Company

api_v1_bp = Blueprint("api_v1", __name__)


@api_v1_bp.get("/companies")
@login_required
def list_companies():
    companies = Company.query.all()
    data = [
        {
            "id": c.id,
            "legal_name": c.legal_name,
            "trade_name": c.trade_name,
            "cnpj": c.cnpj,
            "partner_name": c.partner_name,
        }
        for c in companies
    ]
    return jsonify(data)


@api_v1_bp.post("/companies")
@login_required
def create_company():
    payload = request.get_json() or {}

    company = Company(
        legal_name=payload.get("legal_name"),
        trade_name=payload.get("trade_name"),
        cnpj=payload.get("cnpj"),
        partner_name=payload.get("partner_name"),
    )
    db.session.add(company)
    db.session.commit()

    return (
        jsonify(
            {
                "id": company.id,
                "legal_name": company.legal_name,
                "trade_name": company.trade_name,
                "cnpj": company.cnpj,
                "partner_name": company.partner_name,
            }
        ),
        201,
    )

