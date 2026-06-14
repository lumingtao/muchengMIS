from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .auth import hash_password


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_no TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    wechat TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '个人客户',
    shop_name TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    vip_level TEXT NOT NULL DEFAULT '',
    discount_policy TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '正常',
    source TEXT NOT NULL DEFAULT '',
    birthday TEXT NOT NULL DEFAULT '',
    last_contact_at TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_interactions (
    interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    interaction_type TEXT NOT NULL DEFAULT '备注',
    content TEXT NOT NULL,
    next_follow_at TEXT NOT NULL DEFAULT '',
    completed INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS devices (
    imei TEXT PRIMARY KEY,
    serial TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL,
    memory TEXT NOT NULL DEFAULT '',
    battery TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT '',
    warranty TEXT NOT NULL DEFAULT '',
    condition TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    seller TEXT NOT NULL DEFAULT '',
    recycler TEXT NOT NULL DEFAULT '',
    recycle_price REAL NOT NULL DEFAULT 0,
    recycle_time TEXT NOT NULL DEFAULT '',
    buyer_customer_id INTEGER,
    buyer_name TEXT NOT NULL DEFAULT '',
    salesperson TEXT NOT NULL DEFAULT '',
    sale_price REAL NOT NULL DEFAULT 0,
    sale_time TEXT NOT NULL DEFAULT '',
    settlement_status TEXT NOT NULL DEFAULT '未结',
    remark TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS repairs (
    repair_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    customer_id INTEGER,
    customer_name TEXT NOT NULL,
    model TEXT NOT NULL,
    solution TEXT NOT NULL DEFAULT '',
    quote REAL NOT NULL DEFAULT 0,
    payment_method TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    settlement_status TEXT NOT NULL DEFAULT '未结',
    remark TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settlements (
    settlement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    settlement_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operator TEXT NOT NULL,
    total_amount REAL NOT NULL,
    status TEXT NOT NULL DEFAULT '已确认',
    remark TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settlement_items (
    settlement_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    settlement_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    amount REAL NOT NULL,
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    FOREIGN KEY (settlement_id) REFERENCES settlements(settlement_id)
);

CREATE TABLE IF NOT EXISTS operation_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    username TEXT NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    imei TEXT NOT NULL DEFAULT '',
    customer_id INTEGER,
    request_summary TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL,
    error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS machines (
    machine_id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_no TEXT NOT NULL UNIQUE,
    imei TEXT UNIQUE,
    serial TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL,
    memory TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL DEFAULT '',
    condition TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL DEFAULT '',
    current_status TEXT NOT NULL,
    customer_id INTEGER,
    created_by TEXT NOT NULL DEFAULT '',
    assigned_to TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS device_models (
    device_model_id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT NOT NULL DEFAULT 'Apple',
    model_name TEXT NOT NULL,
    colors_json TEXT NOT NULL DEFAULT '[]',
    capacities_json TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 100,
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(brand, model_name)
);

CREATE TABLE IF NOT EXISTS repair_orders (
    repair_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT,
    machine_id INTEGER NOT NULL,
    customer_id INTEGER,
    customer_name TEXT NOT NULL DEFAULT '',
    customer_type TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    counter_no TEXT NOT NULL DEFAULT '',
    sales_person TEXT NOT NULL DEFAULT '',
    service_type TEXT NOT NULL DEFAULT '',
    intake_condition TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    workflow_status TEXT NOT NULL DEFAULT '待指派工程师',
    assigned_to TEXT NOT NULL DEFAULT '',
    fault_description TEXT NOT NULL DEFAULT '',
    fault_detail TEXT NOT NULL DEFAULT '',
    diagnosis TEXT NOT NULL DEFAULT '',
    repair_solution TEXT NOT NULL DEFAULT '',
    quoted_amount REAL NOT NULL DEFAULT 0,
    quote_confirm_status TEXT NOT NULL DEFAULT '',
    quote_confirm_method TEXT NOT NULL DEFAULT '',
    quote_contact_person TEXT NOT NULL DEFAULT '',
    quote_confirm_remark TEXT NOT NULL DEFAULT '',
    quote_confirmed_at TEXT,
    delivery_check TEXT NOT NULL DEFAULT '',
    payment_status TEXT NOT NULL DEFAULT '未收款',
    settlement_status TEXT NOT NULL DEFAULT '未结',
    promised_hours REAL,
    due_at TEXT NOT NULL DEFAULT '',
    completed_at TEXT NOT NULL DEFAULT '',
    delivered_at TEXT NOT NULL DEFAULT '',
    engineer_closed_at TEXT,
    engineer_close_remark TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    FOREIGN KEY (machine_id) REFERENCES machines(machine_id)
);

CREATE TABLE IF NOT EXISTS repair_order_archives (
    archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_order_id INTEGER NOT NULL UNIQUE,
    order_no TEXT NOT NULL DEFAULT '',
    archived_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_by TEXT NOT NULL DEFAULT '',
    archive_reason TEXT NOT NULL DEFAULT '',
    purge_after TEXT NOT NULL,
    snapshot_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS repair_items (
    repair_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_order_id INTEGER NOT NULL,
    sku_id INTEGER,
    item_name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    cost_amount REAL NOT NULL DEFAULT 0,
    charge_amount REAL NOT NULL DEFAULT 0,
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repair_order_id) REFERENCES repair_orders(repair_order_id)
);

CREATE TABLE IF NOT EXISTS repair_income_items (
    income_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_order_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    item_name TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT '待确认',
    remark TEXT NOT NULL DEFAULT '',
    source_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repair_order_id) REFERENCES repair_orders(repair_order_id)
);

CREATE TABLE IF NOT EXISTS repair_cost_items (
    cost_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_order_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    item_name TEXT NOT NULL,
    qty REAL NOT NULL DEFAULT 1,
    unit_cost REAL NOT NULL DEFAULT 0,
    total_cost REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT '待确认',
    remark TEXT NOT NULL DEFAULT '',
    source_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repair_order_id) REFERENCES repair_orders(repair_order_id)
);

CREATE TABLE IF NOT EXISTS materials (
    material_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE,
    material_code TEXT NOT NULL DEFAULT '',
    category_id INTEGER,
    default_location_id INTEGER,
    min_qty REAL NOT NULL DEFAULT 0,
    track_unit INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    brand TEXT NOT NULL DEFAULT '',
    spec TEXT NOT NULL DEFAULT '',
    compatible_range TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT '件',
    current_qty REAL NOT NULL DEFAULT 0,
    avg_cost REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT '在库',
    remark TEXT NOT NULL DEFAULT '',
    source_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS material_categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    parent_id INTEGER,
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS warehouse_areas (
    area_id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT '启用',
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS warehouse_locations (
    location_id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id INTEGER,
    location_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT '启用',
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (area_id) REFERENCES warehouse_areas(area_id)
);

CREATE TABLE IF NOT EXISTS material_batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    batch_no TEXT NOT NULL UNIQUE,
    supplier TEXT NOT NULL DEFAULT '待确认',
    purchase_type TEXT NOT NULL DEFAULT '采购入库',
    batch_type TEXT NOT NULL DEFAULT 'purchase',
    location_id INTEGER,
    purchase_no TEXT NOT NULL DEFAULT '',
    handler TEXT NOT NULL DEFAULT '',
    qty REAL NOT NULL DEFAULT 0,
    unit_cost REAL NOT NULL DEFAULT 0,
    remaining_qty REAL NOT NULL DEFAULT 0,
    payment_status TEXT NOT NULL DEFAULT '待确认',
    refund_status TEXT NOT NULL DEFAULT '',
    refund_amount REAL NOT NULL DEFAULT 0,
    refund_method TEXT NOT NULL DEFAULT '',
    refund_transaction_no TEXT NOT NULL DEFAULT '',
    purchased_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    remark TEXT NOT NULL DEFAULT '',
    source_key TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (material_id) REFERENCES materials(material_id)
);

CREATE TABLE IF NOT EXISTS material_units (
    unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    batch_id INTEGER,
    unit_code TEXT NOT NULL UNIQUE,
    current_status TEXT NOT NULL DEFAULT '在库可用',
    location_id INTEGER,
    engineer_user TEXT NOT NULL DEFAULT '',
    repair_order_id INTEGER,
    request_id INTEGER,
    unit_cost REAL NOT NULL DEFAULT 0,
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (material_id) REFERENCES materials(material_id),
    FOREIGN KEY (batch_id) REFERENCES material_batches(batch_id),
    FOREIGN KEY (location_id) REFERENCES warehouse_locations(location_id)
);

CREATE TABLE IF NOT EXISTS material_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_no TEXT NOT NULL UNIQUE,
    repair_order_id INTEGER,
    engineer_user TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '待审核',
    requested_by TEXT NOT NULL DEFAULT '',
    approved_by TEXT NOT NULL DEFAULT '',
    issued_by TEXT NOT NULL DEFAULT '',
    rejected_by TEXT NOT NULL DEFAULT '',
    cancelled_by TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at TEXT,
    issued_at TEXT,
    closed_at TEXT,
    FOREIGN KEY (repair_order_id) REFERENCES repair_orders(repair_order_id)
);

CREATE TABLE IF NOT EXISTS material_request_items (
    request_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    repair_sku_id INTEGER,
    qty REAL NOT NULL DEFAULT 1,
    approved_qty REAL NOT NULL DEFAULT 0,
    issued_qty REAL NOT NULL DEFAULT 0,
    remark TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (request_id) REFERENCES material_requests(request_id),
    FOREIGN KEY (material_id) REFERENCES materials(material_id),
    FOREIGN KEY (repair_sku_id) REFERENCES repair_skus(sku_id)
);

CREATE TABLE IF NOT EXISTS material_returns (
    return_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    request_id INTEGER,
    repair_order_id INTEGER,
    engineer_user TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '待验收',
    return_type TEXT NOT NULL DEFAULT '工程师退料',
    inspect_result TEXT NOT NULL DEFAULT '',
    inspected_by TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    inspected_at TEXT,
    FOREIGN KEY (unit_id) REFERENCES material_units(unit_id),
    FOREIGN KEY (request_id) REFERENCES material_requests(request_id),
    FOREIGN KEY (repair_order_id) REFERENCES repair_orders(repair_order_id)
);

CREATE TABLE IF NOT EXISTS repair_materials (
    repair_material_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_order_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    qty REAL NOT NULL DEFAULT 1,
    unit_cost REAL NOT NULL DEFAULT 0,
    total_cost REAL NOT NULL DEFAULT 0,
    source_type TEXT NOT NULL DEFAULT '库存',
    issued_by TEXT NOT NULL DEFAULT '',
    issued_to TEXT NOT NULL DEFAULT '',
    issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    remark TEXT NOT NULL DEFAULT '',
    source_key TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (repair_order_id) REFERENCES repair_orders(repair_order_id),
    FOREIGN KEY (material_id) REFERENCES materials(material_id)
);

CREATE TABLE IF NOT EXISTS stock_movements (
    stock_movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    batch_id INTEGER,
    unit_id INTEGER,
    request_id INTEGER,
    repair_order_id INTEGER,
    location_id INTEGER,
    movement_type TEXT NOT NULL,
    direction TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL DEFAULT '',
    source_id INTEGER,
    qty REAL NOT NULL,
    unit_cost REAL NOT NULL DEFAULT 0,
    actor TEXT NOT NULL DEFAULT '',
    counterparty TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    happened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_key TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (material_id) REFERENCES materials(material_id),
    FOREIGN KEY (repair_order_id) REFERENCES repair_orders(repair_order_id)
);

CREATE TABLE IF NOT EXISTS stock_counts (
    count_id INTEGER PRIMARY KEY AUTOINCREMENT,
    count_no TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT '草稿',
    counted_by TEXT NOT NULL DEFAULT '',
    confirmed_by TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TEXT
);

CREATE TABLE IF NOT EXISTS stock_count_items (
    count_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    count_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    location_id INTEGER,
    book_qty REAL NOT NULL DEFAULT 0,
    actual_qty REAL NOT NULL DEFAULT 0,
    diff_qty REAL NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (count_id) REFERENCES stock_counts(count_id),
    FOREIGN KEY (material_id) REFERENCES materials(material_id)
);

CREATE TABLE IF NOT EXISTS stock_adjustments (
    adjustment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    adjustment_no TEXT NOT NULL UNIQUE,
    material_id INTEGER NOT NULL,
    unit_id INTEGER,
    location_id INTEGER,
    qty REAL NOT NULL DEFAULT 0,
    adjustment_type TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    operator TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (material_id) REFERENCES materials(material_id),
    FOREIGN KEY (unit_id) REFERENCES material_units(unit_id)
);

CREATE TABLE IF NOT EXISTS repair_fault_materials (
    binding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_sku_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    qty REAL NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 1,
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(repair_sku_id, material_id),
    FOREIGN KEY (repair_sku_id) REFERENCES repair_skus(sku_id),
    FOREIGN KEY (material_id) REFERENCES materials(material_id)
);

CREATE TABLE IF NOT EXISTS receivables (
    receivable_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_order_id INTEGER,
    customer_id INTEGER,
    customer_name TEXT NOT NULL,
    counter_no TEXT NOT NULL DEFAULT '',
    receivable_type TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT '未结',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    settled_at TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    source_key TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (repair_order_id) REFERENCES repair_orders(repair_order_id)
);

CREATE TABLE IF NOT EXISTS repair_skus (
    sku_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model TEXT NOT NULL DEFAULT '',
    sku_code TEXT NOT NULL UNIQUE,
    fault_name TEXT NOT NULL,
    solution_name TEXT NOT NULL,
    cost_amount REAL NOT NULL DEFAULT 0,
    charge_amount REAL NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recycle_orders (
    recycle_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT,
    machine_id INTEGER NOT NULL,
    customer_id INTEGER,
    status TEXT NOT NULL,
    inspection_note TEXT NOT NULL DEFAULT '',
    inspection_result TEXT NOT NULL DEFAULT '',
    quoted_amount REAL NOT NULL DEFAULT 0,
    paid_amount REAL NOT NULL DEFAULT 0,
    remark TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    FOREIGN KEY (machine_id) REFERENCES machines(machine_id)
);

CREATE TABLE IF NOT EXISTS inventory_items (
    inventory_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL UNIQUE,
    recycle_order_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    cost_amount REAL NOT NULL DEFAULT 0,
    sale_price REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES machines(machine_id),
    FOREIGN KEY (recycle_order_id) REFERENCES recycle_orders(recycle_order_id)
);

CREATE TABLE IF NOT EXISTS sales_orders (
    sales_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_item_id INTEGER NOT NULL,
    machine_id INTEGER NOT NULL,
    customer_id INTEGER,
    status TEXT NOT NULL,
    sale_price REAL NOT NULL DEFAULT 0,
    salesperson TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(inventory_item_id),
    FOREIGN KEY (machine_id) REFERENCES machines(machine_id)
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    direction TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT NOT NULL DEFAULT '',
    account TEXT NOT NULL DEFAULT '',
    transaction_no TEXT NOT NULL DEFAULT '',
    payer TEXT NOT NULL DEFAULT '',
    payee TEXT NOT NULL DEFAULT '',
    operator TEXT NOT NULL DEFAULT '',
    received_by TEXT NOT NULL DEFAULT '',
    confirmed_by TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '已登记',
    paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    source_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS machine_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    operator TEXT NOT NULL DEFAULT '',
    related_type TEXT NOT NULL DEFAULT '',
    related_id INTEGER,
    source_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES machines(machine_id)
);

CREATE TABLE IF NOT EXISTS machine_notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    operator TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES machines(machine_id)
);

CREATE TABLE IF NOT EXISTS repair_order_photos (
    photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_order_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
    filename TEXT NOT NULL,
    url TEXT NOT NULL,
    uploaded_by TEXT NOT NULL DEFAULT '',
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repair_order_id) REFERENCES repair_orders(repair_order_id)
);

CREATE TABLE IF NOT EXISTS repair_order_inspections (
    inspection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_order_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
    item TEXT NOT NULL,
    abnormal INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (repair_order_id, stage, item),
    FOREIGN KEY (repair_order_id) REFERENCES repair_orders(repair_order_id)
);

CREATE TABLE IF NOT EXISTS repair_order_notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_order_id INTEGER NOT NULL,
    note_type TEXT NOT NULL DEFAULT '内部备注',
    content TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT '',
    deleted_by TEXT NOT NULL DEFAULT '',
    deleted_at TEXT NOT NULL DEFAULT '',
    deleted_reason TEXT NOT NULL DEFAULT '',
    is_deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (repair_order_id) REFERENCES repair_orders(repair_order_id)
);
"""


def connect(database_path: Path | str) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def purge_expired_repair_order_archives(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT repair_order_id
        FROM repair_order_archives
        WHERE purge_after <= CURRENT_TIMESTAMP
        """
    ).fetchall()
    repair_order_ids = [int(row["repair_order_id"]) for row in rows]
    for repair_order_id in repair_order_ids:
        conn.execute("DELETE FROM payments WHERE source_type='repair' AND source_id=?", (repair_order_id,))
        conn.execute("DELETE FROM repair_order_photos WHERE repair_order_id=?", (repair_order_id,))
        conn.execute("DELETE FROM repair_order_inspections WHERE repair_order_id=?", (repair_order_id,))
        conn.execute("DELETE FROM repair_order_notes WHERE repair_order_id=?", (repair_order_id,))
        conn.execute("DELETE FROM repair_items WHERE repair_order_id=?", (repair_order_id,))
        conn.execute("DELETE FROM repair_income_items WHERE repair_order_id=?", (repair_order_id,))
        conn.execute("DELETE FROM repair_cost_items WHERE repair_order_id=?", (repair_order_id,))
        conn.execute("DELETE FROM repair_materials WHERE repair_order_id=?", (repair_order_id,))
        conn.execute("DELETE FROM receivables WHERE repair_order_id=?", (repair_order_id,))
        conn.execute("UPDATE material_units SET repair_order_id=NULL WHERE repair_order_id=?", (repair_order_id,))
        conn.execute("UPDATE material_requests SET repair_order_id=NULL WHERE repair_order_id=?", (repair_order_id,))
        conn.execute("UPDATE material_returns SET repair_order_id=NULL WHERE repair_order_id=?", (repair_order_id,))
        conn.execute("UPDATE stock_movements SET repair_order_id=NULL WHERE repair_order_id=?", (repair_order_id,))
        conn.execute("DELETE FROM repair_orders WHERE repair_order_id=?", (repair_order_id,))
        conn.execute("DELETE FROM repair_order_archives WHERE repair_order_id=?", (repair_order_id,))


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    ensure_columns(conn)
    purge_expired_repair_order_archives(conn)
    backfill_customer_member_no(conn)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_member_no ON customers(member_no)")
    seed_users(conn)
    seed_device_models(conn)
    seed_repair_skus(conn)
    backfill_material_units(conn)
    conn.commit()


