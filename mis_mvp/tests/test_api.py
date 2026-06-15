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


def test_api_warehouse_material_lifecycle(client: TestClient) -> None:
    category = client.post(
        "/api/material-categories",
        headers={"X-User": "admin"},
        json={"category_code": "SCREEN", "name": "屏幕总成"},
    )
    assert category.status_code == 200

    area = client.post(
        "/api/warehouse/areas",
        headers={"X-User": "admin"},
        json={"area_code": "MAIN", "name": "维修主仓"},
    )
    assert area.status_code == 200
    location = client.post(
        "/api/warehouse/locations",
        headers={"X-User": "admin"},
        json={"area_id": area.json()["area_id"], "location_code": "A-01", "name": "屏幕柜"},
    )
    assert location.status_code == 200

    material = client.post(
        "/api/materials",
        headers={"X-User": "admin"},
        json={
            "sku": "SCR-IP13-OLED",
            "material_code": "SCR-IP13-OLED",
            "category_id": category.json()["category_id"],
            "default_location_id": location.json()["location_id"],
            "name": "iPhone 13 OLED 屏幕总成",
            "compatible_range": "iPhone 13",
            "min_qty": 2,
            "avg_cost": 315,
        },
    )
    assert material.status_code == 200
    material_id = material.json()["material_id"]

    batch = client.post(
        "/api/material-batches/purchase",
        headers={"X-User": "admin"},
        json={"material_id": material_id, "location_id": location.json()["location_id"], "qty": 3, "unit_cost": 315, "supplier": "测试供应商"},
    )
    assert batch.status_code == 200
    batch_id = batch.json()["batch_id"]

    units = client.get(f"/api/material-units?material_id={material_id}&status=在库可用", headers={"X-User": "admin"})
    assert units.status_code == 200
    assert len(units.json()) == 3

    repair = client.post(
        "/api/repair-orders",
        headers={"X-User": "staff"},
        json={"machine": {"imei": "860000000001313", "model": "iPhone 13"}, "fault_description": "屏幕碎裂"},
    )
    assert repair.status_code == 200
    repair_id = repair.json()["repair_order_id"]

    request = client.post(
        "/api/material-requests",
        headers={"X-User": "engineer"},
        json={"repair_order_id": repair_id, "items": [{"material_id": material_id, "qty": 2}], "remark": "维修领料"},
    )
    assert request.status_code == 200
    request_id = request.json()["request_id"]
    assert request.json()["status"] == "待审核"

    approved = client.post(f"/api/material-requests/{request_id}/approve", headers={"X-User": "admin"}, json={})
    assert approved.status_code == 200
    issued = client.post(f"/api/material-requests/{request_id}/issue", headers={"X-User": "admin"}, json={})
    assert issued.status_code == 200
    assert issued.json()["status"] == "已发放"

    material_after_issue = client.get(f"/api/materials/{material_id}", headers={"X-User": "admin"})
    assert material_after_issue.status_code == 200
    assert material_after_issue.json()["current_qty"] == 1
    assert len(material_after_issue.json()["movements"]) == 5

    issued_units = client.get(f"/api/material-units?repair_order_id={repair_id}&status=已发放", headers={"X-User": "admin"})
    assert issued_units.status_code == 200
    returned_unit_id = issued_units.json()[0]["unit_id"]
    return_request = client.post(
        f"/api/material-issues/{returned_unit_id}/return-request",
        headers={"X-User": "engineer"},
        json={"return_type": "工程师退料", "remark": "未使用"},
    )
    assert return_request.status_code == 200
    inspected = client.post(
        f"/api/material-returns/{return_request.json()['return_id']}/inspect",
        headers={"X-User": "admin"},
        json={"inspect_result": "可复用", "remark": "验收通过"},
    )
    assert inspected.status_code == 200
    assert inspected.json()["status"] == "已重新入库"

    returned_material = client.get(f"/api/materials/{material_id}", headers={"X-User": "admin"})
    assert returned_material.status_code == 200
    assert returned_material.json()["current_qty"] == 2

    batch_return = client.post(
        f"/api/material-batches/{batch_id}/return",
        headers={"X-User": "admin"},
        json={"qty": 1, "refund_status": "已退款", "refund_amount": 315},
    )
    assert batch_return.status_code == 200
    assert len(batch_return.json()["returned_units"]) == 1

    counted = client.post(
        "/api/stock-counts",
        headers={"X-User": "admin"},
        json={"items": [{"material_id": material_id, "actual_qty": 2, "reason": "盘点补差"}]},
    )
    assert counted.status_code == 200
    confirmed = client.post(f"/api/stock-counts/{counted.json()['count_id']}/confirm", headers={"X-User": "admin"})
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "已确认"

    dashboard = client.get("/api/warehouse/dashboard", headers={"X-User": "admin"})
    assert dashboard.status_code == 200
    assert dashboard.json()["metrics"]["stock_value"] >= 630

    forbidden = client.post(
        "/api/stock-adjustments",
        headers={"X-User": "finance"},
        json={"material_id": material_id, "qty": 1, "adjustment_type": "报损出库"},
    )
    assert forbidden.status_code == 403


