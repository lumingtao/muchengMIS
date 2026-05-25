from __future__ import annotations

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

CREATE TABLE IF NOT EXISTS repair_orders (
    repair_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    customer_id INTEGER,
    status TEXT NOT NULL,
    fault_description TEXT NOT NULL DEFAULT '',
    diagnosis TEXT NOT NULL DEFAULT '',
    quoted_amount REAL NOT NULL DEFAULT 0,
    delivery_check TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    FOREIGN KEY (machine_id) REFERENCES machines(machine_id)
);

CREATE TABLE IF NOT EXISTS repair_items (
    repair_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_order_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    cost_amount REAL NOT NULL DEFAULT 0,
    charge_amount REAL NOT NULL DEFAULT 0,
    remark TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repair_order_id) REFERENCES repair_orders(repair_order_id)
);

CREATE TABLE IF NOT EXISTS recycle_orders (
    recycle_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    payer TEXT NOT NULL DEFAULT '',
    payee TEXT NOT NULL DEFAULT '',
    operator TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
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
"""


def connect(database_path: Path | str) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    seed_users(conn)
    conn.commit()


def seed_users(conn: sqlite3.Connection) -> None:
    users = [
        ("admin", "admin", "admin"),
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
