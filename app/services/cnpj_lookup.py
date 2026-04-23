"""Consulta CNPJ em provedor externo com tolerância a falhas."""
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _digits_only(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _to_dict(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    return {}


def _first_phone(payload: dict[str, Any]) -> str:
    phones = payload.get("telefones")
    if not isinstance(phones, list) or not phones:
        return ""
    first = phones[0]
    if not isinstance(first, dict):
        return ""
    ddd = (first.get("ddd") or "").strip()
    number = (first.get("numero") or "").strip()
    return f"{ddd}{number}".strip()


def _compose_street(payload: dict[str, Any]) -> str:
    logradouro = (payload.get("logradouro") or "").strip()
    numero = (payload.get("numero") or "").strip()
    if logradouro and numero and numero != "S/N":
        return f"{logradouro} {numero}".strip()
    return logradouro or ""


def lookup_cnpj(
    cnpj_raw: str,
    *,
    api_url: str,
    timeout_seconds: float = 6.0,
) -> tuple[bool, str, dict[str, str]]:
    cnpj = _digits_only(cnpj_raw)
    if len(cnpj) != 14:
        return False, "CNPJ inválido. Informe 14 dígitos.", {}
    if not api_url:
        return False, "Consulta de CNPJ indisponível.", {}

    url = f"{api_url.rstrip('/')}/{cnpj}?datasets=receita"
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "gestor-contrato/1.0"})

    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as err:
        if err.code == 404:
            return False, "CNPJ não encontrado.", {}
        if err.code == 429:
            return False, "Limite de consultas excedido. Tente novamente em instantes.", {}
        return False, "Falha ao consultar CNPJ no momento.", {}
    except (URLError, TimeoutError, ValueError):
        return False, "Falha ao consultar CNPJ no momento.", {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return False, "Resposta inválida do serviço de CNPJ.", {}

    data = _to_dict(parsed)
    if not data:
        return False, "CNPJ não encontrado.", {}

    normalized = {
        "cnpj": cnpj,
        "legal_name": (data.get("razao_social") or "").strip(),
        "trade_name": (data.get("nome_fantasia") or "").strip(),
        "email": (data.get("email") or "").strip(),
        "cep": _digits_only(data.get("cep")),
        "street": _compose_street(data),
        "neighborhood": (data.get("bairro") or "").strip(),
        "city": (data.get("municipio") or "").strip(),
        "state": (data.get("uf") or "").strip().upper(),
        "complement": (data.get("complemento") or "").strip(),
        "phone": _first_phone(data),
    }
    return True, "CNPJ localizado com sucesso.", normalized
