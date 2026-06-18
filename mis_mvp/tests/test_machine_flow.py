from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.db import connect, migrate
from backend.models import (
    CustomerInput,
    DeviceModelInput,
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
    RepairInspectionInput,
    RepairInspectionItemInput,
    RepairItemInput,
    RepairOrderInput,
    RepairOrderNoteDeleteInput,
    RepairOrderNoteInput,
    RepairOrderNoteUpdateInput,
    RepairRemarkInput,
    RepairOrderStatusInput,
    RepairQuoteConfirmInput,
    RepairQuoteInput,
    RepairFaultMaterialInput,
    RepairSkuInput,
    Role,
    SalesOrderInput,
    StockInInput,
    WarehouseAreaInput,
    WarehouseLocationInput,
    User,
)
from backend.service import BusinessError, MisService


def assert_order_no(value: str, prefix: str) -> None:
    assert re.fullmatch(rf"{prefix}\d{{8}}-\d{{4}}", value)


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


def test_parse_apple_iphone_model_support_page(service: MisService) -> None:
    html = """
    <html><body>
      <h2>iPhone 17 Pro</h2>
      <p>Year introduced: 2025</p>
      <p>Capacity: 256 GB, 512 GB, 1 TB</p>
      <p>Colors: Silver, Cosmic Orange, Deep Blue</p>
      <p>Model number: A3256, A3257</p>
      <h2>iPhone 16e</h2>
      <p>Year introduced: 2025</p>
      <p>Capacity: 128 GB, 256 GB, 512 GB</p>
      <p>Colors: Black, White</p>
    </body></html>
    """

    models = service._parse_apple_iphone_models(html)

    assert models == [
        {"model_name": "iPhone 17 Pro", "year": "2025", "capacities": ["256GB", "512GB", "1TB"], "colors": ["银色", "星宇橙色", "深蓝色"], "model_numbers": ["A3256", "A3257"], "product": "iPhone", "source_url": "https://support.apple.com/en-us/108044"},
        {"model_name": "iPhone 16e", "year": "2025", "capacities": ["128GB", "256GB", "512GB"], "colors": ["黑色", "白色"], "model_numbers": [], "product": "iPhone", "source_url": "https://support.apple.com/en-us/108044"},
    ]


def test_parse_apple_ipad_and_mac_model_support_pages(service: MisService) -> None:
    ipad_html = """
    <html><body>
      <h2>iPad Pro</h2>
      <h2>iPad Pro 13-inch (M5)</h2>
      <p>Year: 2025</p>
      <p>Capacity: 256 GB, 512 GB, 1 TB, 2 TB</p>
      <p>Model number: A1822</p>
      <h2>iPad Air 11-inch (M3)</h2>
      <p>Year: 2025</p>
      <p>Capacity: 128 GB, 256 GB, 512 GB, 1 TB</p>
    </body></html>
    """
    mac_html = """
    <html><body>
      <h2>List of MacBook models</h2>
      <h2>2017</h2>
      <p>MacBook (Retina, 12-inch, 2017)</p>
      <p>Model Identifier: MacBook10,1</p>
    </body></html>
    """

    ipads = service._parse_apple_mobile_models(ipad_html, ["iPad"], "iPad", "ipad-url")
    macs = service._parse_apple_mac_models(mac_html, ["MacBook"], "MacBook", "mac-url")

    assert [row["model_name"] for row in ipads] == ["iPad Pro 13-inch (M5)", "iPad Air 11-inch (M3)"]
    assert ipads[0]["capacities"] == ["256GB", "512GB", "1TB", "2TB"]
    assert ipads[0]["model_numbers"] == ["A1822"]
    assert macs == [{"model_name": "MacBook (Retina, 12-inch, 2017)", "year": "2017", "capacities": [], "colors": [], "model_numbers": ["MacBook10,1"], "product": "MacBook", "source_url": "mac-url"}]


def test_machine_unique_imei_and_temp_no(service: MisService) -> None:
    first = service.create_machine(user(), MachineInput(imei="861111111111111", model="iPhone 15"))
    assert first["imei"] == "861111111111111"
    temp = service.create_machine(user(), MachineInput(model="无 IMEI 机器"))
    assert temp["machine_no"].startswith("TMP-")
    with pytest.raises(BusinessError):
        service.create_machine(user(), MachineInput(imei="861111111111111", model="重复机器"))

