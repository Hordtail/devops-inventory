from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db_models import ItemDB, StockMovementDB


class StockMovementError(Exception):
    """Base exception for stock movement domain errors."""


class InvalidMovementTypeError(StockMovementError):
    """Raised when a movement type is not IN or OUT."""


class InvalidMovementQuantityError(StockMovementError):
    """Raised when a movement quantity is not a positive integer."""


class ItemNotFoundError(StockMovementError):
    """Raised when the requested item does not exist."""


class InactiveItemError(StockMovementError):
    """Raised when stock movement is attempted for an inactive item."""


class InsufficientStockError(StockMovementError):
    """Raised when an outgoing movement exceeds available stock."""


def register_stock_movement(
    db: Session,
    item_id: int,
    movement_type: str,
    quantity: int,
    note: str | None = None,
) -> StockMovementDB:
    """Apply a stock movement atomically and return its persisted record.

    This service owns its transaction. Call it with a session that has no
    transaction already open, and do not query through that session first.
    The row lock serializes movements for the same item on PostgreSQL.
    """
    if movement_type not in {"IN", "OUT"}:
        raise InvalidMovementTypeError("movement_type must be 'IN' or 'OUT'")
    if (
        isinstance(quantity, bool)
        or not isinstance(quantity, int)
        or quantity <= 0
    ):
        raise InvalidMovementQuantityError("quantity must be a positive integer")

    with db.begin():
        item = db.scalar(
            select(ItemDB)
            .where(ItemDB.id == item_id)
            .with_for_update()
        )

        if item is None:
            raise ItemNotFoundError(f"item {item_id} does not exist")
        if not item.active:
            raise InactiveItemError(f"item {item_id} is inactive")

        if movement_type == "OUT" and item.quantity_available < quantity:
            raise InsufficientStockError(
                f"item {item_id} has insufficient available stock"
            )

        if movement_type == "IN":
            item.quantity_available += quantity
        else:
            item.quantity_available -= quantity

        movement = StockMovementDB(
            item_id=item_id,
            movement_type=movement_type,
            quantity=quantity,
            note=note,
        )
        db.add(movement)
        db.flush()

    return movement
