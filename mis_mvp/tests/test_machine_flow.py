from __future__ import annotations

from pathlib import Path

import pytest

from backend.db import connect, migrate
from backend.models import (
    CustomerInput,
    MachineInput,
    MachineNoteInput,
    MachineStatus,
    MachineUpdateInput,
    OrderStatus,
    PaymentDirection,
    PaymentInput,
    RecycleOrderInput,
    RecycleQuoteInput,
    RepairDeliverInput,
    RepairItemInput,
    RepairOrderInput,
    RepairOrderStatusInput,
    RepairQuoteInput,
    Role,
    SalesOrderInput,
    StockInInput,
    User,
)
from backend.service import BusinessError, MisService


@pytest.fixture()
def service(tmp_path: Path) -> MisService:
    conn = connect(tmp_path / "machine.sqlite3")
    migrate(conn)
    return MisService(conn)


def user(role: Role = Role.admin) -> User:
    return User(username=role.value, role=role)


def test_machine_unique_imei_and_temp_no(service: MisService) -> None:
    first = service.create_machine(user(), MachineInput(imei="861111111111111", model="iPhone 15"))
    assert first["imei"] == "861111111111111"
    temp = service.create_machine(user(), MachineInput(model="无 IMEI 机器"))
    assert temp["machine_no"].startswith("TMP-")
    with pytest.raises(BusinessError):
        service.create_machine(user(), MachineInput(imei="861111111111111", model="重复机器"))


def test_machine_update_writes_timeline_event(service: MisService) -> None:
    machine = service.create_machine(user(), MachineInput(imei="861000000000001", model="iPhone 14"))
    updated = service.update_machine(
        user(Role.staff),
        machine["machine_id"],
        MachineUpdateInput(
            imei="861000000000001",
            serial="SN-EDIT",
            model="iPhone 14 Pro",
            memory="256G",
            color="黑色",
            condition="屏幕轻微划痕",
            source_type=None,
            current_status=MachineStatus.repairing,
        ),
    )
    assert updated["model"] == "iPhone 14 Pro"
    timeline = service.machine_timeline(user(), machine["machine_id"])
    assert any(event["title"] == "编辑订单" and "机型" in event["detail"] for event in timeline["events"])


def test_machine_notes_are_append_only(service: MisService) -> None:
    machine = service.create_machine(user(), MachineInput(imei="861000000000003", model="iPhone 14"))
    first = service.add_machine_note(user(Role.staff), machine["machine_id"], MachineNoteInput(content="客户要求加急"))
    second = service.add_machine_note(user(Role.staff), machine["machine_id"], MachineNoteInput(content="已电话确认价格"))
    assert second["note_id"] > first["note_id"]
    timeline = service.machine_timeline(user(), machine["machine_id"])
    assert [note["content"] for note in timeline["notes"]] == ["客户要求加急", "已电话确认价格"]


def test_machine_delete_removes_order_and_requires_permission(service: MisService) -> None:
    machine = service.create_machine(user(), MachineInput(imei="861000000000002", model="iPhone 15"))
    with pytest.raises(PermissionError):
        service.delete_machine(user(Role.staff), machine["machine_id"])
    result = service.delete_machine(user(Role.admin), machine["machine_id"])
    assert result["deleted"] is True
    with pytest.raises(BusinessError):
        service.machine_timeline(user(), machine["machine_id"])


def test_repair_lifecycle_and_payment_timeline(service: MisService) -> None:
    order = service.create_repair_order(
        user(Role.staff),
        RepairOrderInput(
            machine=MachineInput(imei="862222222222222", model="iPhone 14"),
            customer=CustomerInput(name="维修客户", phone="13800000000"),
            fault_description="不开机",
        ),
    )
    repair_id = order["repair_order_id"]
    diagnosing = service.update_repair_order_status(user(Role.staff), repair_id, RepairOrderStatusInput(status=OrderStatus.diagnosing))
    assert diagnosing["status"] == "检测中"
    quoted = service.quote_repair_order(user(Role.staff), repair_id, RepairQuoteInput(diagnosis="主板故障", quoted_amount=580))
    assert quoted["status"] == "已报价"
    item = service.add_repair_item(
        user(Role.staff),
        repair_id,
        RepairItemInput(item_name="主板维修", quantity=1, cost_amount=180, charge_amount=580),
    )
    assert item["repair_item_id"] > 0
    ready = service.update_repair_order_status(user(Role.staff), repair_id, RepairOrderStatusInput(status=OrderStatus.ready))
    assert ready["status"] == "待交付"
    delivered = service.deliver_repair_order(user(Role.staff), repair_id, RepairDeliverInput(delivery_check="功能正常"))
    assert delivered["status"] == "已交付"
    payment = service.create_payment(
        user(Role.finance),
        PaymentInput(source_type="repair", source_id=repair_id, direction=PaymentDirection.income, amount=580),
    )
    timeline = service.machine_timeline(user(Role.finance), payment["machine_id"])
    assert timeline["machine"]["current_status"] == "已结单"
    assert any(event["event_type"] == "payment" for event in timeline["events"])
    assert timeline["repair_items"][0]["charge_amount"] == 580


