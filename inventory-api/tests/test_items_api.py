def create_item(client, code, name, unit="pcs", active=True):
    return client.post(
        "/items/",
        json={"code": code, "name": name, "unit": unit, "active": active},
    )


def update_item(client, item_id, code, name, unit="pcs", active=True):
    return client.put(
        f"/items/{item_id}",
        json={"code": code, "name": name, "unit": unit, "active": active},
    )


def test_list_items_is_ordered_by_id(client):
    first = create_item(client, "ITEM-B", "Second alphabetically")
    second = create_item(client, "ITEM-A", "First alphabetically")

    assert first.status_code == 200
    assert second.status_code == 200

    response = client.get("/items/")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        first.json()["id"],
        second.json()["id"],
    ]


def test_create_and_get_item(client):
    response = create_item(
        client,
        "BRAKE-PAD-001",
        "Brake pad",
        unit="pair",
        active=False,
    )

    assert response.status_code == 200
    created = response.json()
    assert created["code"] == "BRAKE-PAD-001"
    assert created["name"] == "Brake pad"
    assert created["unit"] == "pair"
    assert created["active"] is False

    fetched_response = client.get(f"/items/{created['id']}")

    assert fetched_response.status_code == 200
    assert fetched_response.json() == created


def test_get_nonexistent_item_returns_404(client):
    response = client.get("/items/999999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


def test_duplicate_item_code_returns_409_and_session_recovers(client):
    first = create_item(client, "FILTER-001", "Oil filter")
    duplicate = create_item(client, "FILTER-001", "Duplicate filter")

    assert first.status_code == 200
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Item code already exists"}

    next_item = create_item(client, "FILTER-002", "Air filter")
    assert next_item.status_code == 200


def test_update_item(client):
    created = create_item(client, "BELT-001", "Old belt")

    response = update_item(
        client,
        created.json()["id"],
        "BELT-002",
        "Replacement belt",
        unit="each",
        active=False,
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": created.json()["id"],
        "code": "BELT-002",
        "name": "Replacement belt",
        "unit": "each",
        "active": False,
        "quantity_available": 0,
        "minimum_stock": 1,
    }


def test_update_nonexistent_item_returns_404(client):
    response = update_item(client, 999999999, "BELT-002", "Replacement belt")

    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


def test_update_item_with_duplicate_code_returns_409_and_rolls_back(client):
    item = create_item(client, "BELT-001", "First belt")
    create_item(client, "BELT-002", "Second belt")

    response = update_item(client, item.json()["id"], "BELT-002", "Changed belt")

    assert response.status_code == 409
    assert response.json() == {"detail": "Item code already exists"}

    unchanged = client.get(f"/items/{item.json()['id']}")
    assert unchanged.status_code == 200
    assert unchanged.json()["code"] == "BELT-001"
    assert unchanged.json()["name"] == "First belt"


def test_update_rejects_blank_required_fields(client):
    item = create_item(client, "BELT-001", "First belt")

    response = update_item(client, item.json()["id"], "BELT-002", "   ")

    assert response.status_code == 422


def test_deactivate_item(client):
    item = create_item(client, "BELT-001", "First belt")

    response = client.patch(f"/items/{item.json()['id']}/deactivate")

    assert response.status_code == 200
    assert response.json()["active"] is False


def test_deactivation_persists_when_item_is_read_again(client):
    item = create_item(client, "BELT-001", "First belt")
    client.patch(f"/items/{item.json()['id']}/deactivate")

    response = client.get(f"/items/{item.json()['id']}")

    assert response.status_code == 200
    assert response.json()["active"] is False
