import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.db_models import ItemDB, StockMovementDB
from app.services.stock import (
    InactiveItemError,
    InsufficientStockError,
    InvalidMovementQuantityError,
    InvalidMovementTypeError,
    ItemNotFoundError,
    register_stock_movement,
)


def create_sqlite_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def create_item(session: Session) -> ItemDB:
    item = ItemDB(code="BRK-001", name="Brake pad", unit="pcs")
    session.add(item)
    session.commit()
    return item


def test_stock_movement_persists_with_database_timestamp_default():
    engine = create_sqlite_engine()

    with Session(engine) as session:
        item = create_item(session)
        movement = StockMovementDB(
            item_id=item.id,
            movement_type="IN",
            quantity=5,
        )
        session.add(movement)
        session.commit()
        session.refresh(movement)

        assert movement.id is not None
        assert movement.item_id == item.id
        assert movement.movement_type == "IN"
        assert movement.quantity == 5
        assert movement.occurred_at is not None
        assert movement.note is None

    engine.dispose()


@pytest.mark.parametrize(
    ("movement_type", "quantity"),
    [("ADJ", 1), ("IN", 0), ("OUT", -1)],
)
def test_stock_movement_check_constraints_reject_invalid_values(
    movement_type, quantity
):
    engine = create_sqlite_engine()

    with Session(engine) as session:
        item = create_item(session)
        session.add(
            StockMovementDB(
                item_id=item.id,
                movement_type=movement_type,
                quantity=quantity,
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()

    engine.dispose()


def test_item_with_stock_movements_cannot_be_physically_deleted():
    engine = create_sqlite_engine()

    with Session(engine) as session:
        item = create_item(session)
        session.add(
            StockMovementDB(
                item_id=item.id,
                movement_type="OUT",
                quantity=1,
            )
        )
        session.commit()

        session.delete(item)
        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()
        assert session.get(ItemDB, item.id) is not None

    engine.dispose()


@pytest.mark.parametrize("movement_type", ["ADJ", "in", ""])
def test_service_rejects_invalid_movement_type(movement_type):
    engine = create_sqlite_engine()

    with Session(engine) as session:
        with pytest.raises(InvalidMovementTypeError):
            register_stock_movement(session, 1, movement_type, 1)

        assert session.scalar(select(ItemDB.id)) is None
        assert session.scalar(select(StockMovementDB.id)) is None

    engine.dispose()


@pytest.mark.parametrize("quantity", [0, -1, True, 1.5])
def test_service_rejects_non_positive_or_non_integer_quantity(quantity):
    engine = create_sqlite_engine()

    with Session(engine) as session:
        item = create_item(session)
        item_id = item.id
        session.rollback()

        with pytest.raises(InvalidMovementQuantityError):
            register_stock_movement(session, item_id, "IN", quantity)

        assert session.get(ItemDB, item_id).quantity_available == 0
        assert session.scalar(select(StockMovementDB.id)) is None

    engine.dispose()


def test_service_rejects_nonexistent_item():
    engine = create_sqlite_engine()

    with Session(engine) as session:
        with pytest.raises(ItemNotFoundError):
            register_stock_movement(session, 999, "IN", 1)

        assert session.scalar(select(StockMovementDB.id)) is None

    engine.dispose()


def test_service_rejects_inactive_item():
    engine = create_sqlite_engine()

    with Session(engine) as session:
        item = create_item(session)
        item_id = item.id
        item.active = False
        session.commit()

        with pytest.raises(InactiveItemError):
            register_stock_movement(session, item_id, "IN", 1)

        assert session.get(ItemDB, item_id).quantity_available == 0
        assert session.scalar(select(StockMovementDB.id)) is None

    engine.dispose()


def test_service_rejects_output_larger_than_available_stock():
    engine = create_sqlite_engine()

    with Session(engine) as session:
        item = create_item(session)
        item_id = item.id
        item.quantity_available = 2
        session.commit()

        with pytest.raises(InsufficientStockError):
            register_stock_movement(session, item_id, "OUT", 3)

        assert session.get(ItemDB, item_id).quantity_available == 2
        assert session.scalar(select(StockMovementDB.id)) is None

    engine.dispose()


def test_service_updates_stock_and_records_in_and_out_movements():
    engine = create_sqlite_engine()

    with Session(engine) as session:
        item = create_item(session)
        item_id = item.id
        session.rollback()

        incoming = register_stock_movement(
            session, item_id, "IN", 5, note="Delivery"
        )
        outgoing = register_stock_movement(
            session, item_id, "OUT", 2, note="Workshop use"
        )

        assert incoming.movement_type == "IN"
        assert incoming.quantity == 5
        assert incoming.note == "Delivery"
        assert outgoing.movement_type == "OUT"
        assert outgoing.quantity == 2
        assert outgoing.note == "Workshop use"
        assert session.get(ItemDB, item_id).quantity_available == 3
        assert len(session.scalars(select(StockMovementDB)).all()) == 2

    engine.dispose()


def test_service_rolls_back_stock_if_movement_flush_fails():
    engine = create_sqlite_engine()
    stock_update_executed = False

    def fail_after_stock_update(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ):
        nonlocal stock_update_executed
        if statement.lstrip().upper().startswith("UPDATE ITEMS "):
            stock_update_executed = True
            raise RuntimeError("simulated movement persistence failure")

    with Session(engine) as session:
        item = create_item(session)
        item_id = item.id
        session.rollback()
        event.listen(engine, "after_cursor_execute", fail_after_stock_update)

        try:
            with pytest.raises(
                RuntimeError,
                match="simulated movement persistence failure",
            ):
                register_stock_movement(session, item_id, "IN", 4)
        finally:
            event.remove(engine, "after_cursor_execute", fail_after_stock_update)

        assert stock_update_executed is True
        assert not session.in_transaction()

        with session.begin():
            assert session.get(ItemDB, item_id).quantity_available == 0
            assert session.scalar(select(StockMovementDB.id)) is None

    engine.dispose()
