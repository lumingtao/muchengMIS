"""
Comprehensive test data generator for Muchen MIS.
Generates: materials, batches, units, repair SKUs, repair orders with
different statuses/time-points, notes, material reservations.
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import connect, migrate
from backend.config import settings


# ── Configuration ──────────────────────────────────────────────

NOW = datetime.now()

MODELS = [
    "iPhone 16 Pro Max", "iPhone 16 Pro", "iPhone 16",
    "iPhone 15 Pro Max", "iPhone 15 Pro", "iPhone 15",
    "iPhone 14 Pro Max", "iPhone 14 Pro", "iPhone 14",
    "iPhone 13 Pro", "iPhone 13",
    "Huawei Mate 70 Pro", "Huawei Pura 80 Ultra",
    "Samsung Galaxy S25 Ultra", "Samsung Galaxy S25+",
    "Xiaomi 15 Pro", "OPPO Find X8 Pro",
    "Huawei Mate 60 Pro",
]
COLORS = ["黑色", "白色", "蓝色", "原色钛金属", "金色", "紫色", "深空黑", "星光色", "苍岭绿"]
MEMORY = ["128G", "256G", "512G", "1T"]
CONDITIONS = ["外观优秀", "轻微磕碰", "屏幕划痕", "后盖破损", "主板故障", "无法开机", "进水", "弯曲变形"]

CUSTOMER_NAMES = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十",
                   "同行客户A", "数码店B", "企业客户C", "老客户D"]
STAFF = ["小陈", "小李", "小周", "刘工", "赵工"]
ENGINEERS = ["小陈", "小李", "刘工"]

FAULTS = [
    "不开机", "屏幕碎裂不显示", "电池不耐用半天就没电", "进水不开机",
    "摄像头打不开黑屏", "面容 ID 失灵无法解锁", "扬声器无声", "充电口松动充不进",
    "信号差经常无服务", "WiFi 灰色打不开", "无限重启进不去系统", "白苹果卡进度条",
    "触屏上半部分失灵", "听筒声音非常小", "闪光灯不亮", "刷机解锁",
    "主板短路烧了", "尾插排线损坏", "中框摔变形了", "后玻璃完全碎裂",
]

DIAGNOSES = [
    "主板电源管理芯片故障需更换", "屏幕总成损坏需更换原厂屏",
    "电池健康度仅 72% 需更换", "进水导致主板多处腐蚀",
    "后置摄像头模组损坏需更换", "面容组件排线断裂",
    "扬声器音圈烧毁需更换", "尾插排线断裂需更换小板",
    "射频功放芯片故障", "WiFi/蓝牙芯片虚焊需重植",
    "CPU 虚焊需重新植球", "存储芯片有坏块需更换",
    "触屏控制 IC 损坏", "听筒排线接触不良",
    "闪光灯驱动 IC 故障", "系统文件损坏需保资料刷机",
    "主板层间短路需分层维修", "尾插小板 USB 控制器损坏",
    "中框变形严重需校正", "后盖总成更换+重新做防水",
]

INSPECTION_ITEMS = [
    "屏幕显示", "触摸功能", "前置摄像头", "后置摄像头",
    "电池健康", "生物识别", "无线网络", "蜂窝网络",
    "音频模块", "指南针", "扬声器", "听筒",
    "充电", "不开机", "软件系统", "重装调试", "其他异常",
]

NOTES = [
    ("内部备注", "客户要求保留原彩显示，务必写回原屏数据"),
    ("内部备注", "客户急用，加急处理，明天来取"),
    ("内部备注", "此机之前在外面的店修过，小心焊点"),
    ("内部备注", "数据重要！先备份再操作"),
    ("交付说明", "告知客户外壳磕碰处无法复原，仅保证功能完好"),
    ("交付说明", "附赠钢化膜一张+透明壳一个"),
    ("内部备注", "配件需从华强北调货，预计 2-3 天"),
    ("内部备注", "客户点名要原厂配件，不用副厂"),
    ("交付说明", "本单免收人工费（老客户优惠）"),
    ("内部备注", "疑似人为损坏，需进一步确认才能走保修"),
    ("内部备注", "客户周六上午 10 点来取"),
    ("交付说明", "维修后质保延长至 6 个月"),
    ("内部备注", "屏幕发黄，客户表示能接受"),
    ("内部备注", "进液严重，可能还有其他暗病"),
    ("交付说明", "旧件已归还客户"),
]

# Material definitions
MATERIALS = [
    ("SCR-IP16PM", "iPhone 16 Pro Max 屏幕总成", "屏幕", 680, "张"),
    ("SCR-IP16", "iPhone 16 屏幕总成", "屏幕", 420, "张"),
    ("SCR-IP15PM", "iPhone 15 Pro Max 屏幕总成", "屏幕", 520, "张"),
    ("SCR-IP15", "iPhone 15 屏幕总成", "屏幕", 320, "张"),
    ("SCR-IP14", "iPhone 14 屏幕总成", "屏幕", 280, "张"),
    ("BAT-IP-STD", "iPhone 标准电池", "电池", 85, "个"),
    ("BAT-IP16", "iPhone 16 系列电池", "电池", 120, "个"),
    ("CAM-FRONT", "iPhone 前置摄像头模组", "摄像头", 95, "个"),
    ("CAM-REAR", "iPhone 后置摄像头模组", "摄像头", 220, "个"),
    ("FPC-TAIL", "iPhone 尾插排线小板", "排线", 45, "个"),
    ("FPC-CHARGER", "Type-C 充电尾插", "排线", 25, "个"),
    ("FACEID", "面容 ID 组件总成", "面容", 160, "个"),
    ("SPEAKER", "扬声器组件", "音频", 35, "个"),
    ("EARPIECE", "听筒组件", "音频", 30, "个"),
    ("WIFI-CHIP", "WiFi/蓝牙芯片", "芯片", 55, "个"),
    ("PMIC", "电源管理 IC", "芯片", 40, "个"),
    ("SCR-HW", "华为旗舰屏幕总成", "屏幕", 420, "张"),
    ("SCR-SS", "三星旗舰屏幕总成", "屏幕", 500, "张"),
    ("BACK-GLASS", "iPhone 后盖玻璃", "外壳", 65, "个"),
    ("FRAME", "iPhone 中框总成", "外壳", 180, "个"),
    ("TAPTIC", "iPhone 线性马达", "其他", 42, "个"),
    ("THERMAL", "散热铜箔/导热垫", "辅料", 8, "张"),
    ("ADHESIVE", "防水胶/屏幕胶", "辅料", 5, "条"),
    ("FLASH-LED", "闪光灯排线", "排线", 18, "个"),
]

# Repair SKU definitions: (code, fault_name, solution, cost, charge, model_hint)
SKUS = [
    ("SKU-SCR", "屏幕损坏", "更换屏幕总成", 520, 780, "iPhone 通用"),
    ("SKU-BAT", "电池老化", "更换电池", 85, 180, ""),
    ("SKU-PWR", "不开机/主板", "主板电源维修", 180, 450, ""),
    ("SKU-WATER", "进水腐蚀", "主板清洗+维修", 250, 600, ""),
    ("SKU-CAM", "摄像头故障", "更换后置摄像头", 220, 420, ""),
    ("SKU-FACE", "面容失灵", "更换面容组件", 160, 350, ""),
    ("SKU-SPK", "扬声器故障", "更换扬声器", 35, 120, ""),
    ("SKU-TAIL", "尾插/充电故障", "更换尾插排线", 70, 200, ""),
    ("SKU-WIFI", "WiFi/蓝牙故障", "重植 WiFi 芯片", 180, 400, ""),
    ("SKU-GLASS", "后盖碎裂", "更换后盖玻璃", 120, 300, ""),
    ("SKU-FRAME", "中框变形", "中框维修+校正", 280, 550, ""),
    ("SKU-WHITE", "白苹果/无限重启", "刷机+硬盘维修", 200, 500, ""),
    ("SKU-TOUCH", "触屏失灵", "更换触屏 IC", 150, 380, ""),
    ("SKU-EAR", "听筒故障", "更换听筒排线", 55, 150, ""),
    ("SKU-SIG", "信号差/无服务", "更换射频天线组件", 120, 300, ""),
]

# SKU -> material bindings (index into MATERIALS)
SKU_MATERIAL_MAP = [
    [0, 2, 3],          # 屏幕: multiple screen options
    [5, 6],             # 电池
    [15],               # 不开机
    [21, 22],           # 进水: 散热+防水胶
    [8, 9],             # 摄像头
    [11],               # 面容
    [12],               # 扬声器
    [9, 10],            # 尾插
    [14],               # WiFi
    [18],               # 后盖
    [19],               # 中框
    [15],               # 白苹果
    [23],               # 触屏
    [13],               # 听筒
]

STATUS_DIST = [
    ("维修中", 25),
    ("待支付", 15),
    ("已完结", 20),
    ("已交付", 10),
    ("已取消", 5),
    ("维修完成", 10),
    ("待报价确认", 10),
    ("财务待确认", 5),
]


# ── Helpers ─────────────────────────────────────────────────────

def rtime(days_back: int) -> str:
    """Random datetime within `days_back` days ago."""
    secs = random.randint(0, days_back * 86400)
    return (NOW - timedelta(seconds=secs)).strftime("%Y-%m-%d %H:%M:%S")


def rtime_between(low_days: int, high_days: int) -> str:
    """Random datetime between low_days and high_days ago."""
    secs = random.randint(low_days * 86400, high_days * 86400)
    return (NOW - timedelta(seconds=secs)).strftime("%Y-%m-%d %H:%M:%S")


# ── Main ────────────────────────────────────────────────────────

def seed(order_count: int = 100):
    random.seed(20260618)
    conn = connect(settings.database_path)
    migrate(conn)

    print("=" * 60)
    print("  沐辰 MIS 综合测试数据生成器")
    print("=" * 60)

    # ── 1. Users ─────────────────────────────────────────────────
    print("\n[1/7] 创建用户...")
    users = ["admin", "staff", "finance"]
    roles = ["admin", "staff", "finance"]
    for u, r in zip(users, roles):
        conn.execute("INSERT OR IGNORE INTO users (username, role) VALUES (?, ?)", (u, r))
    print(f"  OK {len(users)} 个用户")

    # ── 2. Warehouse infrastructure ──────────────────────────────
    print("[2/7] 创建仓库基础资料...")
    conn.execute(
        "INSERT INTO material_categories (category_code, name, remark) VALUES (?, ?, ?)",
        ("WX-PJ", "维修配件", "测试"),
    )
    cat_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        "INSERT INTO warehouse_areas (area_code, name, remark) VALUES (?, ?, ?)",
        ("A01", "维修仓-A区", "测试库区"),
    )
    area_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        "INSERT INTO warehouse_locations (area_id, location_code, name, remark) VALUES (?, ?, ?, ?)",
        (area_id, "A01-01", "A01-01 配件架", ""),
    )
    loc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"  OK cat={cat_id} area={area_id} loc={loc_id}")

    # ── 3. Materials + Batches + Units ───────────────────────────
    print("[3/7] 创建物料 + 入库批次 + 单件码...")
    mat_ids = {}
    total_units = 0
    for sku, name, cat_hint, cost, unit in MATERIALS:
        stock_qty = random.randint(20, 80)
        conn.execute(
            """INSERT INTO materials
            (sku, material_code, name, category_id, default_location_id,
             min_qty, current_qty, avg_cost, unit, brand, spec, status, track_unit)
            VALUES (?, ?, ?, ?, ?, 5, ?, ?, ?, '原厂', '', '在库', 1)""",
            (sku, sku, name, cat_id, loc_id, stock_qty, cost, unit),
        )
        mid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        mat_ids[sku] = mid

        # Batch
        conn.execute(
            "INSERT INTO material_batches (material_id, batch_no, batch_type, qty, unit_cost, remaining_qty, supplier, remark) VALUES (?,?,?,?,?,?,?,?)",
            (mid, f"B-{sku}", "采购入库", stock_qty, cost, stock_qty, "华强电子城", "测试"),
        )
        batch_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Units
        for i in range(stock_qty):
            conn.execute(
                "INSERT INTO material_units (material_id, batch_id, unit_code, current_status, location_id) VALUES (?,?,?,?,?)",
                (mid, batch_id, f"{sku}-{i+1:03d}", "在库可用", loc_id),
            )
            total_units += 1

    conn.commit()
    print(f"  OK 物料 {len(mat_ids)} 个, 库存 {total_units} 件")

    # ── 4. Repair SKUs ───────────────────────────────────────────
    print("[4/7] 创建故障代码 + 物料绑定...")
    sku_ids = {}
    for sc, fn, sol, cost, charge, model in SKUS:
        conn.execute(
            "INSERT INTO repair_skus (sku_code, model, fault_name, solution_name, cost_amount, charge_amount, enabled) VALUES (?,?,?,?,?,?,1)",
            (sc, model, fn, sol, cost, charge),
        )
        sku_ids[sc] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Bind materials to SKUs
    bind_count = 0
    for i, (sc, _, _, _, _, _) in enumerate(SKUS):
        if i >= len(SKU_MATERIAL_MAP):
            continue
        for mat_idx in SKU_MATERIAL_MAP[i]:
            mat_sku = MATERIALS[mat_idx][0]
            mid = mat_ids.get(mat_sku)
            if mid:
                conn.execute(
                    "INSERT INTO repair_fault_materials (repair_sku_id, material_id, qty, priority, is_required) VALUES (?,?,1,1,1)",
                    (sku_ids[sc], mid),
                )
                bind_count += 1

    print(f"  OK SKU {len(sku_ids)} 个, 物料绑定 {bind_count} 条")

    # ── 5. Repair Orders ─────────────────────────────────────────
    print(f"[5/7] 生成 {order_count} 条维修工单...")

    # Assign each order a target status
    status_pool = []
    for st, weight in STATUS_DIST:
        status_pool.extend([st] * weight)

    order_map: dict[int, dict] = {}  # repair_order_id -> info

    for idx in range(order_count):
        target_status = status_pool[idx % len(status_pool)]
        created_at = rtime(60)

        # Machine + Customer
        model = MODELS[idx % len(MODELS)]
        imei = f"86{idx:013d}"
        color = COLORS[idx % len(COLORS)]
        memory = MEMORY[idx % len(MEMORY)]
        condition = CONDITIONS[idx % len(CONDITIONS)]
        serial = f"SN{idx:08d}"

        cname = CUSTOMER_NAMES[idx % len(CUSTOMER_NAMES)]
        cust_name = f"{cname}-{idx:03d}"
        phone = f"13{idx % 10}{idx:08d}"[:11]
        cust_type = "商家客户" if "店" in cname or "同行" in cname else "个人客户"

        # Machine
        conn.execute(
            "INSERT INTO machines (machine_no, imei, serial, model, memory, color, condition, current_status, source_type) VALUES (?,?,?,?,?,?,?,?,?)",
            (f"M{idx+1:06d}", imei, serial, model, memory, color, condition, "维修中", "前台"),
        )
        machine_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Customer
        try:
            conn.execute(
                "INSERT INTO customers (name, phone, gender, category, shop_name, tags) VALUES (?,?,?,?,?,?)",
                (cust_name, phone, "男", cust_type, cust_name if "店" in cname else "", "测试"),
            )
        except Exception:
            pass
        cust_id = conn.execute("SELECT customer_id FROM customers WHERE name=? AND phone=? LIMIT 1", (cust_name, phone)).fetchone()
        customer_id = cust_id[0] if cust_id else None

        # Order
        fault = FAULTS[idx % len(FAULTS)]
        diagnosis = DIAGNOSES[idx % len(DIAGNOSES)]
        engineer = ENGINEERS[idx % len(ENGINEERS)]

        order_no = f"WX{NOW.strftime('%Y%m%d')}-{idx+1:04d}"
        conn.execute(
            """INSERT INTO repair_orders
            (order_no, machine_id, customer_id, customer_name, customer_type,
             status, workflow_status, assigned_to, fault_description, diagnosis,
             created_at, updated_at, created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (order_no, machine_id, customer_id, cust_name, cust_type,
             "维修中", "维修中", engineer, fault, diagnosis,
             created_at, created_at, "admin"),
        )
        repair_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        order_map[repair_id] = {
            "target_status": target_status,
            "created_at": created_at,
            "machine_id": machine_id,
            "engineer": engineer,
        }

        # Inspection (pre)
        abnormal_items = random.sample(INSPECTION_ITEMS, k=random.randint(1, 4))
        for item in abnormal_items:
            conn.execute(
                "INSERT INTO repair_order_inspections (repair_order_id, stage, item, abnormal, note, updated_by) VALUES (?,?,?,?,?,?)",
                (repair_id, "pre", item, 1, "", engineer),
            )

        # Repair items with SKU
        chosen_skus = random.sample(SKUS, k=random.randint(1, 3))
        for sc, fn, sol, cost, charge, _ in chosen_skus:
            conn.execute(
                "INSERT INTO repair_items (repair_order_id, sku_id, item_name, quantity, cost_amount, charge_amount) VALUES (?,?,?,1,?,?)",
                (repair_id, sku_ids[sc], fn, cost, charge),
            )

        # Quote
        quote = sum(c[3] + c[4] for c in chosen_skus) + random.randint(0, 200)
        conn.execute(
            "UPDATE repair_orders SET quoted_amount=? WHERE repair_order_id=?",
            (quote, repair_id),
        )

        # Notes
        if idx % 3 == 0:
            for note_type, content in random.sample(NOTES, k=random.randint(1, 3)):
                conn.execute(
                    "INSERT INTO repair_order_notes (repair_order_id, note_type, content, created_by, created_at) VALUES (?,?,?,?,?)",
                    (repair_id, note_type, content, random.choice(ENGINEERS), created_at),
                )

        if (idx + 1) % 25 == 0:
            print(f"  ... {idx + 1}/{order_count}")

    conn.commit()
    print(f"  OK {order_count} 条工单已创建")

    # ── 6. Apply statuses + timestamps ───────────────────────────
    print("[6/7] 设置工单状态与时间线...")
    status_count: dict[str, int] = {}
    for rid, info in order_map.items():
        ts = info["target_status"]
        created = info["created_at"]

        updated = rtime_between(1, 50)
        completed = None
        delivered = None
        closed = None
        wf = ts

        if ts == "维修完成":
            wf = "待交付检测"
            completed = updated
        elif ts in ("已交付", "待支付"):
            wf = "待收款/财务确认"
            completed = rtime_between(5, 50)
            delivered = updated
        elif ts == "财务待确认":
            wf = "待收款/财务确认"
            completed = rtime_between(10, 50)
            delivered = rtime_between(5, 45)
        elif ts == "已完结":
            wf = "已完结"
            completed = rtime_between(15, 55)
            delivered = rtime_between(10, 50)
            closed = updated
        elif ts == "已取消":
            wf = "已作废"
            closed = updated

        conn.execute(
            """UPDATE repair_orders SET
            status=?, workflow_status=?,
            completed_at=COALESCE(?, completed_at),
            delivered_at=COALESCE(?, delivered_at),
            closed_at=COALESCE(?, closed_at),
            updated_at=?
            WHERE repair_order_id=?""",
            (ts, wf, completed, delivered, closed, updated, rid),
        )
        status_count[ts] = status_count.get(ts, 0) + 1

    for st, cnt in sorted(status_count.items()):
        print(f"  . {st}: {cnt} 条")

    # ── 7. Material reservations ─────────────────────────────────
    print("[7/7] 创建物料预占记录...")
    items = conn.execute(
        "SELECT ri.repair_item_id, ri.repair_order_id, ri.sku_id, ri.quantity FROM repair_items ri WHERE ri.sku_id IS NOT NULL"
    ).fetchall()

    reserved = 0
    for item in items:
        sku_id = item["sku_id"]
        bindings = conn.execute(
            "SELECT * FROM repair_fault_materials WHERE repair_sku_id=? ORDER BY priority, binding_id",
            (sku_id,),
        ).fetchall()
        for b in bindings:
            q = max(int(b["qty"] * max(item["quantity"], 1)), 1)
            conn.execute(
                """INSERT OR IGNORE INTO repair_material_reservations
                (repair_order_id, repair_item_id, repair_sku_id, material_id, qty, reserved_qty, status, note)
                VALUES (?,?,?,?,?,0,'已预占','自动')""",
                (item["repair_order_id"], item["repair_item_id"], sku_id, b["material_id"], q),
            )
            reserved += 1

    conn.commit()
    print(f"  OK 预占记录 {reserved} 条")

    # ── Final stats ──────────────────────────────────────────────
    conn.commit()
    total_orders = conn.execute("SELECT COUNT(*) FROM repair_orders").fetchone()[0]
    total_notes = conn.execute("SELECT COUNT(*) FROM repair_order_notes WHERE is_deleted=0").fetchone()[0]
    ts_min = conn.execute("SELECT MIN(created_at) FROM repair_orders").fetchone()[0]
    ts_max = conn.execute("SELECT MAX(created_at) FROM repair_orders").fetchone()[0]

    print("\n" + "=" * 60)
    print("  生成完成!")
    print(f"  工单总数: {total_orders}  备注: {total_notes}  预占: {reserved}")
    print(f"  时间范围: {ts_min}  ~  {ts_max}")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    amount = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    seed(amount)
