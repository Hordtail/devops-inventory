from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.routers.items import router as items_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ITEM_IMAGE_DIR", str(tmp_path / "images"))
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


def create_item(client, **payload):
    data = {
        "code": "ITEM-001",
        "name": "Brake pad",
        "unit": "pair",
        **payload,
    }
    response = client.post("/items/", json=data)
    assert response.status_code == 200
    return response.json()


def png_image(color=(25, 90, 160)):
    image = Image.new("RGB", (12, 8), color)
    result = BytesIO()
    image.save(result, format="PNG")
    return result.getvalue()


def test_item_description_is_created_returned_and_updated(client):
    item = create_item(client, description="  Ceramic brake pads  ")
    assert item["description"] == "Ceramic brake pads"
    assert item["image_path"] is None

    updated = client.put(
        f"/items/{item['id']}",
        json={
            "code": item["code"],
            "name": item["name"],
            "unit": item["unit"],
            "active": True,
            "description": "Workshop front axle set",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Workshop front axle set"


def test_update_without_description_preserves_existing_description(client):
    item = create_item(client, description="Keep this description")
    updated = client.put(
        f"/items/{item['id']}",
        json={
            "code": item["code"],
            "name": "Updated brake pad",
            "unit": item["unit"],
            "active": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Keep this description"


def test_item_movement_history_is_newest_first_and_paginated(client):
    item = create_item(client)
    item_id = item["id"]
    incoming = client.post(
        f"/items/{item_id}/movements/in",
        json={"quantity": 5, "note": "Delivery"},
    )
    outgoing = client.post(
        f"/items/{item_id}/movements/out",
        json={"quantity": 2, "note": "Repair order 14"},
    )
    assert incoming.status_code == outgoing.status_code == 200

    history = client.get(f"/items/{item_id}/movements")
    assert history.status_code == 200
    movements = history.json()
    assert [entry["id"] for entry in movements] == [
        outgoing.json()["id"],
        incoming.json()["id"],
    ]
    assert movements[0]["movement_type"] == "OUT"
    assert movements[0]["quantity"] == 2
    assert movements[0]["note"] == "Repair order 14"
    assert movements[0]["occurred_at"]

    page = client.get(f"/items/{item_id}/movements?limit=1&offset=1")
    assert [entry["id"] for entry in page.json()] == [incoming.json()["id"]]


def test_movement_history_for_missing_item_returns_404(client):
    response = client.get("/items/99999/movements")
    assert response.status_code == 404


def test_valid_image_upload_is_saved_and_served(client, tmp_path):
    item = create_item(client)
    upload = client.post(
        f"/items/{item['id']}/image",
        files={"image": ("client-name.png", png_image(), "application/octet-stream")},
    )
    assert upload.status_code == 200
    image_reference = upload.json()["image_path"]
    assert image_reference
    assert "/" not in image_reference and "\\" not in image_reference
    assert (tmp_path / "images" / image_reference).is_file()

    fetched = client.get(f"/items/{item['id']}/image")
    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "image/png"
    with Image.open(BytesIO(fetched.content)) as image:
        image.verify()


def test_replacing_image_removes_only_previous_generated_file(client, tmp_path):
    item = create_item(client)
    first = client.post(
        f"/items/{item['id']}/image",
        files={"image": ("first.png", png_image(), "image/png")},
    ).json()["image_path"]
    second_response = client.post(
        f"/items/{item['id']}/image",
        files={"image": ("second.png", png_image((180, 35, 30)), "image/png")},
    )
    second = second_response.json()["image_path"]

    assert second_response.status_code == 200
    assert second != first
    assert not (tmp_path / "images" / first).exists()
    assert (tmp_path / "images" / second).is_file()


def test_image_upload_rejects_non_image_content_despite_image_filename(client):
    item = create_item(client)
    response = client.post(
        f"/items/{item['id']}/image",
        files={"image": ("looks-like.png", b"<html>not an image</html>", "image/png")},
    )
    assert response.status_code == 415
    assert response.json()["detail"]


def test_image_upload_rejects_oversized_file(client):
    item = create_item(client)
    response = client.post(
        f"/items/{item['id']}/image",
        files={"image": ("large.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")},
    )
    assert response.status_code == 413


def test_image_routes_return_404_for_missing_or_imageless_items(client):
    missing = client.get("/items/99999/image")
    assert missing.status_code == 404

    item = create_item(client)
    no_image = client.get(f"/items/{item['id']}/image")
    assert no_image.status_code == 404

    missing_upload = client.post(
        "/items/99999/image",
        files={"image": ("photo.png", png_image(), "image/png")},
    )
    assert missing_upload.status_code == 404
