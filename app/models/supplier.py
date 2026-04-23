from datetime import datetime

from app.extensions import db


SUPPLIER_CLIENT = "client"
SUPPLIER_SUPPLIER = "supplier"
SUPPLIER_MOTOBOY = "motoboy"

# Status operacional do motoboy (cadastro). "inactive" é legado → tratar como encerrado.
MOTOBOY_STATUS_ACTIVE = "active"
MOTOBOY_STATUS_PENDING = "pending"
MOTOBOY_STATUS_TERMINATED = "terminated"
MOTOBOY_TERMINATED_STATUSES = frozenset({MOTOBOY_STATUS_TERMINATED, "inactive"})


def motoboy_supplier_operational(supplier: "Supplier") -> bool:
    """Motoboy disponível para contratos, faltas, buscas e processamentos financeiros."""
    if not supplier or supplier.type != SUPPLIER_MOTOBOY:
        return True
    st = (supplier.status or MOTOBOY_STATUS_ACTIVE).strip().lower()
    return st not in MOTOBOY_TERMINATED_STATUSES


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    # Documento (CPF/CNPJ) sem unicidade global por decisão de negócio.
    document = db.Column(db.String(20), nullable=True)
    type = db.Column(db.String(20), nullable=False)  # client | supplier | motoboy
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Client-type fields (nullable)
    legal_name = db.Column(db.String(255), nullable=True)
    trade_name = db.Column(db.String(255), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    cep = db.Column(db.String(9), nullable=True)
    street = db.Column(db.String(255), nullable=True)
    neighborhood = db.Column(db.String(120), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    state = db.Column(db.String(2), nullable=True)
    contact_name = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    billing_company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    # General notes for client
    notes = db.Column(db.Text, nullable=True)

    # Motoboy-type fields (nullable)
    reference_contact = db.Column(db.String(255), nullable=True)
    bike_plate = db.Column(db.String(20), nullable=True)
    bank_account_pix = db.Column(db.String(120), nullable=True)
    document_secondary = db.Column(db.String(20), nullable=True)  # e.g. motoboy CNPJ
    # Motoboy-specific fields
    status = db.Column(db.String(20), nullable=False, default=MOTOBOY_STATUS_ACTIVE)  # active | pending | terminated
    contact_phone = db.Column(db.String(50), nullable=True)
    # Motoboy pode ser marcado como diarista (cobre faltas de titulares em contratos).
    is_diarist = db.Column(db.Boolean, nullable=False, default=False)

    billing_company = db.relationship("Company", back_populates="billing_suppliers", foreign_keys=[billing_company_id])


def client_display_label(supplier: "Supplier | None") -> str:
    """Nome de exibição para cliente: fantasia, senão razão social, senão nome interno."""
    if not supplier:
        return "-"
    if supplier.type == SUPPLIER_CLIENT:
        return (supplier.trade_name or supplier.legal_name or supplier.name or "-").strip() or "-"
    return (supplier.name or "-").strip() or "-"

