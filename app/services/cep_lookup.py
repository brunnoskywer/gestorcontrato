"""Consulta CEP em provedor externo com tolerância a falhas."""
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _digits_only(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _join_street(tipo: str | None, logradouro: str | None) -> str:
    t = (tipo or "").strip()
    l = (logradouro or "").strip()
    return f"{t} {l}".strip() or l or t


def _to_dict(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    return {}


def lookup_cep(
    cep_raw: str,
    *,
    api_url: str,
    api_key: str,
    timeout_seconds: float = 6.0,
) -> tuple[bool, str, dict[str, str]]:
    cep = _digits_only(cep_raw)
    if len(cep) != 8:
        return False, "CEP inválido. Informe 8 dígitos.", {}

    if not api_url or not api_key:
        return False, "Consulta de CEP indisponível.", {}

    query = urlencode(
        {
            "cep": cep,
            "formato": "json",
            "chave": api_key,
            "identificador": "GESTOR_CONTRATO",
        }
    )
    url = f"{api_url.rstrip('/')}/?{query}"
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "gestor-contrato/1.0"})

    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, ValueError):
        return False, "Falha ao consultar CEP no momento.", {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return False, "Resposta inválida do serviço de CEP.", {}

    data = _to_dict(parsed)
    result_code = str(data.get("resultado", "")).strip()
    if result_code != "1":
        msg = (data.get("resultado_txt") or "CEP não encontrado.").strip()
        return False, msg, {}

    normalized = {
        "cep": cep,
        "street": _join_street(data.get("tipo_logradouro"), data.get("logradouro")),
        "neighborhood": (data.get("bairro") or "").strip(),
        "city": (data.get("cidade") or "").strip(),
        "state": (data.get("uf") or "").strip().upper(),
        "complement": (data.get("complemento") or "").strip(),
    }
    return True, "CEP localizado com sucesso.", normalized
