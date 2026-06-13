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


def test_api_upload_repair_order_photo(client: TestClient) -> None:
    created = client.post(
        "/api/repair-orders",
        headers={"X-User": "staff"},
        json={"machine": {"imei": "860000000008888", "model": "iPhone 15"}, "fault_description": "屏幕异常"},
    )
    assert created.status_code == 200
    repair_id = created.json()["repair_order_id"]

    uploaded = client.post(
        f"/api/repair-orders/{repair_id}/photos",
        headers={"X-User": "staff"},
        data={"stage": "pre"},
        files={"file": ("before.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
    )
    assert uploaded.status_code == 200
    payload = uploaded.json()
    assert payload["stage"] == "pre"
    assert payload["url"].startswith(f"/uploads/repair_orders/{repair_id}/")

    photos = client.get(f"/api/repair-orders/{repair_id}/photos", headers={"X-User": "staff"})
    assert photos.status_code == 200
    assert photos.json()[0]["photo_id"] == payload["photo_id"]

    detail = client.get(f"/api/repair-workbench/{repair_id}", headers={"X-User": "staff"})
    assert detail.status_code == 200
    assert any(row["title"] == "上传维修前照片" for row in detail.json()["events"])
def test_api_save_repair_order_inspection_logs_event(client: TestClient) -> None:
    created = client.post(
        "/api/repair-orders",
        headers={"X-User": "staff"},
        json={"machine": {"imei": "860000000007777", "model": "iPhone 16"}, "fault_description": "检测异常"},
    )
    assert created.status_code == 200
    repair_id = created.json()["repair_order_id"]

    saved = client.post(
        f"/api/repair-orders/{repair_id}/inspections",
        headers={"X-User": "staff"},
        json={
            "stage": "pre",
            "items": [
                {"item": "屏幕显示", "abnormal": True},
                {"item": "其他异常", "abnormal": True},
            ],
            "note": "边框变形",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["stage"] == "pre"

    detail = client.get(f"/api/repair-workbench/{repair_id}", headers={"X-User": "staff"})
    assert detail.status_code == 200
    payload = detail.json()
    assert any(row["stage"] == "pre" and row["item"] == "其他异常" for row in payload["inspections"])
    assert any(row["title"] == "更新维修前检测" for row in payload["events"])

    invalid = client.post(
        f"/api/repair-orders/{repair_id}/inspections",
        headers={"X-User": "staff"},
        json={"stage": "post", "items": [{"item": "其他异常", "abnormal": True}], "note": ""},
    )
    assert invalid.status_code == 400
