from __future__ import annotations

from pathlib import Path

import pytest

from backend.db import connect, migrate
from backend.models import (
    CustomerInput,
    LoginInput,
    PurchaseInput,
    RepairInput,
    Role,
    SellDeviceInput,
    SettlementInput,
    User,
)
from backend.service import BusinessError, MisService


@pytest.fixture()
def service(tmp_path: Path) -> MisService:
    conn = connect(tmp_path / "test.sqlite3")
    migrate(conn)
    return MisService(conn)


def user(role: Role = Role.admin) -> User:
    return User(username=role.value, role=role)


def test_login_and_permission_matrix(service: MisService) -> None:
    assert service.login(LoginInput(username="admin", password="admin"))["role"] == "admin"
    with pytest.raises(BusinessError):
        service.login(LoginInput(username="admin", password="bad"))
    with pytest.raises(PermissionError):
        service.reports(user(Role.staff))


def test_purchase_enforces_unique_imei(service: MisService) -> None:
    payload = PurchaseInput(
        imei="359001234567890",
        model="iPhone 15 Pro",
        recycle_price=4200,
        customer=CustomerInput(name="张三", phone="13800000000"),
    )
    created = service.create_purchase(user(), payload)
    assert created["status"] == "在库"
    with pytest.raises(BusinessError):
        service.create_purchase(user(), payload)


def test_sale_requires_in_stock_device(service: MisService) -> None:
    service.create_purchase(user(), PurchaseInput(imei="860000000000001", model="iPhone 14", recycle_price=3000))
    sold = service.sell_device(
        user(),
        SellDeviceInput(
            imei="860000000000001",
            buyer="李四",
            salesperson="王新淇",
            sale_price=3600,
        ),
    )
    assert sold["status"] == "已出"
    with pytest.raises(BusinessError):
        service.sell_device(
            user(),
            SellDeviceInput(imei="860000000000001", buyer="李四", salesperson="王新淇", sale_price=3600),
        )


def test_settlement_creates_traceable_items(service: MisService) -> None:
    customer = CustomerInput(name="同行客户", phone="13900000000", category="商家客户")
    service.create_purchase(user(), PurchaseInput(imei="860000000000002", model="iPhone 15", recycle_price=4000))
    customers = service.search_customers(user(), "同行客户")
    assert not customers

    cid = service.repo.upsert_customer(customer)
    service.conn.commit()
    service.sell_device(
        user(),
        SellDeviceInput(
            imei="860000000000002",
            buyer_customer_id=cid,
            buyer="同行客户",
            salesperson="王新淇",
            sale_price=4600,
        ),
    )
    repair = service.create_repair(
        user(),
        RepairInput(customer_id=cid, customer_name="同行客户", model="iPhone 13", quote=280, payment_method="同行挂账"),
    )
    preview = service.settlement_preview(user(Role.finance), cid)
    assert preview["total_amount"] == 4880

    result = service.settle_customer(
        user(Role.finance),
        SettlementInput(customer_id=cid, sale_imeis=["860000000000002"], repair_ids=[repair["repair_id"]]),
    )
    assert result["total_amount"] == 4880
    assert service.settlement_preview(user(Role.finance), cid)["total_amount"] == 0


def test_reports_are_traceable_to_details(service: MisService) -> None:
    service.create_purchase(user(), PurchaseInput(imei="860000000000003", model="iPhone 12", recycle_price=2100))
    report = service.reports(user(Role.finance))
    assert report["inventory_cost"] == 2100
    assert report["inventory_count"] == 1
    assert report["details"]["inventory"][0]["imei"] == "860000000000003"
