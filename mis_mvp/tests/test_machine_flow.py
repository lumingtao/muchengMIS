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
    MaterialBatchInput,
    MaterialBatchReturnInput,
    MaterialCategoryInput,
    MaterialInput,
    MaterialIssueReturnInput,
    MaterialRequestActionInput,
    MaterialRequestInput,
    MaterialRequestItemInput,
    MaterialReturnInspectInput,
    OrderStatus,
    PaymentDirection,
    PaymentInput,
    RecycleOrderInput,
    RecycleQuoteInput,
    RepairAssignInput,
    RepairDeliverInput,
    RepairEngineerCloseInput,
    RepairItemInput,
    RepairOrderInput,
    RepairOrderStatusInput,
    RepairQuoteConfirmInput,
    RepairQuoteInput,
    RepairFaultMaterialInput,
    Role,
    SalesOrderInput,
    StockInInput,
    WarehouseAreaInput,
    WarehouseLocationInput,
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


def warehouse_seed(service: MisService) -> tuple[dict, dict, dict, dict]:
    area = service.create_warehouse_area(user(), WarehouseAreaInput(area_code="MAIN", name="主库区"))
    location = service.create_warehouse_location(user(), WarehouseLocationInput(area_id=area["area_id"], location_code="MAIN-A01", name="主库 A01"))
    category = service.create_material_category(user(), MaterialCategoryInput(category_code="SSD", name="硬盘"))
    material = service.create_material(
        user(),
        MaterialInput(
            category_id=category["category_id"],
            default_location_id=location["location_id"],
            name="iPhone 通用 512G 硬盘",
            compatible_range="IPH12-15",
            spec="512G",
            min_qty=1,
            avg_cost=375,
        ),
    )
    return area, location, category, material


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


def test_frontdesk_engineer_repair_handoff_and_visibility(service: MisService) -> None:
    order = service.create_repair_order(
        user(Role.frontdesk),
        RepairOrderInput(
            machine=MachineInput(imei="862222222222221", model="iPhone 15"),
            customer=CustomerInput(name="协作客户", phone="13800000001"),
            fault_description="屏幕碎裂",
        ),
    )
    repair_id = order["repair_order_id"]

    with pytest.raises(PermissionError):
        service.machine_timeline(user(Role.engineer), order["machine_id"])

    assigned = service.assign_repair_order(
        user(Role.frontdesk),
        repair_id,
        RepairAssignInput(engineer_user_id="engineer", remark="优先处理"),
    )
    assert assigned["assigned_to"] == "engineer"
    assert assigned["workflow_status"] == "工程师待检测"

    visible = service.search_machines(user(Role.engineer), "862222222222221")
    assert [row["machine_id"] for row in visible] == [order["machine_id"]]

    service.update_repair_order_status(user(Role.engineer), repair_id, RepairOrderStatusInput(status=OrderStatus.diagnosing))
    sku = service.list_repair_skus(user(Role.engineer))[0]
    quoted = service.quote_repair_order(
        user(Role.engineer),
        repair_id,
        RepairQuoteInput(
            diagnosis="外屏碎裂",
            fault_detail="屏幕显示正常，玻璃碎裂",
            repair_solution="更换屏幕总成",
            sku_ids=[sku["sku_id"]],
        ),
    )
    assert quoted["status"] == "已报价"
    assert quoted["quoted_amount"] == sku["charge_amount"]
    assert quoted["workflow_status"] == "待客户确认"

    confirmed = service.confirm_repair_quote(
        user(Role.frontdesk),
        repair_id,
        RepairQuoteConfirmInput(confirm_result="客户同意维修", confirm_method="微信", contact_person="协作客户"),
    )
    assert confirmed["status"] == "处理中"
    assert confirmed["workflow_status"] == "工程师维修中"

    service.add_repair_item(
        user(Role.engineer),
        repair_id,
        RepairItemInput(
            sku_id=sku["sku_id"],
            item_name=sku["solution_name"],
            quantity=1,
            cost_amount=sku["cost_amount"],
            charge_amount=sku["charge_amount"],
        ),
    )
    closed = service.engineer_close_repair_order(user(Role.engineer), repair_id, RepairEngineerCloseInput(remark="维修完成"))
    assert closed["workflow_status"] == "待前台收费/交付"
    assert closed["status"] == "待交付"

    delivered = service.deliver_repair_order(user(Role.frontdesk), repair_id, RepairDeliverInput(delivery_check="前台交付检测正常"))
    assert delivered["status"] == "已交付"
    payment = service.create_payment(
        user(Role.frontdesk),
        PaymentInput(source_type="repair", source_id=repair_id, direction=PaymentDirection.income, amount=sku["charge_amount"]),
    )
    timeline = service.machine_timeline(user(Role.frontdesk), payment["machine_id"])
    assert timeline["machine"]["current_status"] == "已结单"
    assert any(event["title"] == "指派工程师" for event in timeline["events"])
    assert any(event["title"] == "报价确认" for event in timeline["events"])
    assert any(event["title"] == "工程师结单" for event in timeline["events"])


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


