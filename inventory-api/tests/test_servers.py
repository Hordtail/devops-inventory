from uuid import uuid4


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "DevOps Inventory API"}


def test_get_servers(client):
    response = client.get("/servers/")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_get_update_delete_server(client):
    unique_name = f"test-server-{uuid4().hex[:8]}"

    # CREATE
    response = client.post(
        "/servers/",
        json={
            "name": unique_name,
            "ip": "10.0.0.50",
            "environment": "development",
            "status": "running",
            "location": "Test",
        },
    )

    assert response.status_code == 200

    created = response.json()

    assert created["name"] == unique_name
    assert created["ip"] == "10.0.0.50"
    assert created["environment"] == "development"
    assert created["status"] == "running"
    assert created["location"] == "Test"
    assert "id" in created

    server_id = created["id"]

    # GET
    response = client.get(f"/servers/{server_id}")

    assert response.status_code == 200

    fetched = response.json()

    assert fetched["id"] == server_id
    assert fetched["name"] == unique_name

    # UPDATE
    response = client.put(
        f"/servers/{server_id}",
        json={
            "name": "updated-server",
            "ip": "10.0.0.51",
            "environment": "production",
            "status": "maintenance",
            "location": "Madrid",
        },
    )

    assert response.status_code == 200

    updated = response.json()

    assert updated["id"] == server_id
    assert updated["name"] == "updated-server"
    assert updated["ip"] == "10.0.0.51"
    assert updated["environment"] == "production"
    assert updated["status"] == "maintenance"
    assert updated["location"] == "Madrid"

    # DELETE
    response = client.delete(f"/servers/{server_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Server deleted successfully"

    # GET after DELETE
    response = client.get(f"/servers/{server_id}")

    assert response.status_code == 404


def test_get_nonexistent_server(client):
    response = client.get("/servers/999999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


def test_invalid_status(client):
    response = client.post(
        "/servers/",
        json={
            "name": f"invalid-server-{uuid4().hex[:8]}",
            "ip": "10.0.0.20",
            "environment": "development",
            "status": "active",
            "location": "Test",
        },
    )

    assert response.status_code == 422

