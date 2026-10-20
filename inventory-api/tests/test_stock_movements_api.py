import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.routers.items import router as items_router


@pytest.fixture
def client():
    test_app = FastAPI()
    test_app.include_router(items_router)
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(test_app) as test_client:
            yield test_client
    finally:
        test_app.dependency_overrides.clear()
        engine.dispose()


def create_item(client, *, active=True):
    return client.post(
        "/items/",
        json={
            "code": "BRK-001",
            "name": "Brake pad",
            "unit": "pcs",
            "active": active,
        },
    )


def test_register_stock_in_returns_created_movement(client):
    item = create_item(client)

    response = client.post(
        f"/items/{item.json()['id']}/movements/in",
        json={"quantity": 5, "note": "Delivery"},
    )

    assert response.status_code == 200
    movement = response.json()
    assert movement["id"] > 0
    assert movement["item_id"] == item.json()["id"]
    assert movement["movement_type"] == "IN"
    assert movement["quantity"] == 5
    assert movement["occurred_at"]
    assert movement["note"] == "Delivery"

    updated_item = client.get(f"/items/{item.json()['id']}")
    assert updated_item.json()["quantity_available"] == 5


def test_register_stock_out_returns_created_movement(client):
    item = create_item(client)
    item_id = item.json()["id"]
    client.post(f"/items/{item_id}/movements/in", json={"quantity": 5})

    response = client.post(
        f"/items/{item_id}/movements/out",
        json={"quantity": 2, "note": "Workshop use"},
    )

    assert response.status_code == 200
    movement = response.json()
    assert movement["item_id"] == item_id
    assert movement["movement_type"] == "OUT"
    assert movement["quantity"] == 2
    assert movement["occurred_at"]
    assert movement["note"] == "Workshop use"

    updated_item = client.get(f"/items/{item_id}")
    assert updated_item.json()["quantity_available"] == 3


def test_stock_movement_for_nonexistent_item_returns_404(client):
    response = client.post(
        "/items/999999/movements/in",
        json={"quantity": 1},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


def test_stock_movement_for_inactive_item_returns_409(client):
    item = create_item(client, active=False)

    response = client.post(
        f"/items/{item.json()['id']}/movements/in",
        json={"quantity": 1},
    )

    assert response.status_code == 409


def test_stock_out_greater_than_available_returns_409(client):
    item = create_item(client)

    response = client.post(
        f"/items/{item.json()['id']}/movements/out",
        json={"quantity": 1},
    )

    assert response.status_code == 409


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True])
def test_stock_movement_rejects_invalid_quantity(client, quantity):
    item = create_item(client)

    response = client.post(
        f"/items/{item.json()['id']}/movements/in",
        json={"quantity": quantity},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "forbidden_field",
    ["item_id", "movement_type", "occurred_at", "quantity_available"],
)
def test_stock_movement_rejects_client_controlled_fields(client, forbidden_field):
    item = create_item(client)
    payload = {"quantity": 1, forbidden_field: "client value"}

    response = client.post(
        f"/items/{item.json()['id']}/movements/in",
        json=payload,
    )

    assert response.status_code == 422