def test_material_batch_creates_units_and_purchase_return(service: MisService) -> None:
    _, location, _, material = warehouse_seed(service)
    batch = service.create_material_batch(
        user(),
        MaterialBatchInput(
            material_id=material["material_id"],
            location_id=location["location_id"],
            qty=3,
            unit_cost=375,
            supplier="真实供应商待确认",
        ),
        "purchase",
    )
    units = service.material_units(user())
    assert len([row for row in units if row["batch_id"] == batch["batch_id"]]) == 3
    assert service.warehouse_overview(user())["materials"][0]["current_qty"] == 3

    first_unit = next(row for row in units if row["batch_id"] == batch["batch_id"])
    service.return_material_batch(
        user(),
        batch["batch_id"],
        MaterialBatchReturnInput(unit_ids=[first_unit["unit_id"]], refund_status="待确认"),
    )
    overview = service.warehouse_overview(user())
    returned = next(row for row in overview["units"] if row["unit_id"] == first_unit["unit_id"])
    assert returned["current_status"] == "已退货"
    assert next(row for row in overview["materials"] if row["material_id"] == material["material_id"])["current_qty"] == 2
    assert any(row["movement_type"] == "采购退货" for row in overview["movements"])


def test_material_request_issue_return_and_cancel_guard(service: MisService) -> None:
    _, location, _, material = warehouse_seed(service)
    service.create_material_batch(
        user(),
        MaterialBatchInput(material_id=material["material_id"], location_id=location["location_id"], qty=2, unit_cost=375),
        "purchase",
    )
    order = service.create_repair_order(
        user(Role.staff),
        RepairOrderInput(machine=MachineInput(imei="868888888888001", model="iPhone 15 Pro"), fault_description="不开机"),
    )
    request = service.create_material_request(
        user(Role.engineer),
        MaterialRequestInput(
            repair_order_id=order["repair_order_id"],
            engineer_user="engineer",
            items=[MaterialRequestItemInput(material_id=material["material_id"], qty=1)],
        ),
    )
    assert next(row for row in service.warehouse_overview(user())["materials"] if row["material_id"] == material["material_id"])["current_qty"] == 2
    service.approve_material_request(user(), request["request_id"], MaterialRequestActionInput())
    assert next(row for row in service.warehouse_overview(user())["materials"] if row["material_id"] == material["material_id"])["current_qty"] == 2

    issued = service.issue_material_request(user(), request["request_id"], MaterialRequestActionInput())
    unit_id = issued["units"][0]["unit_id"]
    assert next(row for row in service.warehouse_overview(user())["materials"] if row["material_id"] == material["material_id"])["current_qty"] == 1
    with pytest.raises(BusinessError):
        service.update_repair_order_status(user(Role.staff), order["repair_order_id"], RepairOrderStatusInput(status=OrderStatus.cancelled))

    ret = service.request_material_return(user(Role.engineer), unit_id, MaterialIssueReturnInput(remark="工单取消前退料"))
    service.inspect_material_return(user(), ret["return_id"], MaterialReturnInspectInput(inspect_result="可复用"))
    overview = service.warehouse_overview(user())
    assert next(row for row in overview["materials"] if row["material_id"] == material["material_id"])["current_qty"] == 2
    assert next(row for row in overview["units"] if row["unit_id"] == unit_id)["current_status"] == "在库可用"


def test_repair_fault_material_hints_and_engineer_mine(service: MisService) -> None:
    _, location, _, material = warehouse_seed(service)
    service.create_material_batch(
        user(),
        MaterialBatchInput(material_id=material["material_id"], location_id=location["location_id"], qty=1, unit_cost=375),
        "purchase",
    )
    sku = service.list_repair_skus(user())[0]
    service.upsert_repair_fault_material(
        user(),
        RepairFaultMaterialInput(repair_sku_id=sku["sku_id"], material_id=material["material_id"], qty=1, priority=1),
    )
    hint = service.material_hints_for_sku(user(Role.engineer), sku["sku_id"])
    assert hint["materials"][0]["current_qty"] == 1
    assert hint["materials"][0]["stock_warning"] == ""

    request = service.create_material_request(
        user(Role.engineer),
        MaterialRequestInput(engineer_user="engineer", items=[MaterialRequestItemInput(material_id=material["material_id"], qty=1)]),
    )
    mine = service.material_requests(user(Role.engineer), mine=True)
    assert [row["request_id"] for row in mine] == [request["request_id"]]
