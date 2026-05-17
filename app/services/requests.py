"""Lógica de solicitações: payload, contratos vigentes e resumos."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from flask import request
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    CONTRACT_TYPE_MOTOBOY,
    Contract,
    Supplier,
    SUPPLIER_MOTOBOY,
)
from app.models.requests import (
    REQUEST_STATUS_PENDING,
    REQUEST_TYPE_ABSENCE,
    REQUEST_TYPE_DISTRATO,
    REQUEST_TYPE_MOTOBOY_INCLUSION,
    REQUEST_TYPE_RELOCATION,
    REQUEST_TYPES,
    REQUEST_TYPE_LABELS,
    Request,
)
from app.models.supplier import client_display_label

DEFAULT_LIST_DAYS = 7


def _parse_date(value: str) -> Optional[date]:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _str_field(name: str) -> str:
    return (request.form.get(name) or "").strip()


def _int_field(name: str) -> Optional[int]:
    raw = (request.form.get(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _bool_checkbox(name: str) -> bool:
    return request.form.get(name) == "1"


def active_motoboy_contracts_query(location: Optional[str] = None):
    q = (
        Contract.query.filter_by(contract_type=CONTRACT_TYPE_MOTOBOY)
        .filter(Contract.end_date.is_(None))
        .options(
            joinedload(Contract.supplier),
            joinedload(Contract.other_supplier),
        )
    )
    loc = (location or "").strip()
    if loc:
        q = q.filter(Contract.location == loc)
    return q.order_by(Contract.location, Contract.id)


def distinct_active_locations() -> list[str]:
    rows = (
        db.session.query(Contract.location)
        .filter(
            Contract.contract_type == CONTRACT_TYPE_MOTOBOY,
            Contract.end_date.is_(None),
            Contract.location.isnot(None),
            Contract.location != "",
        )
        .distinct()
        .order_by(Contract.location)
        .all()
    )
    return [r[0] for r in rows if r[0]]


def contract_option_label(contract: Contract) -> str:
    motoboy = contract.supplier.name if contract.supplier else "—"
    client = (
        client_display_label(contract.other_supplier)
        if contract.other_supplier
        else "—"
    )
    loc = contract.location or "—"
    return f"#{contract.id} — {motoboy} — {client} — {loc}"


def contract_to_api_dict(contract: Contract) -> dict[str, Any]:
    missing = contract.missing_value
    return {
        "id": contract.id,
        "label": contract_option_label(contract),
        "location": contract.location or "",
        "missing_value": float(missing) if missing is not None else None,
        "motoboy_name": contract.supplier.name if contract.supplier else "",
        "client_label": (
            client_display_label(contract.other_supplier)
            if contract.other_supplier
            else ""
        ),
    }


def clients_for_relocation_select():
    return (
        Supplier.query.filter_by(type=SUPPLIER_CLIENT, is_active=True)
        .order_by(func.coalesce(Supplier.trade_name, Supplier.legal_name, Supplier.name))
        .all()
    )


def diarist_motoboys_for_form(contract: Optional[Contract] = None):
    q = Supplier.query.filter_by(
        type=SUPPLIER_MOTOBOY, is_active=True, is_diarist=True
    ).order_by(Supplier.name)
    if contract and contract.supplier:
        uf = (contract.supplier.state or "").strip().upper()
        if uf:
            q = q.filter(func.upper(Supplier.state) == uf)
    return q.all()


def diarist_motoboys_to_api(contract: Contract) -> list[dict[str, Any]]:
    return [
        {
            "id": m.id,
            "label": f"{m.name}{f' — {m.document}' if m.document else ''}",
        }
        for m in diarist_motoboys_for_form(contract)
    ]


def build_payload_from_form(request_type: str) -> dict[str, Any]:
    if request_type == REQUEST_TYPE_MOTOBOY_INCLUSION:
        return {
            "full_name": _str_field("full_name"),
            "cpf": _str_field("cpf"),
            "cnpj": _str_field("cnpj"),
            "cep": _str_field("cep"),
            "city": _str_field("city"),
            "state": _str_field("state"),
            "street": _str_field("street"),
            "neighborhood": _str_field("neighborhood"),
            "address": _str_field("address"),
            "reference_contact": _str_field("reference_contact"),
            "bike_plate": _str_field("bike_plate"),
            "bank_account_pix": _str_field("bank_account_pix"),
            "status": _str_field("status") or "pending",
            "contact_phone": _str_field("contact_phone"),
            "is_diarist": _bool_checkbox("is_diarist"),
            "notes": _str_field("notes"),
        }

    if request_type in (REQUEST_TYPE_DISTRATO, REQUEST_TYPE_RELOCATION, REQUEST_TYPE_ABSENCE):
        contract_id = _int_field("motoboy_contract_id")
        payload: dict[str, Any] = {
            "location": _str_field("location"),
            "motoboy_contract_id": contract_id,
        }
        if contract_id:
            c = Contract.query.get(contract_id)
            if c:
                payload["contract_label"] = contract_option_label(c)

        if request_type == REQUEST_TYPE_DISTRATO:
            end_d = _parse_date(_str_field("end_date"))
            payload["end_date"] = end_d.isoformat() if end_d else ""
            payload["reason"] = _str_field("reason")
        elif request_type == REQUEST_TYPE_RELOCATION:
            client_id = _int_field("new_client_id")
            payload["new_client_id"] = client_id
            payload["new_client_label"] = ""
            if client_id:
                client = Supplier.query.get(client_id)
                if client:
                    payload["new_client_label"] = client_display_label(client)
            payload["reason"] = _str_field("reason")
        elif request_type == REQUEST_TYPE_ABSENCE:
            abs_d = _parse_date(_str_field("absence_date"))
            payload["absence_date"] = abs_d.isoformat() if abs_d else ""
            payload["justification"] = _str_field("justification")
            payload["substitute_supplier_id"] = _int_field("substitute_supplier_id")
            payload["substitute_amount"] = _str_field("substitute_amount")
        return payload

    return {}


def validate_request_type(request_type: str) -> bool:
    return request_type in REQUEST_TYPES


def request_summary(req: Request) -> str:
    p = req.payload or {}
    if req.request_type == REQUEST_TYPE_MOTOBOY_INCLUSION:
        name = (p.get("full_name") or "").strip()
        return name or "Motoboy (sem nome informado)"
    if req.request_type in (REQUEST_TYPE_DISTRATO, REQUEST_TYPE_RELOCATION, REQUEST_TYPE_ABSENCE):
        return (p.get("contract_label") or "").strip() or "Contrato não informado"
    return "—"


def list_date_range_from_request() -> tuple[date, date, bool]:
    """Retorna (date_from, date_to, used_default). Padrão: últimos 7 dias."""
    today = date.today()
    default_from = today - timedelta(days=DEFAULT_LIST_DAYS - 1)
    raw_from = request.args.get("date_from", "").strip()
    raw_to = request.args.get("date_to", "").strip()
    used_default = not raw_from and not raw_to
    date_from = _parse_date(raw_from) if raw_from else default_from
    date_to = _parse_date(raw_to) if raw_to else today
    if date_from is None:
        date_from = default_from
    if date_to is None:
        date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    return date_from, date_to, used_default


def list_filter_datetime_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, datetime.min.time())
    end = datetime.combine(date_to, datetime.max.time())
    return start, end
