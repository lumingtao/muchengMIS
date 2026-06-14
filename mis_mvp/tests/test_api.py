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


def test_api_repair_order_delete_archives_and_exact_searches(client: TestClient) -> None:
    created = client.post(
        "/api/repair-orders",
        headers={"X-User": "frontdesk"},
        json={"machine": {"imei": "860000000008889", "model": "iPhone 15"}, "fault_description": "误开订单"},
    )
    assert created.status_code == 200
    payload = created.json()
    repair_id = payload["repair_order_id"]
    order_no = payload["order_no"]

    forbidden = client.request(
        "DELETE",
        f"/api/repair-orders/{repair_id}",
        headers={"X-User": "frontdesk"},
        json={"reason": "前台无权删除"},
    )
    assert forbidden.status_code == 403

    deleted = client.request(
        "DELETE",
        f"/api/repair-orders/{repair_id}",
        headers={"X-User": "admin"},
        json={"reason": "重复录入"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["archived"] is True

    workbench = client.get("/api/repair-workbench", headers={"X-User": "frontdesk"})
    assert workbench.status_code == 200
    assert all(row["repair_order_id"] != repair_id for row in workbench.json()["orders"])

    partial = client.get(f"/api/repair-orders/archive-search?order_no={order_no[:8]}", headers={"X-User": "frontdesk"})
    assert partial.status_code == 200
    assert partial.json() == {}

    archived = client.get(f"/api/repair-orders/archive-search?order_no={order_no}", headers={"X-User": "frontdesk"})
    assert archived.status_code == 200
    assert archived.json()["order"]["repair_order_id"] == repair_id
    assert archived.json()["archive"]["archive_reason"] == "重复录入"


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


def test_api_member_crm_create_filter_detail_and_interactions(client: TestClient) -> None:
    created = client.post(
        "/api/customers",
        headers={"X-User": "frontdesk"},
        json={
            "name": "会员客户",
            "phone": "13800001111",
            "category": "VIP客户",
            "vip_level": "金卡",
            "tags": "高价值,屏幕维修",
            "source": "到店",
            "birthday": "1990-01-02",
        },
    )
    assert created.status_code == 200
    customer = created.json()
    assert customer["member_no"].startswith("M")
    assert customer["status"] == "正常"

    filtered = client.get(
        "/api/customers?q=会员&category=VIP客户&vip_level=金卡&status=正常&tag=屏幕",
        headers={"X-User": "frontdesk"},
    )
    assert filtered.status_code == 200
    assert [row["customer_id"] for row in filtered.json()] == [customer["customer_id"]]

    repair = client.post(
        "/api/repair-orders",
        headers={"X-User": "frontdesk"},
        json={
            "customer_id": customer["customer_id"],
            "machine": {"imei": "860000000006666", "model": "iPhone 15"},
            "fault_description": "屏幕不亮",
            "repair_items": [{"item_name": "屏幕维修", "charge_amount": 300}],
        },
    )
    assert repair.status_code == 200

    interaction = client.post(
        f"/api/customers/{customer['customer_id']}/interactions",
        headers={"X-User": "frontdesk"},
        json={"interaction_type": "回访", "content": "提醒客户取机", "next_follow_at": "2026-06-20"},
    )
    assert interaction.status_code == 200
    assert interaction.json()["completed"] == 0

    updated = client.put(
        f"/api/customer-interactions/{interaction.json()['interaction_id']}",
        headers={"X-User": "frontdesk"},
        json={"interaction_type": "回访", "content": "客户已确认", "completed": True},
    )
    assert updated.status_code == 200
    assert updated.json()["completed"] == 1

    detail = client.get(f"/api/customers/{customer['customer_id']}", headers={"X-User": "frontdesk"})
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["customer"]["name"] == "会员客户"
    assert payload["stats"]["repair_count"] == 1
    assert payload["repair_orders"][0]["fault_description"] == "屏幕不亮"
    assert payload["interactions"][0]["content"] == "客户已确认"


def test_api_member_crm_write_permission_required(client: TestClient) -> None:
    response = client.post(
        "/api/customers",
        headers={"X-User": "engineer"},
        json={"name": "无权新增客户"},
    )
    assert response.status_code == 403


def test_member_metadata_is_preserved_when_order_reuses_customer(client: TestClient) -> None:
    created = client.post(
        "/api/customers",
        headers={"X-User": "frontdesk"},
        json={
            "name": "保留资料客户",
            "phone": "13800002222",
            "category": "VIP客户",
            "vip_level": "金卡",
            "tags": "重要客户",
            "source": "转介绍",
            "remark": "不要清空",
        },
    )
    assert created.status_code == 200
    customer = created.json()

    order = client.post(
        "/api/repair-orders",
        headers={"X-User": "frontdesk"},
        json={
            "customer": {"name": "保留资料客户", "phone": "13800002222"},
            "machine": {"imei": "860000000005555", "model": "iPhone 14"},
            "fault_description": "无法开机",
        },
    )
    assert order.status_code == 200

    detail = client.get(f"/api/customers/{customer['customer_id']}", headers={"X-User": "frontdesk"})
    assert detail.status_code == 200
    payload = detail.json()["customer"]
    assert payload["vip_level"] == "金卡"
    assert payload["tags"] == "重要客户"
    assert payload["source"] == "转介绍"
    assert payload["remark"] == "不要清空"


def test_customer_member_no_backfilled_on_migration(tmp_path: Path) -> None:
    from backend.db import connect, migrate

    conn = connect(tmp_path / "legacy.sqlite3")
    conn.executescript(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            wechat TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '个人客户',
            shop_name TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '',
            vip_level TEXT NOT NULL DEFAULT '',
            discount_policy TEXT NOT NULL DEFAULT '',
            remark TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO customers (name, phone) VALUES ('老客户', '13900001111');
        """
    )
    migrate(conn)
    row = conn.execute("SELECT member_no, status FROM customers WHERE name='老客户'").fetchone()
    assert row["member_no"] == "M000001"
    assert row["status"] == "正常"
