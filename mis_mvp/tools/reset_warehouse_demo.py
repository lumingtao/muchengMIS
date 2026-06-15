from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.db import connect, migrate
from backend.models import MaterialBatchInput, MaterialCategoryInput, MaterialInput, WarehouseAreaInput, WarehouseLocationInput
from backend.service import MisService


WAREHOUSE_TABLES = [
    "repair_fault_materials",
    "stock_adjustments",
    "stock_count_items",
    "stock_counts",
    "stock_movements",
    "material_returns",
    "material_request_items",
    "material_requests",
    "material_units",
    "material_batches",
    "materials",
    "warehouse_locations",
    "warehouse_areas",
    "material_categories",
]


def reset_warehouse(service: MisService) -> None:
    conn = service.conn
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DELETE FROM repair_materials")
    conn.execute("DELETE FROM repair_cost_items WHERE item_type IN ('库存物料', '退料冲减') OR source_key LIKE 'material_unit:%' OR source_key LIKE 'material_return:%'")
    for table in WAREHOUSE_TABLES:
        conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def seed_warehouse(service: MisService) -> None:
    admin = service.get_user("admin")
    categories = [
        ("SCREEN", "屏幕总成", "OLED、LCD、外屏和触摸总成"),
        ("BATTERY", "电池", "原厂、品牌和高容电池"),
        ("FLEX", "排线小件", "尾插、听筒、音量、电源、闪光灯排线"),
        ("CAMERA", "摄像头", "前后摄和 Face ID 相关小件"),
        ("STORAGE", "硬盘存储", "NAND、硬盘扩容和主板存储类"),
        ("TOOLS", "辅料耗材", "胶、防水胶、螺丝、焊油等耗材"),
    ]
    category_ids: dict[str, int] = {}
    for code, name, remark in categories:
        row = service.create_material_category(admin, MaterialCategoryInput(category_code=code, name=name, remark=remark))
        category_ids[code] = int(row["category_id"])

    area_main = service.create_warehouse_area(admin, WarehouseAreaInput(area_code="MAIN", name="维修主仓", remark="常用维修配件"))
    area_temp = service.create_warehouse_area(admin, WarehouseAreaInput(area_code="TEMP", name="临采暂存", remark="当天临采和待确认配件"))
    locations = [
        ("A-01", "屏幕柜 A1", area_main["area_id"]),
        ("A-02", "电池柜 A2", area_main["area_id"]),
        ("B-01", "小件抽屉 B1", area_main["area_id"]),
        ("B-02", "主板存储 B2", area_main["area_id"]),
        ("T-01", "临采待检 T1", area_temp["area_id"]),
    ]
    location_ids: dict[str, int] = {}
    for code, name, area_id in locations:
        row = service.create_warehouse_location(admin, WarehouseLocationInput(area_id=int(area_id), location_code=code, name=name))
        location_ids[code] = int(row["location_id"])

    materials = [
        ("SCR-IP13-OLED", "iPhone 13 OLED 屏幕总成", "Apple", "OLED 黑色", "iPhone 13", "SCREEN", "A-01", 2, 315, 5),
        ("SCR-IP14P-OLED", "iPhone 14 Pro OLED 屏幕总成", "Apple", "OLED 灵动岛", "iPhone 14 Pro", "SCREEN", "A-01", 1, 580, 2),
        ("BAT-IP12-HC", "iPhone 12 高容电池", "闪电蜂", "高容量", "iPhone 12/12 Pro", "BATTERY", "A-02", 3, 78, 8),
        ("BAT-IP13-HC", "iPhone 13 高容电池", "闪电蜂", "高容量", "iPhone 13", "BATTERY", "A-02", 3, 86, 4),
        ("FLEX-IP13-CHG", "iPhone 13 尾插排线", "国产优品", "黑色", "iPhone 13", "FLEX", "B-01", 2, 42, 6),
        ("CAM-IP14-REAR", "iPhone 14 后置摄像头", "拆机", "后摄总成", "iPhone 14", "CAMERA", "B-01", 1, 210, 2),
        ("NAND-512-12-15", "512GB 硬盘/存储颗粒", "原厂拆机", "512GB", "iPhone 12-15 系列", "STORAGE", "B-02", 1, 375, 3),
        ("TOOLS-SEAL-IP", "iPhone 防水胶", "通用", "整套", "iPhone 11-16 系列", "TOOLS", "B-01", 10, 5, 20),
    ]
    for sku, name, brand, spec, compatible, category_code, location_code, min_qty, unit_cost, qty in materials:
        material = MaterialInput(
            sku=sku,
            material_code=sku,
            category_id=category_ids[category_code],
            default_location_id=location_ids[location_code],
            name=name,
            brand=brand,
            spec=spec,
            compatible_range=compatible,
            min_qty=min_qty,
            avg_cost=unit_cost,
            remark="仓库演示数据",
        )
        created = service.create_material(admin, material)
        service.create_material_batch(
            admin,
            MaterialBatchInput(
                material_id=int(created["material_id"]),
                supplier="默认供应商",
                purchase_no=f"PO-DEMO-{sku}",
                location_id=location_ids[location_code],
                qty=qty,
                unit_cost=unit_cost,
                payment_status="已付款",
                remark="仓库重建演示批次",
            ),
            "purchase",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="清空并重建维修物料仓演示数据")
    parser.add_argument("--database", default=str(settings.database_path), help="SQLite 数据库路径")
    parser.add_argument("--yes", action="store_true", help="确认执行清空重建")
    args = parser.parse_args()
    if not args.yes:
        raise SystemExit("该脚本会清空维修物料仓数据。确认执行请加 --yes")
    conn = connect(args.database)
    try:
        migrate(conn)
        service = MisService(conn)
        reset_warehouse(service)
        seed_warehouse(service)
    finally:
        conn.close()
    print(f"已重建维修物料仓演示数据：{args.database}")


if __name__ == "__main__":
    main()
