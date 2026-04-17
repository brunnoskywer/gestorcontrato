"""Shared utilities."""


def parse_decimal_form(value):
    """
    Parse a decimal from form input. Accepts Brazilian format (1.234,56) or dot decimal (1234.56).
    Returns None if empty/invalid, otherwise the float value.
    """
    if value is None:
        return None
    s = (value if isinstance(value, str) else str(value)).strip()
    if not s:
        return None
    # Brazilian: remove thousands dot, then comma -> dot
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def format_address_line(
    street: str | None,
    neighborhood: str | None,
    city: str | None,
    state: str | None,
    *,
    complement: str | None = None,
) -> str:
    """Monta uma linha de endereço a partir de rua, bairro, cidade e UF."""
    parts: list[str] = []
    s = (street or "").strip()
    if s:
        parts.append(s)
    b = (neighborhood or "").strip()
    if b:
        parts.append(b)
    c = (city or "").strip()
    uf = (state or "").strip().upper()
    if c and uf:
        parts.append(f"{c}/{uf}")
    elif c:
        parts.append(c)
    elif uf:
        parts.append(uf)
    line = " — ".join(parts) if parts else ""
    comp = (complement or "").strip()
    if comp:
        line = f"{line} ({comp})" if line else comp
    return line