def test_repair_workbench_includes_bill_export_fields(service: MisService) -> None:
    order = service.create_repair_order(
        user(Role.staff),
        RepairOrderInput(
            machine=MachineInput(imei="861111111111112", model="iPhone 15"),
            customer=CustomerInput(name="导出客户"),
            fault_description="待机短",
            repair_items=[
                RepairItemInput(item_name="更换电池", quantity=2, cost_amount=30, charge_amount=60),
                RepairItemInput(item_name="防水胶", quantity=1, cost_amount=5, charge_amount=15),
            ],
            inspections=[
                RepairInspectionInput(
                    stage="pre",
                    items=[
                        RepairInspectionItemInput(item="电池健康", abnormal=True),
                        RepairInspectionItemInput(item="屏幕显示", abnormal=False),
                    ],
                    note="循环次数高",
                )
            ],
        ),
    )
    repair_id = order["repair_order_id"]
    material = service.create_material(user(), MaterialInput(name="库存屏幕", avg_cost=120))
    service.conn.execute(
        """
        INSERT INTO repair_materials
        (repair_order_id, material_id, qty, unit_cost, total_cost, source_type)
        VALUES (?, ?, 1, 120, 120, '库存')
        """,
        (repair_id, material["material_id"]),
    )
    service.conn.execute(
        """
        INSERT INTO payments
        (source_type, source_id, direction, amount, method)
        VALUES ('repair', ?, '收入', 180, '微信')
        """,
        (repair_id,),
    )
    service.conn.commit()

    workbench = service.repair_workbench(user(Role.staff))
    exported = next(row for row in workbench["orders"] if row["repair_order_id"] == repair_id)
    assert exported["export_parts"] == "更换电池||防水胶||库存屏幕"
    assert exported["export_part_sources"] == "库存"
    assert exported["export_payment_method"] == "微信"
    assert exported["export_cost_amount"] == 185
    assert exported["export_profit_amount"] == 15
    assert exported["pool_fault_names"] == "更换电池||防水胶"
    assert exported["pool_pre_inspection_abnormal"] == "电池健康：循环次数高"


def test_device_model_master_data_upsert_search_and_enabled_filter(service: MisService) -> None:
    created = service.upsert_device_model(
        user(Role.staff),
        DeviceModelInput(
            brand="Apple",
            model_name="iPhone Test Pro",
            colors=["黑色", "白色"],
            capacities=["128GB", "256GB"],
            sort_order=1,
            remark="测试机型",
        ),
    )
    assert created["device_model_id"] > 0
    assert created["colors"] == ["黑色", "白色"]
    assert created["capacities"] == ["128GB", "256GB"]

    searched = service.list_device_models(user(Role.frontdesk), keyword="Test Pro")
    assert [row["device_model_id"] for row in searched] == [created["device_model_id"]]

    updated = service.upsert_device_model(
        user(Role.staff),
        DeviceModelInput(
            device_model_id=created["device_model_id"],
            brand="Apple",
            model_name="iPhone Test Pro",
            colors=["蓝色"],
            capacities=["512GB"],
            enabled=False,
            sort_order=2,
        ),
    )
    assert updated["colors"] == ["蓝色"]
    assert updated["capacities"] == ["512GB"]
    assert updated["enabled"] == 0
    enabled_rows = service.list_device_models(user(Role.frontdesk), enabled_only=True)
    assert all(row["device_model_id"] != created["device_model_id"] for row in enabled_rows)


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
    detail = service.repair_workbench_detail(user(Role.staff), repair_id)
    assert detail["order"]["status"] == "已报价"
    assert detail["order"]["quoted_amount"] == 760
    timeline = service.machine_timeline(user(Role.staff), order["machine_id"])
    assert timeline["repair_items"][0]["charge_amount"] == 580


