from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app, get_service
from backend.db import connect, migrate
from backend.service import MisService


@pytest.fixture()
def client(tmp_path: Path):
    conn = connect(tmp_path / "api.sqlite3")
    migrate(conn)
    service = MisService(conn)

    def override_service() -> MisService:
        return service

    app.dependency_overrides[get_service] = override_service
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_api_purchase_and_stock(client: TestClient) -> None:
    login = client.post("/api/login", json={"username": "admin", "password": "admin"})
    assert login.status_code == 200

    created = client.post(
        "/api/purchases",
        headers={"X-User": "staff"},
        json={"imei": "860000000009999", "model": "iPhone 15", "recycle_price": 4500},
    )
    assert created.status_code == 200
    assert created.json()["status"] == "在库"

    stock = client.get("/api/stock", headers={"X-User": "staff"})
    assert stock.status_code == 200
    assert stock.json()[0]["imei"] == "860000000009999"


def test_api_forbidden_report_for_staff(client: TestClient) -> None:
    response = client.get("/api/reports", headers={"X-User": "staff"})
    assert response.status_code == 403