def ensure_columns(conn: sqlite3.Connection) -> None:
    columns: dict[str, list[tuple[str, str]]] = {
        "customers": [
            ("member_no", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT '正常'"),
            ("source", "TEXT NOT NULL DEFAULT ''"),
            ("birthday", "TEXT NOT NULL DEFAULT ''"),
            ("last_contact_at", "TEXT NOT NULL DEFAULT ''"),
        ],
        "repair_orders": [
            ("order_no", "TEXT"),
            ("customer_name", "TEXT NOT NULL DEFAULT ''"),
            ("customer_type", "TEXT NOT NULL DEFAULT ''"),
            ("source", "TEXT NOT NULL DEFAULT ''"),
            ("counter_no", "TEXT NOT NULL DEFAULT ''"),
            ("sales_person", "TEXT NOT NULL DEFAULT ''"),
            ("service_type", "TEXT NOT NULL DEFAULT ''"),
            ("intake_condition", "TEXT NOT NULL DEFAULT ''"),
            ("workflow_status", "TEXT NOT NULL DEFAULT '待指派工程师'"),
            ("assigned_to", "TEXT NOT NULL DEFAULT ''"),
            ("fault_detail", "TEXT NOT NULL DEFAULT ''"),
            ("repair_solution", "TEXT NOT NULL DEFAULT ''"),
            ("quote_confirm_status", "TEXT NOT NULL DEFAULT ''"),
            ("quote_confirm_method", "TEXT NOT NULL DEFAULT ''"),
            ("quote_contact_person", "TEXT NOT NULL DEFAULT ''"),
            ("quote_confirm_remark", "TEXT NOT NULL DEFAULT ''"),
            ("quote_confirmed_at", "TEXT"),
            ("payment_status", "TEXT NOT NULL DEFAULT '未收款'"),
            ("settlement_status", "TEXT NOT NULL DEFAULT '未结'"),
            ("promised_hours", "REAL"),
            ("due_at", "TEXT NOT NULL DEFAULT ''"),
            ("completed_at", "TEXT NOT NULL DEFAULT ''"),
            ("delivered_at", "TEXT NOT NULL DEFAULT ''"),
            ("engineer_closed_at", "TEXT"),
            ("engineer_close_remark", "TEXT NOT NULL DEFAULT ''"),
            ("archived_at", "TEXT NOT NULL DEFAULT ''"),
            ("archived_by", "TEXT NOT NULL DEFAULT ''"),
            ("archive_reason", "TEXT NOT NULL DEFAULT ''"),
            ("purge_after", "TEXT NOT NULL DEFAULT ''"),
        ],
        "recycle_orders": [
            ("order_no", "TEXT"),
        ],
        "repair_items": [
            ("sku_id", "INTEGER"),
        ],
        "repair_skus": [
            ("model", "TEXT NOT NULL DEFAULT ''"),
        ],
        "device_models": [
            ("brand", "TEXT NOT NULL DEFAULT 'Apple'"),
            ("colors_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("capacities_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("enabled", "INTEGER NOT NULL DEFAULT 1"),
            ("sort_order", "INTEGER NOT NULL DEFAULT 100"),
            ("remark", "TEXT NOT NULL DEFAULT ''"),
        ],
        "payments": [
            ("account", "TEXT NOT NULL DEFAULT ''"),
            ("transaction_no", "TEXT NOT NULL DEFAULT ''"),
            ("received_by", "TEXT NOT NULL DEFAULT ''"),
            ("confirmed_by", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT '已登记'"),
            ("paid_at", "TEXT NOT NULL DEFAULT ''"),
            ("confirmed_at", "TEXT NOT NULL DEFAULT ''"),
            ("source_key", "TEXT NOT NULL DEFAULT ''"),
        ],
        "machine_events": [
            ("source_key", "TEXT NOT NULL DEFAULT ''"),
        ],
        "materials": [
            ("material_code", "TEXT NOT NULL DEFAULT ''"),
            ("category_id", "INTEGER"),
            ("default_location_id", "INTEGER"),
            ("min_qty", "REAL NOT NULL DEFAULT 0"),
            ("track_unit", "INTEGER NOT NULL DEFAULT 1"),
        ],
        "material_batches": [
            ("batch_type", "TEXT NOT NULL DEFAULT 'purchase'"),
            ("location_id", "INTEGER"),
            ("purchase_no", "TEXT NOT NULL DEFAULT ''"),
            ("handler", "TEXT NOT NULL DEFAULT ''"),
            ("refund_status", "TEXT NOT NULL DEFAULT ''"),
            ("refund_amount", "REAL NOT NULL DEFAULT 0"),
            ("refund_method", "TEXT NOT NULL DEFAULT ''"),
            ("refund_transaction_no", "TEXT NOT NULL DEFAULT ''"),
        ],
        "stock_movements": [
            ("batch_id", "INTEGER"),
            ("unit_id", "INTEGER"),
            ("request_id", "INTEGER"),
            ("location_id", "INTEGER"),
            ("direction", "TEXT NOT NULL DEFAULT ''"),
            ("source_type", "TEXT NOT NULL DEFAULT ''"),
            ("source_id", "INTEGER"),
        ],
    }
    for table, table_columns in columns.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, definition in table_columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def backfill_customer_member_no(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT customer_id FROM customers WHERE member_no = '' OR member_no IS NULL ORDER BY customer_id"
    ).fetchall()
    for row in rows:
        customer_id = int(row["customer_id"])
        conn.execute(
            "UPDATE customers SET member_no=? WHERE customer_id=?",
            (f"M{customer_id:06d}", customer_id),
        )


def seed_users(conn: sqlite3.Connection) -> None:
    users = [
        ("admin", "admin", "admin"),
        ("boss", "boss", "boss"),
        ("frontdesk", "frontdesk", "frontdesk"),
        ("engineer", "engineer", "engineer"),
        ("staff", "staff", "staff"),
        ("finance", "finance", "finance"),
    ]
    for username, password, role in users:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (username, hash_password(password), role),
        )


def seed_device_models(conn: sqlite3.Connection) -> None:
    apple_common_colors = ["黑色", "白色", "蓝色", "粉色", "绿色", "黄色", "紫色", "红色", "银色", "金色", "深空灰", "午夜色", "星光色"]
    titanium_colors = ["原色钛金属", "黑色钛金属", "白色钛金属", "蓝色钛金属", "沙漠色钛金属"]
    models = [
        ("Apple", "iPhone 16 Pro Max", titanium_colors, ["256GB", "512GB", "1TB"], 10),
        ("Apple", "iPhone 16 Pro", titanium_colors, ["128GB", "256GB", "512GB", "1TB"], 11),
        ("Apple", "iPhone 16 Plus", ["黑色", "白色", "粉色", "青色", "深群青色"], ["128GB", "256GB", "512GB"], 12),
        ("Apple", "iPhone 16", ["黑色", "白色", "粉色", "青色", "深群青色"], ["128GB", "256GB", "512GB"], 13),
        ("Apple", "iPhone 15 Pro Max", titanium_colors[:4], ["256GB", "512GB", "1TB"], 20),
        ("Apple", "iPhone 15 Pro", titanium_colors[:4], ["128GB", "256GB", "512GB", "1TB"], 21),
        ("Apple", "iPhone 15 Plus", ["黑色", "蓝色", "绿色", "黄色", "粉色"], ["128GB", "256GB", "512GB"], 22),
        ("Apple", "iPhone 15", ["黑色", "蓝色", "绿色", "黄色", "粉色"], ["128GB", "256GB", "512GB"], 23),
        ("Apple", "iPhone 14 Pro Max", ["深空黑色", "银色", "金色", "暗紫色"], ["128GB", "256GB", "512GB", "1TB"], 30),
        ("Apple", "iPhone 14 Pro", ["深空黑色", "银色", "金色", "暗紫色"], ["128GB", "256GB", "512GB", "1TB"], 31),
        ("Apple", "iPhone 14 Plus", ["午夜色", "星光色", "蓝色", "紫色", "黄色", "红色"], ["128GB", "256GB", "512GB"], 32),
        ("Apple", "iPhone 14", ["午夜色", "星光色", "蓝色", "紫色", "黄色", "红色"], ["128GB", "256GB", "512GB"], 33),
        ("Apple", "iPhone 13 Pro Max", ["石墨色", "金色", "银色", "远峰蓝色", "苍岭绿色"], ["128GB", "256GB", "512GB", "1TB"], 40),
        ("Apple", "iPhone 13 Pro", ["石墨色", "金色", "银色", "远峰蓝色", "苍岭绿色"], ["128GB", "256GB", "512GB", "1TB"], 41),
        ("Apple", "iPhone 13", ["星光色", "午夜色", "蓝色", "粉色", "绿色", "红色"], ["128GB", "256GB", "512GB"], 42),
        ("Apple", "iPhone 12", apple_common_colors, ["64GB", "128GB", "256GB"], 50),
        ("Apple", "iPhone 11", ["黑色", "白色", "绿色", "黄色", "紫色", "红色"], ["64GB", "128GB", "256GB"], 60),
        ("Apple", "iPad Pro 12.9", ["银色", "深空灰"], ["128GB", "256GB", "512GB", "1TB", "2TB"], 70),
        ("Apple", "iPad Pro 11", ["银色", "深空灰"], ["128GB", "256GB", "512GB", "1TB", "2TB"], 71),
        ("Apple", "iPad Air", ["深空灰", "星光色", "粉色", "紫色", "蓝色"], ["64GB", "256GB", "128GB", "512GB"], 72),
        ("Apple", "iPad", ["银色", "蓝色", "粉色", "黄色"], ["64GB", "256GB"], 73),
        ("Huawei", "Mate 30", ["亮黑色", "星河银", "翡冷翠", "罗兰紫"], ["128GB", "256GB"], 100),
        ("OPPO", "OPPO 常见机型", ["黑色", "白色", "蓝色", "绿色", "金色"], ["64GB", "128GB", "256GB", "512GB"], 110),
    ]
    for brand, model_name, colors, capacities, sort_order in models:
        conn.execute(
            """
            INSERT OR IGNORE INTO device_models
            (brand, model_name, colors_json, capacities_json, enabled, sort_order, remark)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                brand,
                model_name,
                json.dumps(colors, ensure_ascii=False),
                json.dumps(capacities, ensure_ascii=False),
                sort_order,
                "系统预置",
            ),
        )


def seed_repair_skus(conn: sqlite3.Connection) -> None:
    skus = [
        ("SCREEN-OLED", "屏幕损坏", "更换 OLED 屏幕总成", 320, 580, "常见碎屏维修"),
        ("BATTERY", "电池老化", "更换电池", 80, 180, "电池健康低于建议值"),
        ("CHARGE-FLEX", "无法充电", "更换尾插排线", 60, 160, "充电口或排线故障"),
        ("BOARD-DIAG", "不开机", "主板检测维修", 180, 580, "主板类故障基础报价"),
        ("WATER-CLEAN", "进水", "进水清洗检测", 50, 120, "不保证修复结果"),
    ]
    for sku_code, fault_name, solution_name, cost_amount, charge_amount, remark in skus:
        conn.execute(
            """
            INSERT OR IGNORE INTO repair_skus
            (model, sku_code, fault_name, solution_name, cost_amount, charge_amount, enabled, remark)
            VALUES ('', ?, ?, ?, ?, ?, 1, ?)
            """,
            (sku_code, fault_name, solution_name, cost_amount, charge_amount, remark),
        )


def backfill_material_units(conn: sqlite3.Connection) -> None:
    movement_balances = {
        row["material_id"]: int(row["qty"] or 0)
        for row in conn.execute(
            "SELECT material_id, SUM(qty) AS qty FROM stock_movements GROUP BY material_id"
        ).fetchall()
        if row["qty"] is not None
    }
    materials = {
        row["material_id"]: int(row["current_qty"] or 0)
        for row in conn.execute("SELECT material_id, current_qty FROM materials").fetchall()
    }
    available_targets = {material_id: max(0, movement_balances.get(material_id, qty)) for material_id, qty in materials.items()}
    allocated_available: dict[int, int] = {}
    batches = conn.execute(
        """
        SELECT b.*, m.sku, m.material_code
        FROM material_batches b
        JOIN materials m ON m.material_id=b.material_id
        ORDER BY b.batch_id
        """
    ).fetchall()
    for batch in batches:
        existing = conn.execute("SELECT COUNT(*) AS qty FROM material_units WHERE batch_id=?", (batch["batch_id"],)).fetchone()["qty"]
        if existing:
            continue
        total_qty = int(batch["qty"] or 0)
        remaining_qty = int(batch["remaining_qty"] or 0)
        if total_qty <= 0:
            continue
        material_code = batch["material_code"] or batch["sku"]
        purchased_day = str(batch["purchased_at"] or "").replace("-", "")[:8] or "HISTORY"
        target_available = available_targets.get(batch["material_id"], max(0, remaining_qty))
        already_available = allocated_available.get(batch["material_id"], 0)
        for index in range(1, total_qty + 1):
            unit_code = f"{material_code}-{purchased_day}-{index:04d}"
            status = "在库可用" if already_available < target_available else "历史出库"
            if status == "在库可用":
                already_available += 1
            conn.execute(
                """
                INSERT OR IGNORE INTO material_units
                (material_id, batch_id, unit_code, current_status, location_id, unit_cost, remark)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch["material_id"],
                    batch["batch_id"],
                    unit_code,
                    status,
                    batch["location_id"] if "location_id" in batch.keys() else None,
                    batch["unit_cost"] or 0,
                    "历史批次迁移生成单件码",
                ),
            )
        allocated_available[batch["material_id"]] = already_available
    for material_id, target_available in available_targets.items():
        generated = conn.execute(
            """
            SELECT unit_id FROM material_units
            WHERE material_id=? AND remark='历史批次迁移生成单件码'
            ORDER BY unit_id
            """,
            (material_id,),
        ).fetchall()
        for index, unit in enumerate(generated):
            status = "在库可用" if index < target_available else "历史出库"
            conn.execute(
                "UPDATE material_units SET current_status=? WHERE unit_id=? AND remark='历史批次迁移生成单件码'",
                (status, unit["unit_id"]),
            )
    material_ids = conn.execute("SELECT material_id FROM materials").fetchall()
    for row in material_ids:
        qty = conn.execute(
            "SELECT COUNT(*) AS qty FROM material_units WHERE material_id=? AND current_status='在库可用'",
            (row["material_id"],),
        ).fetchone()["qty"]
        conn.execute("UPDATE materials SET current_qty=? WHERE material_id=?", (qty, row["material_id"]))