def test_frontdesk_repair_order_creation_defaults_and_order_no(service: MisService) -> None:
    order = service.create_repair_order(
        user(Role.frontdesk),
        RepairOrderInput(
            machine=MachineInput(imei="862222222222225", model="iPhone 15 Pro"),
            customer=CustomerInput(name="开单客户", phone="13800000005"),
            fault_description="客户描述无法充电",
        ),
    )

    assert order["status"] == "已开单"
    assert order["workflow_status"] == "待指派工程师"
    assert order["assigned_to"] == ""
    assert_order_no(order["order_no"], "WX")

    timeline = service.machine_timeline(user(Role.frontdesk), order["machine_id"])
    assert timeline["machine"]["current_status"] == "检测中"
    assert timeline["machine"]["source_type"] == "维修"
    assert any(event["title"] == "维修开单" for event in timeline["events"])

    workbench = service.repair_workbench(user(Role.frontdesk))
    row = next(item for item in workbench["orders"] if item["repair_order_id"] == order["repair_order_id"])
    assert row["order_no"] == order["order_no"]


def test_repair_order_archive_hides_from_normal_views_and_exact_searches(service: MisService) -> None:
    order = service.create_repair_order(
        user(Role.frontdesk),
        RepairOrderInput(
            machine=MachineInput(imei="862222222222248", model="iPhone 15 Pro"),
            customer=CustomerInput(name="归档客户", phone="13800000048"),
            fault_description="误开订单",
            notes=[RepairOrderNoteInput(note_type="内部备注", content="归档前备注")],
            repair_items=[RepairItemInput(item_name="检测费", quantity=1, cost_amount=0, charge_amount=30)],
        ),
    )
    repair_id = order["repair_order_id"]
    order_no = order["order_no"]

    archived = service.delete_repair_order(user(Role.admin), repair_id, "重复录入")

    assert archived["archived"] is True
    assert repair_id not in {row["repair_order_id"] for row in service.repair_workbench(user(Role.frontdesk))["orders"]}
    assert service.machine_timeline(user(Role.frontdesk), order["machine_id"])["repair_orders"] == []
    assert service.repo.customer_detail(order["customer_id"])["repair_orders"] == []
    with pytest.raises(BusinessError, match="维修单不存在"):
        service.repair_workbench_detail(user(Role.frontdesk), repair_id)

    assert service.search_archived_repair_order(user(Role.frontdesk), order_no[:8]) == {}
    archive_detail = service.search_archived_repair_order(user(Role.frontdesk), order_no)
    assert archive_detail["readonly"] is True
    assert archive_detail["order"]["repair_order_id"] == repair_id
    assert archive_detail["order"]["archive"]["archive_reason"] == "重复录入"
    assert archive_detail["repair_items"][0]["item_name"] == "检测费"
    assert archive_detail["notes"][0]["content"] == "归档前备注"


def test_repair_order_archive_delete_permission_and_purge(service: MisService) -> None:
    order = service.create_repair_order(
        user(Role.frontdesk),
        RepairOrderInput(
            machine=MachineInput(imei="862222222222249", model="iPhone 15"),
            customer=CustomerInput(name="权限归档客户"),
            fault_description="误开订单",
        ),
    )
    repair_id = order["repair_order_id"]
    order_no = order["order_no"]

    for role in (Role.frontdesk, Role.engineer, Role.finance):
        with pytest.raises(PermissionError):
            service.delete_repair_order(user(role), repair_id, "无权限删除")

    service.delete_repair_order(user(Role.boss), repair_id, "老板确认删除")
    service.conn.execute(
        "UPDATE repair_order_archives SET purge_after=datetime(CURRENT_TIMESTAMP, '-1 day') WHERE repair_order_id=?",
        (repair_id,),
    )
    service.conn.execute(
        "UPDATE repair_orders SET purge_after=datetime(CURRENT_TIMESTAMP, '-1 day') WHERE repair_order_id=?",
        (repair_id,),
    )
    service.conn.commit()
    migrate(service.conn)

    assert service.search_archived_repair_order(user(Role.frontdesk), order_no) == {}
    assert service.repo.get_repair_order(repair_id, include_archived=True) is None


