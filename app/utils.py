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