def test_api_repair_sku_material_reservation_and_consumption(client: TestClient) -> None:
    category = client.post(
        "/api/material-categories",
        headers={"X-User": "admin"},
        json={"category_code": "BAT", "name": "电池"},
    )
    assert category.status_code == 200
    area = client.post("/api/warehouse/areas", headers={"X-User": "admin"}, json={"area_code": "BAT", "name": "电池仓"})
    assert area.status_code == 200
    location = client.post(
        "/api/warehouse/locations",
        headers={"X-User": "admin"},
        json={"area_id": area.json()["area_id"], "location_code": "BAT-A01", "name": "电池 A01"},
    )
    assert location.status_code == 200
    material = client.post(
        "/api/materials",
        headers={"X-User": "admin"},
        json={
            "sku": "BAT-IP15",
            "material_code": "BAT-IP15",
            "category_id": category.json()["category_id"],
            "default_location_id": location.json()["location_id"],
            "name": "iPhone 15 电池",
            "compatible_range": "iPhone 15",
            "min_qty": 1,
            "avg_cost": 180,
        },
    )
    assert material.status_code == 200
    material_id = material.json()["material_id"]
    batch = client.post(
        "/api/material-batches/purchase",
        headers={"X-User": "admin"},
        json={"material_id": material_id, "location_id": location.json()["location_id"], "qty": 2, "unit_cost": 180, "supplier": "测试供应商"},
    )
    assert batch.status_code == 200

    sku = client.post(
        "/api/repair-skus",
        headers={"X-User": "admin"},
        json={
            "model": "iPhone 15",
            "sku_code": "BAT-REPLACE-IP15",
            "fault_name": "电池老化",
            "solution_name": "更换电池",
            "cost_amount": 260,
            "charge_amount": 80,
            "enabled": True,
        },
    )
    assert sku.status_code == 200
    sku_id = sku.json()["sku_id"]
    binding = client.post(
        f"/api/repair-skus/{sku_id}/materials",
        headers={"X-User": "admin"},
        json={"items": [{"material_id": material_id, "qty": 1, "priority": 1, "is_required": True}]},
    )
    assert binding.status_code == 200
    assert binding.json()["materials"][0]["available_qty"] == 2

    order = client.post(
        "/api/repair-orders",
        headers={"X-User": "staff"},
        json={
            "machine": {"imei": "860000000001515", "model": "iPhone 15"},
            "fault_description": "电池不耐用",
            "repair_items": [{"sku_id": sku_id, "item_name": "更换电池", "quantity": 1}],
        },
    )
    assert order.status_code == 200
    repair_id = order.json()["repair_order_id"]

    detail = client.get(f"/api/repair-workbench/{repair_id}", headers={"X-User": "staff"})
    assert detail.status_code == 200
    reservations = detail.json()["material_reservations"]
    assert reservations[0]["status"] == "已预占"
    assert reservations[0]["reserved_qty"] == 1
    material_after_reserve = client.get(f"/api/materials/{material_id}", headers={"X-User": "admin"})
    assert material_after_reserve.status_code == 200
    assert material_after_reserve.json()["current_qty"] == 2
    assert material_after_reserve.json()["reserved_qty"] == 1
    assert material_after_reserve.json()["sellable_qty"] == 1

    consumed_response = client.post(
        f"/api/repair-orders/{repair_id}/materials/consume",
        headers={"X-User": "staff"},
        json={"remark": "维修完成"},
    )
    assert consumed_response.status_code == 200
    after_close = client.get(f"/api/repair-workbench/{repair_id}", headers={"X-User": "staff"})
    assert after_close.status_code == 200
    consumed = after_close.json()["material_reservations"][0]
    assert consumed["status"] == "已消耗"
    assert consumed["consumed_qty"] == 1
    assert any(row["item_type"] == "库存物料" and row["total_cost"] == 180 for row in after_close.json()["cost_items"])
    material_after_consume = client.get(f"/api/materials/{material_id}", headers={"X-User": "admin"})
    assert material_after_consume.status_code == 200
    assert material_after_consume.json()["current_qty"] == 1


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