def test_repair_order_rejects_jump_and_closed_changes(service: MisService) -> None:
    order = service.create_repair_order(
        user(Role.staff),
        RepairOrderInput(machine=MachineInput(imei="862222222222223", model="iPhone 14"), fault_description="不开机"),
    )
    repair_id = order["repair_order_id"]

    with pytest.raises(BusinessError):
        service.deliver_repair_order(user(Role.staff), repair_id, RepairDeliverInput(delivery_check="跳步交付"))

    service.update_repair_order_status(user(Role.staff), repair_id, RepairOrderStatusInput(status=OrderStatus.diagnosing))
    service.quote_repair_order(user(Role.staff), repair_id, RepairQuoteInput(diagnosis="电池故障", quoted_amount=180))
    service.add_repair_item(user(Role.staff), repair_id, RepairItemInput(item_name="更换电池", charge_amount=180))
    service.update_repair_order_status(user(Role.staff), repair_id, RepairOrderStatusInput(status=OrderStatus.ready))
    service.deliver_repair_order(user(Role.staff), repair_id, RepairDeliverInput(delivery_check="功能正常"))
    service.create_payment(user(Role.finance), PaymentInput(source_type="repair", source_id=repair_id, direction=PaymentDirection.income, amount=180))

    with pytest.raises(BusinessError):
        service.add_repair_item(user(Role.staff), repair_id, RepairItemInput(item_name="重复维修"))


def test_cancelled_repair_order_cannot_deliver_or_receive_payment(service: MisService) -> None:
    order = service.create_repair_order(
        user(Role.staff),
        RepairOrderInput(machine=MachineInput(imei="862222222222224", model="iPhone 13"), fault_description="进水"),
    )
    repair_id = order["repair_order_id"]
    cancelled = service.update_repair_order_status(user(Role.staff), repair_id, RepairOrderStatusInput(status=OrderStatus.cancelled, remark="客户放弃维修"))
    assert cancelled["status"] == "已作废"

    with pytest.raises(BusinessError):
        service.deliver_repair_order(user(Role.staff), repair_id, RepairDeliverInput(delivery_check="不可交付"))
    with pytest.raises(BusinessError):
        service.create_payment(user(Role.finance), PaymentInput(source_type="repair", source_id=repair_id, direction=PaymentDirection.income, amount=100))


def test_recycle_inventory_sale_and_payment(service: MisService) -> None:
    recycle = service.create_recycle_order(
        user(Role.staff),
        RecycleOrderInput(
            machine=MachineInput(imei="863333333333333", model="iPhone 13 Pro"),
            customer=CustomerInput(name="回收客户"),
            inspection_note="外观轻微磕碰",
        ),
    )
    recycle_id = recycle["recycle_order_id"]
    service.quote_recycle_order(user(Role.staff), recycle_id, RecycleQuoteInput(inspection_result="功能正常", quoted_amount=3200))
    inventory = service.stock_in_recycle_order(user(), recycle_id, StockInInput(pay_amount=3200, sale_price=3880))
    assert inventory["status"] == "可销售"
    sale = service.create_sales_order(
        user(Role.staff),
        SalesOrderInput(
            inventory_item_id=inventory["inventory_item_id"],
            customer=CustomerInput(name="销售客户"),
            sale_price=3880,
            salesperson="小王",
        ),
    )
    assert sale["status"] == "已售出"
    payment = service.create_payment(
        user(Role.finance),
        PaymentInput(source_type="sale", source_id=sale["sales_order_id"], direction=PaymentDirection.income, amount=3880),
    )
    assert payment["machine_id"] == sale["machine_id"]
    report = service.machine_reports(user(Role.finance))
    assert report["inventory_count"] == 0
    assert any(row["direction"] == "收入" for row in report["payment_totals"])