def test_engineer_can_create_repair_order_and_is_auto_assigned(service: MisService) -> None:
    order = service.create_repair_order(
        user(Role.engineer),
        RepairOrderInput(
            machine=MachineInput(imei="862222222222226", model="iPhone 14 Pro"),
            customer=CustomerInput(name="工程师开单客户"),
            fault_description="屏幕异常",
        ),
    )

    assert order["status"] == "已开单"
    assert order["workflow_status"] == "工程师待检测"
    assert order["assigned_to"] == "engineer"
    assert_order_no(order["order_no"], "WX")

    visible = service.search_machines(user(Role.engineer), "862222222222226")
    assert [row["machine_id"] for row in visible] == [order["machine_id"]]

    timeline = service.machine_timeline(user(Role.engineer), order["machine_id"])
    assert timeline["machine"]["assigned_to"] == "engineer"
    assert any(event["title"] == "指派工程师" for event in timeline["events"])


def test_repair_order_creation_can_reuse_customer_and_machine(service: MisService) -> None:
    machine = service.create_machine(
        user(Role.frontdesk),
        MachineInput(
            imei="862222222222227",
            model="iPhone 13",
            customer=CustomerInput(name="复用客户", phone="13800000007"),
        ),
    )
    customer_id = machine["customer_id"]

    order = service.create_repair_order(
        user(Role.frontdesk),
        RepairOrderInput(
            machine_id=machine["machine_id"],
            customer_id=customer_id,
            fault_description="复用机器开单",
        ),
    )

    assert order["machine_id"] == machine["machine_id"]
    assert order["customer_id"] == customer_id
    assert_order_no(order["order_no"], "WX")
    assert len(service.search_machines(user(Role.frontdesk), "862222222222227")) == 1


def test_rework_repair_order_uses_rework_order_no_prefix(service: MisService) -> None:
    order = service.create_repair_order(
        user(Role.frontdesk),
        RepairOrderInput(
            machine=MachineInput(imei="862222222222247", model="iPhone 15 Pro"),
            customer=CustomerInput(name="返修客户"),
            order_type="返修",
            fault_description="上次维修后返修检测",
        ),
    )

    assert_order_no(order["order_no"], "FX")
    assert order["service_type"] == "返修"


def test_repair_order_creation_validation_errors(service: MisService) -> None:
    machine = service.create_machine(user(Role.frontdesk), MachineInput(imei="862222222222228", model="iPhone 12"))

    with pytest.raises(BusinessError, match="必须提供机器档案或 machine_id"):
        service.create_repair_order(user(Role.frontdesk), RepairOrderInput(fault_description="缺少机器"))

    with pytest.raises(BusinessError, match="机器档案不存在"):
        service.create_repair_order(user(Role.frontdesk), RepairOrderInput(machine_id=9999))

    repeat = service.create_repair_order(
        user(Role.frontdesk),
        RepairOrderInput(machine=MachineInput(imei="862222222222228", model="iPhone 12"), fault_description="二次维修"),
    )
    assert repeat["machine_id"] == machine["machine_id"]


def test_repair_order_reuses_existing_machine_by_serial(service: MisService) -> None:
    machine = service.create_machine(user(Role.frontdesk), MachineInput(serial="SERIAL-REPAIR-001", model="iPhone 13"))

    repeat = service.create_repair_order(
        user(Role.frontdesk),
        RepairOrderInput(machine=MachineInput(serial="SERIAL-REPAIR-001", model="iPhone 13"), fault_description="序列号复修"),
    )

    assert repeat["machine_id"] == machine["machine_id"]


