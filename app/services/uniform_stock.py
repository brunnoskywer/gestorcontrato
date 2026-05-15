"""Regras de movimentação e atualização de saldo de fardamentos."""
from app.extensions import db
from app.models import (
    ENTRY_PAYABLE,
    ENTRY_PURCHASE,
    ENTRY_RETURN,
    EXIT_DISCARD,
    EXIT_LOST,
    EXIT_SHIPMENT,
    MOVEMENT_ENTRY,
    MOVEMENT_EXIT,
    SUPPLIER_MOTOBOY,
    FinancialEntry,
    Supplier,
    Uniform,
    UniformMovement,
)


class UniformStockError(ValueError):
    """Erro de validação de movimentação ou estoque."""


def _validate_payable_entry(entry_id: int | None) -> FinancialEntry | None:
    if entry_id is None:
        return None
    entry = FinancialEntry.query.get(entry_id)
    if not entry:
        raise UniformStockError("Conta a pagar vinculada não encontrada.")
    if entry.entry_type != ENTRY_PAYABLE:
        raise UniformStockError("Somente lançamentos do tipo contas a pagar podem ser vinculados.")
    return entry


def _validate_motoboy(motoboy_id: int | None, required: bool) -> Supplier | None:
    if motoboy_id is None:
        if required:
            raise UniformStockError("Selecione o motoboy.")
        return None
    motoboy = Supplier.query.filter_by(id=motoboy_id, type=SUPPLIER_MOTOBOY).first()
    if not motoboy:
        raise UniformStockError("Motoboy inválido.")
    return motoboy


def create_uniform_movement(
    uniform: Uniform,
    *,
    direction: str,
    subtype: str,
    quantity: int,
    motoboy_id: int | None = None,
    financial_entry_id: int | None = None,
    notes: str | None = None,
) -> UniformMovement:
    """Registra movimentação e atualiza saldo do item."""
    if quantity is None or int(quantity) <= 0:
        raise UniformStockError("Informe uma quantidade maior que zero.")

    quantity = int(quantity)
    notes = (notes or "").strip() or None

    if direction == MOVEMENT_ENTRY:
        if subtype == ENTRY_PURCHASE:
            _validate_payable_entry(financial_entry_id)
            _validate_motoboy(motoboy_id, required=False)
        elif subtype == ENTRY_RETURN:
            if financial_entry_id:
                raise UniformStockError(
                    "Conta a pagar só pode ser vinculada em entradas do tipo Compra."
                )
            _validate_motoboy(motoboy_id, required=True)
        else:
            raise UniformStockError("Tipo de entrada inválido.")
        uniform.quantity = (uniform.quantity or 0) + quantity

    elif direction == MOVEMENT_EXIT:
        if financial_entry_id:
            raise UniformStockError("Conta a pagar não se aplica a saídas de estoque.")
        current = uniform.quantity or 0
        if current < quantity:
            raise UniformStockError(
                f"Estoque insuficiente. Saldo atual: {current}, solicitado: {quantity}."
            )
        if subtype == EXIT_SHIPMENT:
            _validate_motoboy(motoboy_id, required=True)
        elif subtype in (EXIT_DISCARD, EXIT_LOST):
            _validate_motoboy(motoboy_id, required=False)
        else:
            raise UniformStockError("Tipo de saída inválido.")
        uniform.quantity = current - quantity

    else:
        raise UniformStockError("Direção da movimentação inválida.")

    movement = UniformMovement(
        direction=direction,
        subtype=subtype,
        quantity=quantity,
        motoboy_id=motoboy_id,
        financial_entry_id=financial_entry_id if direction == MOVEMENT_ENTRY else None,
        notes=notes,
    )
    movement.uniform = uniform
    db.session.add(movement)
    return movement
