"""Jinja2 filters for the application."""


def jinja_finalize(value):
    """Converte None em string vazia na impressão (evita 'None' em inputs e textos)."""
    if value is None:
        return ""
    return value


def format_currency(value):
    """Format a number as Brazilian currency: thousands with dot, decimal with comma (e.g. 1.234,56)."""
    if value is None:
        return ""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return ""
    # Format with 2 decimal places, comma as decimal separator, dot as thousands separator
    parts = f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return parts
