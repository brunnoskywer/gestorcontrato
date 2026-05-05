"""Shared utilities."""
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Query
from sqlalchemy.sql.elements import ColumnElement


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


def parse_created_datetime_range(
    date_from_str: str | None,
    date_to_str: str | None,
) -> tuple[datetime | None, datetime | None]:
    """
    Lê datas no formato ISO (input type=date).
    Retorna (início inclusivo 00:00, fim exclusivo) para filtrar DateTime:
      col >= start AND col < end_exclusive
    """
    start: datetime | None = None
    end_exclusive: datetime | None = None
    fs = (date_from_str or "").strip()
    ts = (date_to_str or "").strip()
    if fs:
        try:
            d = date.fromisoformat(fs)
            start = datetime.combine(d, time.min)
        except ValueError:
            pass
    if ts:
        try:
            d = date.fromisoformat(ts)
            end_exclusive = datetime.combine(d + timedelta(days=1), time.min)
        except ValueError:
            pass
    return start, end_exclusive


def apply_created_at_range(
    query: Query,
    column: ColumnElement,
    date_from_str: str | None,
    date_to_str: str | None,
) -> Query:
    start, end_exclusive = parse_created_datetime_range(date_from_str, date_to_str)
    if start is not None:
        query = query.filter(column >= start)
    if end_exclusive is not None:
        query = query.filter(column < end_exclusive)
    return query
