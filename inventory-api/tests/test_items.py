import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db_models import ItemDB
from app.main import app
from app.models import Item, ItemCreate, ItemUpdate


def test_item_create_accepts_valid_fields_and_defaults_active():
    item = ItemCreate(code=" BRK-001 ", name=" Brake pad ", unit=" pcs ")

    assert item.model_dump() == {
        "code": "BRK-001",
        "name": "Brake pad",
        "unit": "pcs",
        "active": True,
        "minimum_stock": 1,
    }


def test_item_stock_defaults_match_orm_and_database_defaults():
    quantity = ItemDB.__table__.c.quantity_available
    minimum = ItemDB.__table__.c.minimum_stock

    assert quantity.default.arg == 0
    assert str(quantity.server_default.arg) == "0"
    assert minimum.default.arg == 1
    assert str(minimum.server_default.arg) == "1"


def test_minimum_stock_can_be_configured_and_cannot_be_negative():
    item = ItemCreate(
        code="BRK-001",
        name="Brake pad",
        unit="pcs",
        minimum_stock=4,
    )

    assert item.minimum_stock == 4

    with pytest.raises(ValidationError):
        ItemCreate(code="BRK-002", name="Brake pad", unit="pcs", minimum_stock=-1)

    with pytest.raises(ValidationError):
        ItemUpdate(
            code="BRK-002",
            name="Brake pad",
            unit="pcs",
            active=True,
            minimum_stock=-1,
        )

    with pytest.raises(ValidationError):
        ItemUpdate(
            code="BRK-002",
            name="Brake pad",
            unit="pcs",
            active=True,
            minimum_stock=None,
        )


def test_stock_quantity_cannot_be_set_in_create_or_update_schemas():
    with pytest.raises(ValidationError):
        ItemCreate(
            code="BRK-001",
            name="Brake pad",
            unit="pcs",
            quantity_available=100,
        )

    with pytest.raises(ValidationError):
        ItemUpdate(
            code="BRK-001",
            name="Brake pad",
            unit="pcs",
            active=True,
            quantity_available=100,
        )


def test_item_stock_check_constraints_are_registered():
    constraint_names = {
        constraint.name for constraint in ItemDB.__table__.constraints
    }

    assert "ck_items_quantity_available_nonnegative" in constraint_names
    assert "ck_items_minimum_stock_nonnegative" in constraint_names


def test_catalog_and_server_routes_remain_registered():
    registered_routes = app.openapi()["paths"]

    assert "get" in registered_routes["/items/"]
    assert "get" in registered_routes["/items/{item_id}"]
    assert "post" in registered_routes["/items/"]
    assert "put" in registered_routes["/items/{item_id}"]
    assert "patch" in registered_routes["/items/{item_id}/deactivate"]
    assert "get" in registered_routes["/servers/"]
    assert "get" in registered_routes["/servers/{server_id}"]
    assert "post" in registered_routes["/servers/"]
    assert "put" in registered_routes["/servers/{server_id}"]
    assert "delete" in registered_routes["/servers/{server_id}"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("code", ""),
        ("code", "   "),
        ("name", ""),
        ("name", "   "),
        ("unit", ""),
        ("unit", "   "),
        ("code", "x" * 51),
        ("name", "x" * 101),
        ("unit", "x" * 21),
    ],
)
def test_item_create_rejects_invalid_required_text(field, value):
    payload = {"code": "BRK-001", "name": "Brake pad", "unit": "pcs"}
    payload[field] = value

    with pytest.raises(ValidationError):
        ItemCreate(**payload)


def test_item_response_reads_sqlalchemy_attributes():
    class ItemAttributes:
        id = 1
        code = "BRK-001"
        name = "Brake pad"
        unit = "pcs"
        active = True
        quantity_available = 0
        minimum_stock = 1

    item = Item.model_validate(ItemAttributes(), from_attributes=True)

    assert item.active is True
    assert item.quantity_available == 0
    assert item.minimum_stock == 1


def test_item_persists_to_database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    ItemDB.__table__.create(engine)

    with Session(engine) as session:
        item = ItemDB(code="BRK-001", name="Brake pad", unit="pcs")
        session.add(item)
        session.commit()

        loaded = session.get(ItemDB, item.id)

        assert loaded is not None
        assert loaded.code == "BRK-001"
        assert loaded.name == "Brake pad"
        assert loaded.unit == "pcs"
        assert loaded.active is True
        assert loaded.quantity_available == 0
        assert loaded.minimum_stock == 1

    engine.dispose()


def test_item_code_is_unique_in_database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    ItemDB.__table__.create(engine)

    with Session(engine) as session:
        session.add(ItemDB(code="BRK-001", name="Brake pad", unit="pcs"))
        session.commit()
        session.add(ItemDB(code="BRK-001", name="Another pad", unit="pcs"))

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()

    engine.dispose()
