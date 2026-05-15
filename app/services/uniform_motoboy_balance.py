"""Saldo de fardamentos em posse de motoboys (envios − retornos)."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import and_, case, func

from app.extensions import db
from app.models import (
    ENTRY_RETURN,
    EXIT_SHIPMENT,
    MOVEMENT_ENTRY,
    MOVEMENT_EXIT,
    SUPPLIER_MOTOBOY,
    Supplier,
    Uniform,
    UniformMovement,
)
from app.search_text import folded_icontains


def _balance_query():
    """Agrega saldo por motoboy e item (uniform_id)."""
    shipped = case(
        (
            and_(
                UniformMovement.direction == MOVEMENT_EXIT,
                UniformMovement.subtype == EXIT_SHIPMENT,
            ),
            UniformMovement.quantity,
        ),
        else_=0,
    )
    returned = case(
        (
            and_(
                UniformMovement.direction == MOVEMENT_ENTRY,
                UniformMovement.subtype == ENTRY_RETURN,
            ),
            UniformMovement.quantity,
        ),
        else_=0,
    )
    balance = func.sum(shipped) - func.sum(returned)
    return (
        db.session.query(
            UniformMovement.motoboy_id.label("motoboy_id"),
            UniformMovement.uniform_id.label("uniform_id"),
            balance.label("balance"),
        )
        .filter(UniformMovement.motoboy_id.isnot(None))
        .group_by(UniformMovement.motoboy_id, UniformMovement.uniform_id)
        .having(balance > 0)
    )


def motoboy_uniform_balance_rows(*, motoboy_name: str = "") -> list[dict]:
    """
    Retorna lista de motoboys com fardamento em posse.
    Cada item: {motoboy_id, motoboy_name, total, uniform_items: [{uniform_id, label, quantity}]}
    """
    subq = _balance_query().subquery()
    query = (
        db.session.query(
            subq.c.motoboy_id,
            subq.c.uniform_id,
            subq.c.balance,
            Supplier.name.label("motoboy_name"),
            Uniform.name.label("uniform_name"),
            Uniform.size.label("uniform_size"),
        )
        .join(Supplier, Supplier.id == subq.c.motoboy_id)
        .join(Uniform, Uniform.id == subq.c.uniform_id)
        .filter(Supplier.type == SUPPLIER_MOTOBOY)
    )
    if motoboy_name:
        query = query.filter(folded_icontains(Supplier.name, motoboy_name))

    query = query.order_by(Supplier.name, Uniform.name, Uniform.size)

    grouped: dict[int, dict] = {}
    for row in query.all():
        mid = row.motoboy_id
        qty = int(row.balance or 0)
        if qty <= 0:
            continue
        if mid not in grouped:
            grouped[mid] = {
                "motoboy_id": mid,
                "motoboy_name": row.motoboy_name,
                "total": 0,
                "uniform_items": [],
            }
        label = f"{row.uniform_name} — {row.uniform_size}"
        grouped[mid]["uniform_items"].append(
            {
                "uniform_id": row.uniform_id,
                "label": label,
                "quantity": qty,
            }
        )
        grouped[mid]["total"] += qty

    rows = list(grouped.values())
    rows.sort(key=lambda r: r["motoboy_name"])
    return rows