def test_repair_sku_model_filter_and_upsert(service: MisService) -> None:
    common = service.upsert_repair_sku(
        user(Role.staff),
        RepairSkuInput(sku_code="COMMON-DIAG", fault_name="通用检测", solution_name="基础检测", charge_amount=99),
    )
    specific = service.upsert_repair_sku(
        user(Role.staff),
        RepairSkuInput(model="iPhone 15 Pro", sku_code="IP15P-SCREEN", fault_name="屏幕损坏", solution_name="更换屏幕总成", cost_amount=500, charge_amount=880),
    )
    other = service.upsert_repair_sku(
        user(Role.staff),
        RepairSkuInput(model="iPhone 14", sku_code="IP14-BATTERY", fault_name="电池老化", solution_name="更换电池", charge_amount=220),
    )

    rows = service.list_repair_skus(user(Role.frontdesk), model="iPhone 15 Pro")
    ids = {row["sku_id"] for row in rows}
    assert common["sku_id"] in ids
    assert specific["sku_id"] in ids
    assert other["sku_id"] not in ids
    assert service.list_repair_skus(user(Role.frontdesk), keyword="屏幕")[0]["model"] == "iPhone 15 Pro"

    updated = service.upsert_repair_sku(
        user(Role.staff),
        RepairSkuInput(model="iPhone 15 Pro", sku_code="IP15P-SCREEN", fault_name="屏幕损坏", solution_name="更换原彩屏幕总成", cost_amount=520, charge_amount=920, enabled=False),
    )
    assert updated["sku_id"] == specific["sku_id"]
    assert updated["model"] == "iPhone 15 Pro"
    assert updated["enabled"] == 0


def test_create_repair_order_with_initial_repair_items(service: MisService) -> None:
    sku = service.upsert_repair_sku(
        user(Role.staff),
        RepairSkuInput(model="iPhone 13 Pro", sku_code="IP13P-SCR", fault_name="屏幕总成更换", solution_name="更换屏幕总成", cost_amount=680, charge_amount=980),
    )

    order = service.create_repair_order(
        user(Role.frontdesk),
        RepairOrderInput(
            machine=MachineInput(imei="862222222222229", model="iPhone 13 Pro"),
            customer=CustomerInput(name="带明细客户"),
            fault_description="屏幕损坏",
            repair_items=[RepairItemInput(sku_id=sku["sku_id"], item_name=sku["solution_name"], quantity=2)],
        ),
    )

    assert order["status"] == "已开单"
    assert order["quoted_amount"] == 3320
    assert len(order["items"]) == 1
    assert order["items"][0]["sku_code"] == "IP13P-SCR"
    assert order["items"][0]["cost_amount"] == 680
    assert order["items"][0]["charge_amount"] == 980
    timeline = service.machine_timeline(user(Role.frontdesk), order["machine_id"])
    assert any(event["title"] == "维修项目" for event in timeline["events"])


def test_create_repair_order_with_manual_item_auto_creates_sku(service: MisService) -> None:
    order = service.create_repair_order(
        user(Role.frontdesk),
        RepairOrderInput(
            machine=MachineInput(imei="862222222222233", model="iPhone 15 Pro"),
            customer=CustomerInput(name="手动故障客户"),
            fault_description="主板异常",
            repair_items=[RepairItemInput(item_name="主板维修", quantity=1, cost_amount=330, charge_amount=177)],
        ),
    )

    item = order["items"][0]
    assert item["item_name"] == "主板维修"
    assert item["sku_id"]
    assert item["sku_code"].startswith("AUTO-")
    assert item["fault_name"] == "主板维修"
    assert order["quoted_amount"] == 507

    rows = service.list_repair_skus(user(Role.frontdesk), model="iPhone 15 Pro", keyword="主板维修")
    assert any(row["sku_id"] == item["sku_id"] for row in rows)


def test_create_repair_order_keeps_explicit_zero_service_fee(service: MisService) -> None:
    sku = service.upsert_repair_sku(
        user(Role.staff),
        RepairSkuInput(model="iPhone 16 Pro", sku_code="IP16P-BAT", fault_name="电池老化", solution_name="更换电池", cost_amount=80, charge_amount=260),
    )

    order = service.create_repair_order(
        user(Role.frontdesk),
        RepairOrderInput(
            machine=MachineInput(imei="862222222222232", model="iPhone 16 Pro"),
            customer=CustomerInput(name="零工时客户"),
            fault_description="电池老化",
            repair_items=[RepairItemInput(sku_id=sku["sku_id"], item_name="电池老化", quantity=1, cost_amount=80, charge_amount=0)],
        ),
    )

    assert order["quoted_amount"] == 80
    assert order["items"][0]["cost_amount"] == 80
    assert order["items"][0]["charge_amount"] == 0


