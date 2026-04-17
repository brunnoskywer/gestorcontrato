"""Jinja2 filters for the application."""

from app.models.supplier import (
    MOTOBOY_STATUS_ACTIVE,
    MOTOBOY_STATUS_PENDING,
    MOTOBOY_TERMINATED_STATUSES,
    SUPPLIER_CLIENT,
    client_display_label,
)


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


def motoboy_status_stripe_class(status: str | None) -> str:
    """Classe CSS da faixa de status (motoboy): ativo, pendente, encerrado."""
    s = (status or MOTOBOY_STATUS_ACTIVE).strip().lower()
    if s in MOTOBOY_TERMINATED_STATUSES:
        return "status-stripe-encerrado"
    if s == MOTOBOY_STATUS_PENDING:
        return "status-stripe-pendente"
    return "status-stripe-ativo"


def motoboy_status_label_pt(status: str | None) -> str:
    s = (status or MOTOBOY_STATUS_ACTIVE).strip().lower()
    if s in MOTOBOY_TERMINATED_STATUSES:
        return "Encerrado"
    if s == MOTOBOY_STATUS_PENDING:
        return "Pendente"
    return "Ativo"


def finance_supplier_display(supplier) -> str:
    """Célula de fornecedor na lista financeira: cliente por fantasia; demais por nome."""
    if supplier is None:
        return "-"
    if getattr(supplier, "type", None) == SUPPLIER_CLIENT:
        return client_display_label(supplier)
    return (supplier.name or "-").strip() or "-"


def finance_entry_stripe_class(entry) -> str:
    """Faixa na lista financeira: quitado (azul) ou pendente (amarelo)."""
    if entry is None:
        return "status-stripe-pendente"
    if getattr(entry, "settled_at", None):
        return "status-stripe-quitado"
    return "status-stripe-pendente"
