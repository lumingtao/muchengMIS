from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MVP_ROOT = ROOT / "mis_mvp"
if str(MVP_ROOT) not in sys.path:
    sys.path.insert(0, str(MVP_ROOT))

from backend.db import connect, migrate

DEFAULT_SOURCE = ROOT / "mis_pwa" / "data" / "mis_workflow.sqlite3"
DEFAULT_TARGET = ROOT / "mis_mvp" / "data" / "mis_mvp.sqlite3"


def rowdict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def ensure_customer(conn: sqlite3.Connection, src: dict[str, Any]) -> int:
    name = src.get("name") or "待补"
    phone = src.get("contact_masked") or src.get("contact") or ""
    existing = conn.execute(
        """
        SELECT customer_id FROM customers
        WHERE name=? AND (phone=? OR ?='')
        ORDER BY customer_id LIMIT 1
        """,
        (name, phone, phone),
    ).fetchone()
    if existing:
        return int(existing["customer_id"])
    cur = conn.execute(
        """
        INSERT INTO customers
        (name, phone, category, shop_name, tags, remark, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            phone,
            src.get("customer_type") or "待确认",
            src.get("shop_name") or "",
            src.get("counter_no") or "",
            src.get("remark") or "",
            src.get("created_at") or "",
            src.get("updated_at") or src.get("created_at") or "",
        ),
    )
    return int(cur.lastrowid)


def ensure_machine(conn: sqlite3.Connection, order: dict[str, Any], customer_id: int | None) -> int:
    order_no = order["order_no"]
    machine_no = f"WF-{order_no}"
    existing = conn.execute("SELECT machine_id FROM machines WHERE machine_no=?", (machine_no,)).fetchone()
    if existing:
        machine_id = int(existing["machine_id"])
        conn.execute(
            """
            UPDATE machines
            SET model=?, current_status=?, customer_id=?, assigned_to=?, remark=?, updated_at=?
            WHERE machine_id=?
            """,
            (
                order.get("device") or "待补",
                order.get("status") or "待确认",
                customer_id,
                order.get("engineer") or "",
                order.get("remark") or "",
                order.get("updated_at") or order.get("created_at") or "",
                machine_id,
            ),
        )
        return machine_id
    cur = conn.execute(
        """
        INSERT INTO machines
        (machine_no, imei, model, source_type, current_status, customer_id,
         created_by, assigned_to, remark, created_at, updated_at, closed_at)
        VALUES (?, NULL, ?, '维修', ?, ?, 'workflow-import', ?, ?, ?, ?, ?)
        """,
        (
            machine_no,
            order.get("device") or "待补",
            order.get("status") or "待确认",
            customer_id,
            order.get("engineer") or "",
            order.get("remark") or "",
            order.get("created_at") or "",
            order.get("updated_at") or order.get("created_at") or "",
            order.get("closed_at") or None,
        ),
    )
    return int(cur.lastrowid)


def upsert_repair_order(conn: sqlite3.Connection, order: dict[str, Any], customer_id: int | None, machine_id: int) -> int:
    existing = conn.execute("SELECT repair_order_id FROM repair_orders WHERE order_no=?", (order["order_no"],)).fetchone()
    values = (
        machine_id,
        customer_id,
        order.get("customer_name") or "待补",
        order.get("customer_type") or "待确认",
        order.get("source") or "",
        order.get("counter_no") or "",
        order.get("sales_person") or "",
        order.get("service_type") or "",
        order.get("intake_condition") or "",
        order.get("status") or "待确认",
        order.get("status") or "待确认",
        order.get("engineer") or "",
        order.get("customer_issue") or "",
        order.get("diagnosis") or "",
        order.get("solution") or "",
        float(order.get("quote_amount") or 0),
        order.get("payment_status") or "未收款",
        order.get("settlement_status") or "未结",
        order.get("promised_hours"),
        order.get("due_at") or "",
        order.get("completed_at") or "",
        order.get("delivered_at") or "",
        order.get("remark") or "",
        order.get("created_at") or "",
        order.get("updated_at") or order.get("created_at") or "",
        order.get("closed_at") or None,
    )
    if existing:
        repair_order_id = int(existing["repair_order_id"])
        conn.execute(
            """
            UPDATE repair_orders
            SET machine_id=?, customer_id=?, customer_name=?, customer_type=?, source=?,
                counter_no=?, sales_person=?, service_type=?, intake_condition=?, status=?,
                workflow_status=?, assigned_to=?, fault_description=?, diagnosis=?,
                repair_solution=?, quoted_amount=?, payment_status=?, settlement_status=?,
                promised_hours=?, due_at=?, completed_at=?, delivered_at=?, remark=?,
                created_at=?, updated_at=?, closed_at=?
            WHERE repair_order_id=?
            """,
            (*values, repair_order_id),
        )
        return repair_order_id
    cur = conn.execute(
        """
        INSERT INTO repair_orders
        (order_no, machine_id, customer_id, customer_name, customer_type, source,
         counter_no, sales_person, service_type, intake_condition, status,
         workflow_status, assigned_to, fault_description, diagnosis, repair_solution,
         quoted_amount, payment_status, settlement_status, promised_hours, due_at,
         completed_at, delivered_at, remark, created_at, updated_at, closed_at,
         created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'workflow-import')
        """,
        (order["order_no"], *values),
    )
    return int(cur.lastrowid)


def insert_once(conn: sqlite3.Connection, table: str, source_key: str, sql: str, params: tuple[Any, ...]) -> None:
    existing = conn.execute(f"SELECT 1 FROM {table} WHERE source_key=?", (source_key,)).fetchone()
    if not existing:
        conn.execute(sql, params)


def import_data(source: Path, target: Path, backup: bool = True) -> dict[str, int]:
    if not source.exists():
        raise FileNotFoundError(source)
    if backup and target.exists():
        shutil.copy2(target, target.with_suffix(f".sqlite3.bak"))
    src = sqlite3.connect(source)
    src.row_factory = sqlite3.Row
    dst = connect(target)
    migrate(dst)
    counts = {"orders": 0, "materials": 0, "payments": 0, "receivables": 0}
    customer_map: dict[int, int] = {}
    material_map: dict[int, int] = {}
    repair_map: dict[int, int] = {}
    for customer in rows(src, "SELECT * FROM customers ORDER BY id"):
        customer_map[int(customer["id"])] = ensure_customer(dst, customer)
    for material in rows(src, "SELECT * FROM materials ORDER BY id"):
        existing = dst.execute("SELECT material_id FROM materials WHERE sku=?", (material["sku"],)).fetchone()
        if existing:
            material_id = int(existing["material_id"])
            dst.execute(
                """
                UPDATE materials
                SET name=?, brand=?, spec=?, compatible_range=?, unit=?, current_qty=?,
                    avg_cost=?, status=?, remark=?, source_key=?, updated_at=?
                WHERE material_id=?
                """,
                (
                    material["name"], material.get("brand") or "", material.get("spec") or "",
                    material.get("compatible_range") or "", material.get("unit") or "件",
                    material.get("current_qty") or 0, material.get("avg_cost") or 0,
                    material.get("status") or "在库", material.get("remark") or "",
                    f"workflow-material-{material['id']}", material.get("updated_at") or "",
                    material_id,
                ),
            )
        else:
            cur = dst.execute(
                """
                INSERT INTO materials
                (sku, name, brand, spec, compatible_range, unit, current_qty, avg_cost,
                 status, remark, source_key, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    material["sku"], material["name"], material.get("brand") or "",
                    material.get("spec") or "", material.get("compatible_range") or "",
                    material.get("unit") or "件", material.get("current_qty") or 0,
                    material.get("avg_cost") or 0, material.get("status") or "在库",
                    material.get("remark") or "", f"workflow-material-{material['id']}",
                    material.get("created_at") or "", material.get("updated_at") or "",
                ),
            )
            material_id = int(cur.lastrowid)
            counts["materials"] += 1
        material_map[int(material["id"])] = material_id
    for batch in rows(src, "SELECT * FROM material_batches ORDER BY id"):
        material_id = material_map[int(batch["material_id"])]
        insert_once(
            dst,
            "material_batches",
            f"workflow-batch-{batch['id']}",
            """
            INSERT INTO material_batches
            (material_id, batch_no, supplier, purchase_type, qty, unit_cost, remaining_qty,
             payment_status, purchased_at, remark, source_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                material_id, batch["batch_no"], batch.get("supplier") or "待确认",
                batch.get("purchase_type") or "采购入库", batch.get("qty") or 0,
                batch.get("unit_cost") or 0, batch.get("remaining_qty") or 0,
                batch.get("payment_status") or "待确认", batch.get("purchased_at") or "",
                batch.get("remark") or "", f"workflow-batch-{batch['id']}",
            ),
        )
    for order in rows(src, "SELECT * FROM repair_orders ORDER BY id"):
        customer_id = customer_map.get(int(order["customer_id"])) if order.get("customer_id") else None
        machine_id = ensure_machine(dst, order, customer_id)
        repair_id = upsert_repair_order(dst, order, customer_id, machine_id)
        repair_map[int(order["id"])] = repair_id
        counts["orders"] += 1
        confirmed = float(order.get("confirmed_amount") or order.get("quote_amount") or 0)
        if confirmed > 0 or "待补" in (order.get("remark") or ""):
            insert_once(
                dst,
                "repair_income_items",
                f"workflow-income-{order['id']}",
                """
                INSERT INTO repair_income_items
                (repair_order_id, item_type, item_name, amount, status, remark, source_key)
                VALUES (?, '维修收入', ?, ?, ?, ?, ?)
                """,
                (
                    repair_id,
                    order.get("service_type") or "维修收入",
                    confirmed,
                    order.get("payment_status") or "待确认",
                    order.get("remark") or "",
                    f"workflow-income-{order['id']}",
                ),
            )
    for event in rows(src, "SELECT * FROM repair_events ORDER BY id"):
        repair_id = repair_map.get(int(event["repair_id"]))
        order = dst.execute("SELECT machine_id FROM repair_orders WHERE repair_order_id=?", (repair_id,)).fetchone()
        if repair_id and order:
            insert_once(
                dst,
                "machine_events",
                f"workflow-event-{event['id']}",
                """
                INSERT INTO machine_events
                (machine_id, event_type, title, detail, operator, related_type, related_id, created_at)
                VALUES (?, 'repair', ?, ?, ?, 'repair', ?, ?)
                """,
                (
                    int(order["machine_id"]),
                    event.get("event_type") or "维修事件",
                    event.get("note") or event.get("status") or "",
                    event.get("actor") or "import",
                    repair_id,
                    event.get("happened_at") or event.get("created_at") or "",
                ),
            )
    for payment in rows(src, "SELECT * FROM payments ORDER BY id"):
        repair_id = repair_map.get(int(payment["repair_id"])) if payment.get("repair_id") else None
        if not repair_id:
            continue
        insert_once(
            dst,
            "payments",
            f"workflow-payment-{payment['id']}",
            """
            INSERT INTO payments
            (source_type, source_id, direction, amount, method, account, transaction_no,
             operator, received_by, confirmed_by, status, paid_at, confirmed_at, remark, source_key)
            VALUES ('repair', ?, '收入', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repair_id, payment.get("amount") or 0, payment.get("payment_method") or "待确认",
                payment.get("account") or "", payment.get("transaction_no") or "",
                payment.get("received_by") or "import", payment.get("received_by") or "import",
                payment.get("confirmed_by") or "", payment.get("status") or "待确认",
                payment.get("paid_at") or "", payment.get("confirmed_at") or "",
                payment.get("remark") or "", f"workflow-payment-{payment['id']}",
            ),
        )
        counts["payments"] += 1
    for receivable in rows(src, "SELECT * FROM receivables ORDER BY id"):
        repair_id = repair_map.get(int(receivable["repair_id"])) if receivable.get("repair_id") else None
        insert_once(
            dst,
            "receivables",
            f"workflow-receivable-{receivable['id']}",
            """
            INSERT INTO receivables
            (repair_order_id, customer_id, customer_name, receivable_type, amount,
             status, created_at, settled_at, remark, source_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repair_id, customer_map.get(int(receivable["customer_id"])) if receivable.get("customer_id") else None,
                receivable.get("customer_name") or "待补", receivable.get("receivable_type") or "待确认",
                receivable.get("amount") or 0, receivable.get("status") or "未结",
                receivable.get("created_at") or "", receivable.get("settled_at") or "",
                receivable.get("remark") or "", f"workflow-receivable-{receivable['id']}",
            ),
        )
        counts["receivables"] += 1
    for material_use in rows(src, "SELECT * FROM repair_materials ORDER BY id"):
        repair_id = repair_map.get(int(material_use["repair_id"]))
        material_id = material_map.get(int(material_use["material_id"]))
        if not repair_id or not material_id:
            continue
        insert_once(
            dst,
            "repair_materials",
            f"workflow-repair-material-{material_use['id']}",
            """
            INSERT INTO repair_materials
            (repair_order_id, material_id, qty, unit_cost, total_cost, source_type,
             issued_by, issued_to, issued_at, remark, source_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repair_id, material_id, material_use.get("qty") or 0,
                material_use.get("unit_cost") or 0, material_use.get("total_cost") or 0,
                material_use.get("source_type") or "库存", material_use.get("issued_by") or "",
                material_use.get("issued_to") or "", material_use.get("issued_at") or "",
                material_use.get("remark") or "", f"workflow-repair-material-{material_use['id']}",
            ),
        )
        insert_once(
            dst,
            "repair_cost_items",
            f"workflow-material-cost-{material_use['id']}",
            """
            INSERT INTO repair_cost_items
            (repair_order_id, item_type, item_name, qty, unit_cost, total_cost,
             status, remark, source_key)
            VALUES (?, '库存物料', ?, ?, ?, ?, '已确认', ?, ?)
            """,
            (
                repair_id,
                rows(src, "SELECT name FROM materials WHERE id=?", (material_use["material_id"],))[0]["name"],
                material_use.get("qty") or 0, material_use.get("unit_cost") or 0,
                material_use.get("total_cost") or 0, material_use.get("remark") or "",
                f"workflow-material-cost-{material_use['id']}",
            ),
        )
    for movement in rows(src, "SELECT * FROM stock_movements ORDER BY id"):
        material_id = material_map.get(int(movement["material_id"]))
        repair_id = repair_map.get(int(movement["repair_id"])) if movement.get("repair_id") else None
        if material_id:
            insert_once(
                dst,
                "stock_movements",
                f"workflow-stock-movement-{movement['id']}",
                """
                INSERT INTO stock_movements
                (material_id, repair_order_id, movement_type, qty, unit_cost, actor,
                 counterparty, note, happened_at, source_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    material_id, repair_id, movement.get("movement_type") or "待确认",
                    movement.get("qty") or 0, movement.get("unit_cost") or 0,
                    movement.get("actor") or "import", movement.get("counterparty") or "",
                    movement.get("note") or "", movement.get("happened_at") or "",
                    f"workflow-stock-movement-{movement['id']}",
                ),
            )
    dst.commit()
    src.close()
    dst.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Import real repair workflow data into mis_mvp.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()
    counts = import_data(args.source, args.target, backup=not args.no_backup)
    print(counts)


if __name__ == "__main__":
    main()