def test_create_repair_order_with_initial_inspection(service: MisService) -> None:
    order = service.create_repair_order(
        user(Role.frontdesk),
        RepairOrderInput(
            machine=MachineInput(imei="862222222222231", model="iPhone 16 Pro"),
            customer=CustomerInput(name="带检测客户"),
            fault_description="屏幕触摸异常",
            inspections=[
                RepairInspectionInput(
                    stage="pre",
                    items=[
                        RepairInspectionItemInput(item="屏幕显示", abnormal=True),
                        RepairInspectionItemInput(item="触摸功能", abnormal=True),
                        RepairInspectionItemInput(item="摄像头", abnormal=False),
                    ],
                    note="入库前检测",
                )
            ],
        ),
    )

    detail = service.repair_workbench_detail(user(Role.frontdesk), order["repair_order_id"])
    inspections = detail["inspections"]
    assert any(row["stage"] == "pre" and row["item"] == "屏幕显示" and row["abnormal"] == 1 for row in inspections)
    assert any(row["stage"] == "pre" and row["note"] == "入库前检测" for row in inspections)
    assert any(event["title"] == "更新维修前检测" for event in detail["events"])


def test_append_repair_order_remark_preserves_existing_remark(service: MisService) -> None:
    order = service.create_repair_order(
        user(Role.frontdesk),
        RepairOrderInput(
            machine=MachineInput(imei="862222222222233", model="iPhone 16"),
            customer=CustomerInput(name="备注客户"),
            remark="【内部备注】原备注",
            notes=[RepairOrderNoteInput(note_type="内部备注", content="原备注")],
        ),
    )

    updated = service.append_repair_order_remark(
        user(Role.frontdesk),
        order["repair_order_id"],
        RepairRemarkInput(remark="【交付说明】新备注"),
    )

    assert "【内部备注】原备注" in updated["remark"]
    assert "【交付说明】新备注" in updated["remark"]
    assert len(updated["notes"]) == 2
    assert updated["notes"][0]["created_by"] == "frontdesk"
    assert any(event["title"] == "新增工单备注" for event in updated["events"])

    note_id = updated["notes"][0]["note_id"]
    edited = service.update_repair_order_note(
        user(Role.frontdesk),
        order["repair_order_id"],
        note_id,
        RepairOrderNoteUpdateInput(note_type="内部备注", content="修改后备注"),
    )
    assert any(note["content"] == "修改后备注" and note["updated_by"] == "frontdesk" for note in edited["notes"])
    assert any(event["title"] == "修改工单备注" for event in edited["events"])

    deleted = service.delete_repair_order_note(
        user(Role.frontdesk),
        order["repair_order_id"],
        note_id,
        RepairOrderNoteDeleteInput(reason="误填"),
    )
    assert all(note["note_id"] != note_id for note in deleted["notes"])
    assert any(event["title"] == "删除工单备注" and "误填" in event["detail"] for event in deleted["events"])


def test_create_repair_order_rejects_bad_initial_repair_item_without_order(service: MisService) -> None:
    with pytest.raises(BusinessError, match="维修 SKU 不存在或已停用"):
        service.create_repair_order(
            user(Role.frontdesk),
            RepairOrderInput(
                machine=MachineInput(imei="862222222222230", model="iPhone 13 Pro"),
                customer=CustomerInput(name="坏明细客户"),
                repair_items=[RepairItemInput(sku_id=999999, item_name="不存在故障")],
            ),
        )

    assert service.repair_workbench(user(Role.frontdesk))["orders"] == []
    assert service.search_machines(user(Role.frontdesk), "862222222222230") == []


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
    detail = service.repair_workbench_detail(user(Role.frontdesk), repair_id)
    assert detail["order"]["status"] == "处理中"
    assert detail["order"]["quoted_amount"] == sku["cost_amount"] + sku["charge_amount"]
    timeline = service.machine_timeline(user(Role.frontdesk), order["machine_id"])
    assert any(event["title"] == "指派工程师" for event in timeline["events"])
    assert any(event["title"] == "报价确认" for event in timeline["events"])
    assert any(event["title"] == "维修项目" for event in timeline["events"])


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
    service.update_repair_order_status(user(Role.staff), repair_id, RepairOrderStatusInput(status=OrderStatus.cancelled, remark="客户取消"))

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
    assert_order_no(recycle["order_no"], "ZB")
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
