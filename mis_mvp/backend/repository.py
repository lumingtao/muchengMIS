from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from .models import CustomerInput, DeviceStatus, PurchaseInput, RepairInput, RepairStatus, SettlementStatus


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def next_customer_member_no(self) -> str:
        row = self.conn.execute("SELECT COALESCE(MAX(customer_id), 0) + 1 AS next_id FROM customers").fetchone()
        next_id = int(row["next_id"])
        while True:
            member_no = f"M{next_id:06d}"
            exists = self.conn.execute("SELECT 1 FROM customers WHERE member_no=?", (member_no,)).fetchone()
            if not exists:
                return member_no
            next_id += 1

    def next_order_no(self, table: str, prefix: str) -> str:
        if table not in {"repair_orders", "recycle_orders"}:
            raise ValueError(f"Unsupported order table: {table}")
        day = datetime.now().strftime("%Y%m%d")
        pattern = f"{prefix}{day}-%"
        rows = self.conn.execute(
            f"SELECT order_no FROM {table} WHERE order_no LIKE ? ORDER BY order_no DESC",
            (pattern,),
        ).fetchall()
        next_seq = 1
        for row in rows:
            suffix = str(row["order_no"] or "").rsplit("-", 1)[-1]
            if suffix.isdigit():
                next_seq = int(suffix) + 1
                break
        return f"{prefix}{day}-{next_seq:04d}"

    def get_user(self, username: str) -> dict[str, Any] | None:
        return row_to_dict(self.conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone())

    def upsert_customer(self, data: CustomerInput) -> int:
        existing = self.conn.execute(
            """
            SELECT customer_id FROM customers
            WHERE name = ? AND (phone = ? OR ? = '')
            ORDER BY customer_id LIMIT 1
            """,
            (data.name, data.phone, data.phone),
        ).fetchone()
        if existing:
            cid = int(existing["customer_id"])
            self.conn.execute(
                """
                UPDATE customers
                SET phone=CASE WHEN ? = '' THEN phone ELSE ? END,
                    gender=CASE WHEN ? = '' THEN gender ELSE ? END,
                    wechat=CASE WHEN ? = '' THEN wechat ELSE ? END,
                    category=CASE WHEN ? = '' THEN category ELSE ? END,
                    shop_name=CASE WHEN ? = '' THEN shop_name ELSE ? END,
                    address=CASE WHEN ? = '' THEN address ELSE ? END,
                    tags=CASE WHEN ? = '' THEN tags ELSE ? END,
                    vip_level=CASE WHEN ? = '' THEN vip_level ELSE ? END,
                    discount_policy=CASE WHEN ? = '' THEN discount_policy ELSE ? END,
                    status=CASE WHEN ? = '' THEN status ELSE ? END,
                    source=CASE WHEN ? = '' THEN source ELSE ? END,
                    birthday=CASE WHEN ? = '' THEN birthday ELSE ? END,
                    last_contact_at=CASE WHEN ? = '' THEN last_contact_at ELSE ? END,
                    remark=CASE WHEN ? = '' THEN remark ELSE ? END,
                    updated_at=CURRENT_TIMESTAMP
                WHERE customer_id=?
                """,
                (
                    data.phone,
                    data.phone,
                    data.gender,
                    data.gender,
                    data.wechat,
                    data.wechat,
                    data.category,
                    data.category,
                    data.shop_name,
                    data.shop_name,
                    data.address,
                    data.address,
                    data.tags,
                    data.tags,
                    data.vip_level,
                    data.vip_level,
                    data.discount_policy,
                    data.discount_policy,
                    data.status,
                    data.status,
                    data.source,
                    data.source,
                    data.birthday,
                    data.birthday,
                    data.last_contact_at,
                    data.last_contact_at,
                    data.remark,
                    data.remark,
                    cid,
                ),
            )
            return cid
        member_no = data.member_no.strip() or self.next_customer_member_no()
        cur = self.conn.execute(
            """
            INSERT INTO customers
            (member_no, name, phone, gender, wechat, category, shop_name, address, tags, vip_level,
             discount_policy, status, source, birthday, last_contact_at, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                member_no,
                data.name,
                data.phone,
                data.gender,
                data.wechat,
                data.category,
                data.shop_name,
                data.address,
                data.tags,
                data.vip_level,
                data.discount_policy,
                data.status,
                data.source,
                data.birthday,
                data.last_contact_at,
                data.remark,
            ),
        )
        return int(cur.lastrowid)

    def create_customer(self, data: CustomerInput) -> int:
        member_no = data.member_no.strip() or self.next_customer_member_no()
        cur = self.conn.execute(
            """
            INSERT INTO customers
            (member_no, name, phone, gender, wechat, category, shop_name, address, tags, vip_level,
             discount_policy, status, source, birthday, last_contact_at, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                member_no,
                data.name,
                data.phone,
                data.gender,
                data.wechat,
                data.category,
                data.shop_name,
                data.address,
                data.tags,
                data.vip_level,
                data.discount_policy,
                data.status,
                data.source,
                data.birthday,
                data.last_contact_at,
                data.remark,
            ),
        )
        return int(cur.lastrowid)

    def get_customer(self, customer_id: int) -> dict[str, Any] | None:
        return row_to_dict(self.conn.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,)).fetchone())

    def update_customer(self, customer_id: int, data: CustomerInput) -> None:
        member_no = data.member_no.strip() or f"M{customer_id:06d}"
        self.conn.execute(
            """
            UPDATE customers
            SET member_no=?, name=?, phone=?, gender=?, wechat=?, category=?, shop_name=?, address=?, tags=?,
                vip_level=?, discount_policy=?, status=?, source=?, birthday=?, last_contact_at=?,
                remark=?, updated_at=CURRENT_TIMESTAMP
            WHERE customer_id=?
            """,
            (
                member_no,
                data.name,
                data.phone,
                data.gender,
                data.wechat,
                data.category,
                data.shop_name,
                data.address,
                data.tags,
                data.vip_level,
                data.discount_policy,
                data.status,
                data.source,
                data.birthday,
                data.last_contact_at,
                data.remark,
                customer_id,
            ),
        )

    def search_customers(
        self,
        keyword: str = "",
        category: str = "",
        vip_level: str = "",
        status: str = "",
        tag: str = "",
    ) -> list[dict[str, Any]]:
        like = f"%{keyword}%"
        tag_like = f"%{tag}%"
        rows = self.conn.execute(
            """
            SELECT c.*,
                   COALESCE(rs.repair_total, 0) + COALESCE(ss.sale_total, 0) AS total_spent,
                   COALESCE(rs.repair_count, 0) AS repair_count,
                   COALESCE(rc.recycle_count, 0) AS recycle_count,
                   COALESCE(ss.sale_count, 0) AS sale_count
            FROM customers c
            LEFT JOIN (
                SELECT customer_id, COUNT(*) AS repair_count, SUM(quoted_amount) AS repair_total
                FROM repair_orders
                WHERE customer_id IS NOT NULL AND archived_at=''
                GROUP BY customer_id
            ) rs ON rs.customer_id = c.customer_id
            LEFT JOIN (
                SELECT customer_id, COUNT(*) AS recycle_count
                FROM recycle_orders
                WHERE customer_id IS NOT NULL
                GROUP BY customer_id
            ) rc ON rc.customer_id = c.customer_id
            LEFT JOIN (
                SELECT customer_id, COUNT(*) AS sale_count, SUM(sale_price) AS sale_total
                FROM sales_orders
                WHERE customer_id IS NOT NULL
                GROUP BY customer_id
            ) ss ON ss.customer_id = c.customer_id
            WHERE (? = '' OR c.member_no LIKE ? OR c.name LIKE ? OR c.phone LIKE ? OR c.shop_name LIKE ? OR c.tags LIKE ?)
              AND (? = '' OR c.category = ?)
              AND (? = '' OR c.vip_level = ?)
              AND (? = '' OR c.status = ?)
              AND (? = '' OR c.tags LIKE ?)
            ORDER BY c.updated_at DESC, c.customer_id DESC
            LIMIT 100
            """,
            (
                keyword,
                like,
                like,
                like,
                like,
                like,
                category,
                category,
                vip_level,
                vip_level,
                status,
                status,
                tag,
                tag_like,
            ),
        ).fetchall()
        return [dict(row) for row in rows]

    def customer_detail(self, customer_id: int) -> dict[str, Any]:
        customer = self.get_customer(customer_id)
        machines = self.conn.execute(
            """
            SELECT * FROM machines
            WHERE customer_id=?
            ORDER BY updated_at DESC, machine_id DESC
            """,
            (customer_id,),
        ).fetchall()
        repair_orders = self.conn.execute(
            """
            SELECT ro.*, m.machine_no, m.imei, m.model
            FROM repair_orders ro
            JOIN machines m ON m.machine_id = ro.machine_id
            WHERE ro.customer_id=? AND ro.archived_at=''
            ORDER BY ro.updated_at DESC, ro.repair_order_id DESC
            """,
            (customer_id,),
        ).fetchall()
        recycle_orders = self.conn.execute(
            """
            SELECT ro.*, m.machine_no, m.imei, m.model
            FROM recycle_orders ro
            JOIN machines m ON m.machine_id = ro.machine_id
            WHERE ro.customer_id=?
            ORDER BY ro.updated_at DESC, ro.recycle_order_id DESC
            """,
            (customer_id,),
        ).fetchall()
        sales_orders = self.conn.execute(
            """
            SELECT so.*, m.machine_no, m.imei, m.model
            FROM sales_orders so
            JOIN machines m ON m.machine_id = so.machine_id
            WHERE so.customer_id=?
            ORDER BY so.sales_order_id DESC
            """,
            (customer_id,),
        ).fetchall()
        interactions = self.list_customer_interactions(customer_id)
        repair_total = sum(float(row["quoted_amount"] or 0) for row in repair_orders)
        sale_total = sum(float(row["sale_price"] or 0) for row in sales_orders)
        recycle_total = sum(float(row["paid_amount"] or 0) for row in recycle_orders)
        return {
            "customer": customer,
            "machines": [dict(row) for row in machines],
            "repair_orders": [dict(row) for row in repair_orders],
            "recycle_orders": [dict(row) for row in recycle_orders],
            "sales_orders": [dict(row) for row in sales_orders],
            "interactions": interactions,
            "stats": {
                "machine_count": len(machines),
                "repair_count": len(repair_orders),
                "recycle_count": len(recycle_orders),
                "sale_count": len(sales_orders),
                "repair_total": repair_total,
                "sale_total": sale_total,
                "recycle_total": recycle_total,
                "total_spent": repair_total + sale_total,
            },
        }

    def add_customer_interaction(self, customer_id: int, data: dict[str, Any], created_by: str) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO customer_interactions
            (customer_id, interaction_type, content, next_follow_at, completed, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                data.get("interaction_type", "备注"),
                data.get("content", ""),
                data.get("next_follow_at", ""),
                1 if data.get("completed") else 0,
                created_by,
            ),
        )
        self.conn.execute(
            "UPDATE customers SET last_contact_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE customer_id=?",
            (customer_id,),
        )
        return int(cur.lastrowid)

    def get_customer_interaction(self, interaction_id: int) -> dict[str, Any] | None:
        return row_to_dict(
            self.conn.execute(
                "SELECT * FROM customer_interactions WHERE interaction_id=?",
                (interaction_id,),
            ).fetchone()
        )

    def update_customer_interaction(self, interaction_id: int, data: dict[str, Any]) -> None:
        self.conn.execute(
            """
            UPDATE customer_interactions
            SET interaction_type=?, content=?, next_follow_at=?, completed=?, updated_at=CURRENT_TIMESTAMP
            WHERE interaction_id=?
            """,
            (
                data.get("interaction_type", "备注"),
                data.get("content", ""),
                data.get("next_follow_at", ""),
                1 if data.get("completed") else 0,
                interaction_id,
            ),
        )

    def list_customer_interactions(self, customer_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT * FROM customer_interactions
            WHERE customer_id=?
            ORDER BY completed ASC, created_at DESC, interaction_id DESC
            """,
            (customer_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def create_device(self, data: PurchaseInput, customer_id: int | None) -> None:
        self.conn.execute(
            """
            INSERT INTO devices
            (imei, serial, model, memory, battery, color, country, version, warranty, condition,
             status, seller, recycler, recycle_price, recycle_time, settlement_status, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.imei,
                data.serial,
                data.model,
                data.memory,
                data.battery,
                data.color,
                data.country,
                data.version,
                data.warranty,
                data.condition,
                DeviceStatus.in_stock.value,
                data.seller,
                data.recycler,
                data.recycle_price,
                data.recycle_time,
                data.settlement_status.value,
                data.remark,
            ),
        )

    def get_device(self, imei: str) -> dict[str, Any] | None:
        return row_to_dict(self.conn.execute("SELECT * FROM devices WHERE imei = ?", (imei,)).fetchone())

    def list_devices(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.conn.execute("SELECT * FROM devices WHERE status = ? ORDER BY rowid DESC", (status,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM devices ORDER BY rowid DESC").fetchall()
        return [dict(row) for row in rows]

    def sell_device(self, imei: str, buyer_customer_id: int | None, buyer: str, salesperson: str, sale_time: str, sale_price: float, settlement_status: SettlementStatus) -> None:
        self.conn.execute(
            """
            UPDATE devices
            SET status=?, buyer_customer_id=?, buyer_name=?, salesperson=?,
                sale_time=?, sale_price=?, settlement_status=?
            WHERE imei=?
            """,
            (DeviceStatus.sold.value, buyer_customer_id, buyer, salesperson, sale_time, sale_price, settlement_status.value, imei),
        )

    def create_repair(self, data: RepairInput, customer_id: int | None) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO repairs
            (customer_id, customer_name, model, solution, quote, payment_method, status, settlement_status, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                data.customer_name,
                data.model,
                data.solution,
                data.quote,
                data.payment_method,
                data.status.value,
                data.settlement_status.value,
                data.remark,
            ),
        )
        return int(cur.lastrowid)

    def get_repair(self, repair_id: int) -> dict[str, Any] | None:
        return row_to_dict(self.conn.execute("SELECT * FROM repairs WHERE repair_id = ?", (repair_id,)).fetchone())

    def list_repairs(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM repairs ORDER BY repair_id DESC").fetchall()
        return [dict(row) for row in rows]

    def update_repair_status(self, repair_id: int, status: RepairStatus) -> None:
        self.conn.execute("UPDATE repairs SET status = ? WHERE repair_id = ?", (status.value, repair_id))

    def unsettled_sales_for_customer(self, customer_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT * FROM devices
            WHERE buyer_customer_id=? AND status=? AND settlement_status=?
            ORDER BY sale_time DESC, imei
            """,
            (customer_id, DeviceStatus.sold.value, SettlementStatus.unsettled.value),
        ).fetchall()
        return [dict(row) for row in rows]

    def unsettled_repairs_for_customer(self, customer_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT * FROM repairs
            WHERE customer_id=? AND settlement_status=?
            ORDER BY repair_id DESC
            """,
            (customer_id, SettlementStatus.unsettled.value),
        ).fetchall()
        return [dict(row) for row in rows]

    def unsettled_repair_orders_for_customer(self, customer_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT ro.*, ro.repair_order_id AS repair_id, ro.quoted_amount AS quote,
                   COALESCE(m.model, '') AS model
            FROM repair_orders ro
            JOIN machines m ON m.machine_id = ro.machine_id
            WHERE ro.customer_id=? AND ro.archived_at='' AND ro.status NOT IN ('已结单', '已作废')
              AND ro.quoted_amount > 0
            ORDER BY ro.repair_order_id DESC
            """,
            (customer_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def create_settlement(self, customer_id: int, operator: str, total_amount: float, remark: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO settlements (customer_id, operator, total_amount, remark) VALUES (?, ?, ?, ?)",
            (customer_id, operator, total_amount, remark),
        )
        return int(cur.lastrowid)

    def add_settlement_item(self, settlement_id: int, source_type: str, source_id: str, amount: float, previous_status: str, new_status: str) -> None:
        self.conn.execute(
            """
            INSERT INTO settlement_items
            (settlement_id, source_type, source_id, amount, previous_status, new_status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (settlement_id, source_type, source_id, amount, previous_status, new_status),
        )

    def mark_sale_settled(self, imei: str) -> None:
        self.conn.execute("UPDATE devices SET settlement_status=? WHERE imei=?", (SettlementStatus.settled.value, imei))

    def mark_repair_settled(self, repair_id: int) -> None:
        self.conn.execute(
            "UPDATE repairs SET settlement_status=?, status=? WHERE repair_id=?",
            (SettlementStatus.settled.value, RepairStatus.settled.value, repair_id),
        )

    def mark_repair_order_settled(self, repair_order_id: int) -> None:
        self.conn.execute(
            "UPDATE repair_orders SET status='已结单', closed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?",
            (repair_order_id,),
        )

    def add_log(self, username: str, role: str, action: str, target_type: str, target_id: str, result: str, error: str = "", imei: str = "", customer_id: int | None = None, request_summary: str = "") -> None:
        self.conn.execute(
            """
            INSERT INTO operation_logs
            (username, role, action, target_type, target_id, imei, customer_id, request_summary, result, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (username, role, action, target_type, target_id, imei, customer_id, request_summary, result, error),
        )

    def logs(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM operation_logs ORDER BY log_id DESC LIMIT 200").fetchall()
        return [dict(row) for row in rows]

    def get_machine(self, machine_id: int) -> dict[str, Any] | None:
        return row_to_dict(self.conn.execute("SELECT * FROM machines WHERE machine_id = ?", (machine_id,)).fetchone())

    def get_machine_by_imei(self, imei: str) -> dict[str, Any] | None:
        return row_to_dict(self.conn.execute("SELECT * FROM machines WHERE imei = ?", (imei,)).fetchone())

    def get_machine_by_serial(self, serial: str) -> dict[str, Any] | None:
        return row_to_dict(
            self.conn.execute(
                """
                SELECT * FROM machines
                WHERE serial = ? AND serial <> ''
                ORDER BY updated_at DESC, machine_id DESC
                LIMIT 1
                """,
                (serial,),
            ).fetchone()
        )

    def create_machine(self, data: dict[str, Any]) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO machines
            (machine_no, imei, serial, model, memory, color, condition, source_type,
             current_status, customer_id, created_by, assigned_to, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["machine_no"],
                data.get("imei") or None,
                data.get("serial", ""),
                data["model"],
                data.get("memory", ""),
                data.get("color", ""),
                data.get("condition", ""),
                data.get("source_type", ""),
                data["current_status"],
                data.get("customer_id"),
                data.get("created_by", ""),
                data.get("assigned_to", ""),
                data.get("remark", ""),
            ),
        )
        return int(cur.lastrowid)

    def update_machine_status(self, machine_id: int, status: str, source_type: str | None = None) -> None:
        if source_type is None:
            self.conn.execute(
                "UPDATE machines SET current_status=?, updated_at=CURRENT_TIMESTAMP WHERE machine_id=?",
                (status, machine_id),
            )
        else:
            self.conn.execute(
                "UPDATE machines SET current_status=?, source_type=?, updated_at=CURRENT_TIMESTAMP WHERE machine_id=?",
                (status, source_type, machine_id),
            )

    def update_machine(self, machine_id: int, data: dict[str, Any]) -> None:
        self.conn.execute(
            """
            UPDATE machines
            SET imei=?, serial=?, model=?, memory=?, color=?, condition=?,
                source_type=?, current_status=?, customer_id=?, updated_at=CURRENT_TIMESTAMP
            WHERE machine_id=?
            """,
            (
                data.get("imei") or None,
                data.get("serial", ""),
                data["model"],
                data.get("memory", ""),
                data.get("color", ""),
                data.get("condition", ""),
                data.get("source_type", ""),
                data["current_status"],
                data.get("customer_id"),
                machine_id,
            ),
        )

    def _device_model_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for source, target in (("colors_json", "colors"), ("capacities_json", "capacities"), ("model_numbers_json", "model_numbers")):
            try:
                data[target] = json.loads(data.get(source) or "[]")
            except json.JSONDecodeError:
                data[target] = []
        return data

    def list_device_models(self, keyword: str = "", enabled_only: bool = False) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if enabled_only:
            clauses.append("enabled=1")
        if keyword:
            like = f"%{keyword}%"
            clauses.append("(brand LIKE ? OR model_name LIKE ? OR model_numbers_json LIKE ? OR remark LIKE ?)")
            params.extend([like, like, like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM device_models {where} ORDER BY enabled DESC, sort_order, brand, model_name",
            params,
        ).fetchall()
        return [self._device_model_row(row) for row in rows]

    def get_device_model(self, device_model_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM device_models WHERE device_model_id=?", (device_model_id,)).fetchone()
        return self._device_model_row(row) if row else None

    def upsert_device_model(self, data: dict[str, Any]) -> int:
        brand = str(data.get("brand") or "Apple").strip()
        model_name = str(data.get("model_name") or "").strip()
        colors = [str(item).strip() for item in data.get("colors", []) if str(item).strip()]
        capacities = [str(item).strip() for item in data.get("capacities", []) if str(item).strip()]
        model_numbers = [str(item).strip() for item in data.get("model_numbers", []) if str(item).strip()]
        payload = (
            brand,
            model_name,
            json.dumps(colors, ensure_ascii=False),
            json.dumps(capacities, ensure_ascii=False),
            json.dumps(model_numbers, ensure_ascii=False),
            1 if data.get("enabled", True) else 0,
            int(data.get("sort_order") or 100),
            str(data.get("remark") or ""),
        )
        if data.get("device_model_id"):
            device_model_id = int(data["device_model_id"])
            self.conn.execute(
                """
                UPDATE device_models
                SET brand=?, model_name=?, colors_json=?, capacities_json=?, model_numbers_json=?,
                    enabled=?, sort_order=?, remark=?, updated_at=CURRENT_TIMESTAMP
                WHERE device_model_id=?
                """,
                (*payload, device_model_id),
            )
            return device_model_id
        existing = self.conn.execute(
            "SELECT device_model_id FROM device_models WHERE brand=? AND model_name=?",
            (brand, model_name),
        ).fetchone()
        if existing:
            device_model_id = int(existing["device_model_id"])
            self.conn.execute(
                """
                UPDATE device_models
                SET colors_json=?, capacities_json=?, model_numbers_json=?, enabled=?, sort_order=?,
                    remark=?, updated_at=CURRENT_TIMESTAMP
                WHERE device_model_id=?
                """,
                (payload[2], payload[3], payload[4], payload[5], payload[6], payload[7], device_model_id),
            )
            return device_model_id
        cur = self.conn.execute(
            """
            INSERT INTO device_models
            (brand, model_name, colors_json, capacities_json, model_numbers_json, enabled, sort_order, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        return int(cur.lastrowid)

    def _employee_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        try:
            data["skill_tags"] = json.loads(data.get("skill_tags_json") or "[]")
        except json.JSONDecodeError:
            data["skill_tags"] = []
        data["accepting_orders"] = bool(data.get("accepting_orders"))
        return data

    def list_employees(self, keyword: str = "", department: str = "", accepting_orders: str = "") -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if keyword:
            like = f"%{keyword}%"
            clauses.append("(name LIKE ? OR position LIKE ? OR department LIKE ? OR skill_tags_json LIKE ? OR remark LIKE ?)")
            params.extend([like, like, like, like, like])
        if department:
            clauses.append("department=?")
            params.append(department)
        if accepting_orders:
            clauses.append("accepting_orders=?")
            params.append(1 if accepting_orders == "true" else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"""
            SELECT e.*,
                   COALESCE(u.role, '') AS user_role,
                   (
                       SELECT COUNT(*)
                       FROM repair_orders ro
                       WHERE ro.assigned_to=e.username
                         AND ro.archived_at=''
                         AND ro.status NOT IN ('已完结', '已结单', '已作废')
                   ) AS active_order_count
            FROM employees e
            LEFT JOIN users u ON u.username=e.username
            {where}
            ORDER BY accepting_orders DESC, department, open_order_count, employee_id DESC
            """,
            params,
        ).fetchall()
        return [self._employee_row(row) for row in rows]

    def get_employee(self, employee_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM employees WHERE employee_id=?", (employee_id,)).fetchone()
        return self._employee_row(row) if row else None

    def upsert_employee(self, data: dict[str, Any]) -> int:
        username = str(data.get("username") or "").strip()
        name = str(data.get("name") or "").strip()
        position = str(data.get("position") or "工程师").strip() or "工程师"
        department = str(data.get("department") or "").strip()
        skill_tags = [str(item).strip() for item in data.get("skill_tags", []) if str(item).strip()]
        payload = (
            username,
            name,
            position,
            department,
            int(data.get("open_order_count") or 0),
            json.dumps(skill_tags, ensure_ascii=False),
            1 if data.get("accepting_orders", True) else 0,
            str(data.get("remark") or ""),
        )
        if data.get("employee_id"):
            employee_id = int(data["employee_id"])
            self.conn.execute(
                """
                UPDATE employees
                SET username=?, name=?, position=?, department=?, open_order_count=?, skill_tags_json=?,
                    accepting_orders=?, remark=?, updated_at=CURRENT_TIMESTAMP
                WHERE employee_id=?
                """,
                (*payload, employee_id),
            )
            return employee_id
        existing = self.conn.execute(
            "SELECT employee_id FROM employees WHERE name=? AND position=? AND department=?",
            (name, position, department),
        ).fetchone()
        if existing:
            employee_id = int(existing["employee_id"])
            self.conn.execute(
                """
                UPDATE employees
                SET username=?, open_order_count=?, skill_tags_json=?, accepting_orders=?, remark=?, updated_at=CURRENT_TIMESTAMP
                WHERE employee_id=?
                """,
                (payload[0], payload[4], payload[5], payload[6], payload[7], employee_id),
            )
            return employee_id
        cur = self.conn.execute(
            """
            INSERT INTO employees
            (username, name, position, department, open_order_count, skill_tags_json, accepting_orders, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        return int(cur.lastrowid)

    def employee_by_username(self, username: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM employees WHERE username=?", (username,)).fetchone()
        return self._employee_row(row) if row else None

    def refresh_employee_open_order_count(self, username: str) -> None:
        if not username:
            return
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM repair_orders
            WHERE assigned_to=?
              AND archived_at=''
              AND status NOT IN ('已完结', '已结单', '已作废')
            """,
            (username,),
        ).fetchone()
        self.conn.execute(
            "UPDATE employees SET open_order_count=?, updated_at=CURRENT_TIMESTAMP WHERE username=?",
            (int(row["count"] if row else 0), username),
        )

    def add_machine_note(self, machine_id: int, content: str, operator: str) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO machine_notes (machine_id, content, operator)
            VALUES (?, ?, ?)
            """,
            (machine_id, content, operator),
        )
        return int(cur.lastrowid)

    def close_machine(self, machine_id: int, status: str) -> None:
        self.conn.execute(
            "UPDATE machines SET current_status=?, closed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE machine_id=?",
            (status, machine_id),
        )

    def delete_machine(self, machine_id: int) -> None:
        repair_ids = [
            int(row["repair_order_id"])
            for row in self.conn.execute("SELECT repair_order_id FROM repair_orders WHERE machine_id=?", (machine_id,)).fetchall()
        ]
        recycle_ids = [
            int(row["recycle_order_id"])
            for row in self.conn.execute("SELECT recycle_order_id FROM recycle_orders WHERE machine_id=?", (machine_id,)).fetchall()
        ]
        sales_ids = [
            int(row["sales_order_id"])
            for row in self.conn.execute("SELECT sales_order_id FROM sales_orders WHERE machine_id=?", (machine_id,)).fetchall()
        ]
        for repair_id in repair_ids:
            self.conn.execute("DELETE FROM payments WHERE source_type='repair' AND source_id=?", (repair_id,))
            self.conn.execute("DELETE FROM repair_items WHERE repair_order_id=?", (repair_id,))
        for recycle_id in recycle_ids:
            self.conn.execute("DELETE FROM payments WHERE source_type='recycle' AND source_id=?", (recycle_id,))
        for sales_id in sales_ids:
            self.conn.execute("DELETE FROM payments WHERE source_type='sale' AND source_id=?", (sales_id,))
        self.conn.execute("DELETE FROM sales_orders WHERE machine_id=?", (machine_id,))
        self.conn.execute("DELETE FROM inventory_items WHERE machine_id=?", (machine_id,))
        self.conn.execute("DELETE FROM recycle_orders WHERE machine_id=?", (machine_id,))
        self.conn.execute("DELETE FROM repair_orders WHERE machine_id=?", (machine_id,))
        self.conn.execute("DELETE FROM machine_notes WHERE machine_id=?", (machine_id,))
        self.conn.execute("DELETE FROM machine_events WHERE machine_id=?", (machine_id,))
        self.conn.execute("DELETE FROM machines WHERE machine_id=?", (machine_id,))

    def search_machines(self, keyword: str = "", assigned_to: str | None = None) -> list[dict[str, Any]]:
        like = f"%{keyword}%"
        assigned_filter = " AND (m.assigned_to = ? OR EXISTS (SELECT 1 FROM repair_orders ro WHERE ro.machine_id = m.machine_id AND ro.assigned_to = ? AND ro.archived_at=''))" if assigned_to else ""
        params: list[Any] = [keyword, like, like, like, like, like, like]
        if assigned_to:
            params.extend([assigned_to, assigned_to])
        rows = self.conn.execute(
            f"""
            SELECT m.*, c.name AS customer_name
            FROM machines m
            LEFT JOIN customers c ON c.customer_id = m.customer_id
            WHERE (? = '' OR m.machine_no LIKE ? OR m.imei LIKE ? OR m.serial LIKE ?
               OR m.model LIKE ? OR c.name LIKE ? OR c.phone LIKE ?)
            {assigned_filter}
            ORDER BY m.updated_at DESC, m.machine_id DESC
            LIMIT 100
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def create_repair_order(
        self,
        machine_id: int,
        customer_id: int | None,
        status: str,
        fault_description: str,
        remark: str,
        created_by: str,
        workflow_status: str = "待指派工程师",
        assigned_to: str = "",
        order_prefix: str = "WX",
        service_type: str = "维修",
    ) -> int:
        order_no = self.next_order_no("repair_orders", order_prefix)
        cur = self.conn.execute(
            """
            INSERT INTO repair_orders
            (order_no, machine_id, customer_id, status, workflow_status, assigned_to, service_type, fault_description, remark, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (order_no, machine_id, customer_id, status, workflow_status, assigned_to, service_type, fault_description, remark, created_by),
        )
        return int(cur.lastrowid)

    def get_repair_order(self, repair_order_id: int, include_archived: bool = False) -> dict[str, Any] | None:
        archived_clause = "" if include_archived else " AND archived_at=''"
        return row_to_dict(
            self.conn.execute(
                f"SELECT * FROM repair_orders WHERE repair_order_id=?{archived_clause}",
                (repair_order_id,),
            ).fetchone()
        )

    def assign_repair_order(self, repair_order_id: int, engineer: str, workflow_status: str) -> None:
        self.conn.execute(
            """
            UPDATE repair_orders
            SET assigned_to=?, workflow_status=?, updated_at=CURRENT_TIMESTAMP
            WHERE repair_order_id=?
            """,
            (engineer, workflow_status, repair_order_id),
        )

    def update_repair_order_machine(self, repair_order_id: int, machine_id: int) -> None:
        self.conn.execute(
            """
            UPDATE repair_orders
            SET machine_id=?, updated_at=CURRENT_TIMESTAMP
            WHERE repair_order_id=?
            """,
            (machine_id, repair_order_id),
        )

    def assign_machine(self, machine_id: int, engineer: str) -> None:
        self.conn.execute(
            "UPDATE machines SET assigned_to=?, updated_at=CURRENT_TIMESTAMP WHERE machine_id=?",
            (engineer, machine_id),
        )

    def update_repair_order_status(self, repair_order_id: int, status: str, remark: str = "") -> None:
        self.conn.execute(
            """
            UPDATE repair_orders
            SET status=?, remark=CASE WHEN ? = '' THEN remark ELSE ? END,
                updated_at=CURRENT_TIMESTAMP,
                closed_at=CASE WHEN ? = '已结单' THEN CURRENT_TIMESTAMP ELSE closed_at END
            WHERE repair_order_id=?
            """,
            (status, remark, remark, status, repair_order_id),
        )

    def quote_repair_order(
        self,
        repair_order_id: int,
        diagnosis: str,
        quoted_amount: float,
        status: str,
        fault_detail: str = "",
        repair_solution: str = "",
        workflow_status: str = "待客户确认",
    ) -> None:
        self.conn.execute(
            """
            UPDATE repair_orders
            SET diagnosis=?, quoted_amount=?, status=?, fault_detail=?,
                repair_solution=?, workflow_status=?, updated_at=CURRENT_TIMESTAMP
            WHERE repair_order_id=?
            """,
            (diagnosis, quoted_amount, status, fault_detail, repair_solution, workflow_status, repair_order_id),
        )

    def confirm_repair_quote(self, repair_order_id: int, status: str, workflow_status: str, result: str, method: str, contact: str, remark: str) -> None:
        self.conn.execute(
            """
            UPDATE repair_orders
            SET status=?, workflow_status=?, quote_confirm_status=?, quote_confirm_method=?,
                quote_contact_person=?, quote_confirm_remark=?, quote_confirmed_at=CURRENT_TIMESTAMP,
                updated_at=CURRENT_TIMESTAMP
            WHERE repair_order_id=?
            """,
            (status, workflow_status, result, method, contact, remark, repair_order_id),
        )

    def update_repair_order_price(self, repair_order_id: int, quoted_amount: float) -> None:
        self.conn.execute(
            "UPDATE repair_orders SET quoted_amount=?, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?",
            (quoted_amount, repair_order_id),
        )

    def update_repair_order_discount(self, repair_order_id: int, discount_amount: float) -> None:
        self.conn.execute(
            "UPDATE repair_orders SET discount_amount=?, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?",
            (discount_amount, repair_order_id),
        )

    def update_repair_order_remark(self, repair_order_id: int, remark: str) -> None:
        self.conn.execute(
            "UPDATE repair_orders SET remark=?, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?",
            (remark, repair_order_id),
        )

    def archive_repair_order(self, repair_order_id: int, archived_by: str, reason: str, snapshot: dict[str, Any]) -> None:
        order = self.get_repair_order(repair_order_id)
        if not order:
            return
        order_no = str(order.get("order_no") or "")
        snapshot_json = json.dumps(snapshot, ensure_ascii=False, default=str)
        self.conn.execute(
            """
            UPDATE repair_orders
            SET status='已删除',
                archived_at=CURRENT_TIMESTAMP,
                archived_by=?,
                archive_reason=?,
                purge_after=datetime(CURRENT_TIMESTAMP, '+30 days'),
                updated_at=CURRENT_TIMESTAMP
            WHERE repair_order_id=? AND archived_at=''
            """,
            (archived_by, reason, repair_order_id),
        )
        self.conn.execute(
            """
            INSERT INTO repair_order_archives
            (repair_order_id, order_no, archived_by, archive_reason, purge_after, snapshot_json)
            VALUES (?, ?, ?, ?, datetime(CURRENT_TIMESTAMP, '+30 days'), ?)
            ON CONFLICT(repair_order_id) DO UPDATE SET
                order_no=excluded.order_no,
                archived_at=CURRENT_TIMESTAMP,
                archived_by=excluded.archived_by,
                archive_reason=excluded.archive_reason,
                purge_after=excluded.purge_after,
                snapshot_json=excluded.snapshot_json
            """,
            (repair_order_id, order_no, archived_by, reason, snapshot_json),
        )

    def get_repair_order_archive_by_order_no(self, order_no: str) -> dict[str, Any] | None:
        return row_to_dict(
            self.conn.execute(
                """
                SELECT a.*, ro.machine_id
                FROM repair_order_archives a
                JOIN repair_orders ro ON ro.repair_order_id=a.repair_order_id
                WHERE a.order_no=? AND ro.archived_at<>''
                """,
                (order_no,),
            ).fetchone()
        )

    def add_repair_item(self, repair_order_id: int, item_name: str, quantity: int, cost_amount: float, charge_amount: float, remark: str, sku_id: int | None = None) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO repair_items
            (repair_order_id, sku_id, item_name, quantity, cost_amount, charge_amount, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (repair_order_id, sku_id, item_name, quantity, cost_amount, charge_amount, remark),
        )
        return int(cur.lastrowid)

    def get_repair_item(self, repair_order_id: int, repair_item_id: int) -> dict[str, Any] | None:
        return row_to_dict(
            self.conn.execute(
                """
                SELECT ri.*, rs.sku_code, rs.fault_name, rs.solution_name, rs.model
                FROM repair_items ri
                LEFT JOIN repair_skus rs ON rs.sku_id=ri.sku_id
                WHERE ri.repair_order_id=? AND ri.repair_item_id=?
                """,
                (repair_order_id, repair_item_id),
            ).fetchone()
        )

    def update_repair_item(self, repair_order_id: int, repair_item_id: int, quantity: int, cost_amount: float, charge_amount: float, remark: str) -> None:
        self.conn.execute(
            """
            UPDATE repair_items
            SET quantity=?, cost_amount=?, charge_amount=?, remark=?
            WHERE repair_order_id=? AND repair_item_id=?
            """,
            (quantity, cost_amount, charge_amount, remark, repair_order_id, repair_item_id),
        )

    def repair_item_consumed_material_count(self, repair_order_id: int, repair_item_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM repair_material_reservations
            WHERE repair_order_id=? AND repair_item_id=? AND consumed_qty>0
            """,
            (repair_order_id, repair_item_id),
        ).fetchone()
        return int(row["count"] if row else 0)

    def delete_repair_item_reservations(self, repair_order_id: int, repair_item_id: int) -> None:
        self.conn.execute(
            """
            DELETE FROM repair_material_reservations
            WHERE repair_order_id=? AND repair_item_id=? AND consumed_qty<=0
            """,
            (repair_order_id, repair_item_id),
        )

    def delete_repair_item(self, repair_order_id: int, repair_item_id: int) -> None:
        self.conn.execute(
            "DELETE FROM repair_items WHERE repair_order_id=? AND repair_item_id=?",
            (repair_order_id, repair_item_id),
        )

    def list_repair_skus(self, include_disabled: bool = False, model: str = "", keyword: str = "") -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if not include_disabled:
            clauses.append("rs.enabled=1")
        if model:
            clauses.append("(rs.model='' OR rs.model=?)")
            params.append(model)
        if keyword:
            like = f"%{keyword}%"
            clauses.append("(rs.sku_code LIKE ? OR rs.fault_name LIKE ? OR rs.solution_name LIKE ? OR rs.remark LIKE ?)")
            params.extend([like, like, like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"""
            SELECT rs.*,
                   m.material_id,
                   m.name AS material_name,
                   m.material_code,
                   m.sku AS material_sku,
                   m.current_qty AS material_stock_qty,
                   COALESCE(m.avg_cost, 0) AS material_unit_price
            FROM repair_skus rs
            LEFT JOIN repair_fault_materials rfm ON rfm.repair_sku_id=rs.sku_id
            LEFT JOIN materials m ON m.material_id=rfm.material_id
            {where}
            GROUP BY rs.sku_id
            ORDER BY rs.enabled DESC, CASE WHEN rs.model='' THEN 1 ELSE 0 END, rs.model, rs.sku_id
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def get_repair_sku(self, sku_id: int) -> dict[str, Any] | None:
        return row_to_dict(self.conn.execute("SELECT * FROM repair_skus WHERE sku_id=?", (sku_id,)).fetchone())

    def upsert_repair_sku(self, data: dict[str, Any]) -> int:
        existing = self.conn.execute("SELECT sku_id FROM repair_skus WHERE sku_code=?", (data["sku_code"],)).fetchone()
        if existing:
            sku_id = int(existing["sku_id"])
            self.conn.execute(
                """
                UPDATE repair_skus
                SET model=?, fault_name=?, solution_name=?, cost_amount=?, charge_amount=?,
                    enabled=?, remark=?, updated_at=CURRENT_TIMESTAMP
                WHERE sku_id=?
                """,
                (
                    data.get("model", ""),
                    data["fault_name"],
                    data["solution_name"],
                    data["cost_amount"],
                    data["charge_amount"],
                    1 if data.get("enabled", True) else 0,
                    data.get("remark", ""),
                    sku_id,
                ),
            )
            return sku_id
        cur = self.conn.execute(
            """
            INSERT INTO repair_skus
            (model, sku_code, fault_name, solution_name, cost_amount, charge_amount, enabled, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("model", ""),
                data["sku_code"],
                data["fault_name"],
                data["solution_name"],
                data["cost_amount"],
                data["charge_amount"],
                1 if data.get("enabled", True) else 0,
                data.get("remark", ""),
            ),
        )
        return int(cur.lastrowid)

    def list_repair_items(self, repair_order_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT ri.*, rs.sku_code, rs.fault_name, rs.solution_name, rs.model
            FROM repair_items ri
            LEFT JOIN repair_skus rs ON rs.sku_id=ri.sku_id
            WHERE ri.repair_order_id=?
            ORDER BY ri.repair_item_id
            """,
            (repair_order_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def deliver_repair_order(self, repair_order_id: int, delivery_check: str, remark: str, status: str) -> None:
        self.conn.execute(
            """
            UPDATE repair_orders
            SET delivery_check=?, remark=CASE WHEN ? = '' THEN remark ELSE ? END,
                status=?, updated_at=CURRENT_TIMESTAMP
            WHERE repair_order_id=?
            """,
            (delivery_check, remark, remark, status, repair_order_id),
        )

    def engineer_close_repair_order(self, repair_order_id: int, remark: str) -> None:
        self.conn.execute(
            """
            UPDATE repair_orders
            SET workflow_status='待前台收费/交付', engineer_closed_at=CURRENT_TIMESTAMP,
                engineer_close_remark=CASE WHEN ? = '' THEN engineer_close_remark ELSE ? END,
                status=CASE WHEN status='处理中' THEN '待交付' ELSE status END,
                updated_at=CURRENT_TIMESTAMP
            WHERE repair_order_id=?
            """,
            (remark, remark, repair_order_id),
        )

    def create_recycle_order(self, machine_id: int, customer_id: int | None, status: str, inspection_note: str, remark: str, created_by: str) -> int:
        order_no = self.next_order_no("recycle_orders", "ZB")
        cur = self.conn.execute(
            """
            INSERT INTO recycle_orders
            (order_no, machine_id, customer_id, status, inspection_note, remark, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (order_no, machine_id, customer_id, status, inspection_note, remark, created_by),
        )
        return int(cur.lastrowid)

    def get_recycle_order(self, recycle_order_id: int) -> dict[str, Any] | None:
        return row_to_dict(self.conn.execute("SELECT * FROM recycle_orders WHERE recycle_order_id=?", (recycle_order_id,)).fetchone())

    def quote_recycle_order(self, recycle_order_id: int, inspection_result: str, quoted_amount: float, status: str) -> None:
        self.conn.execute(
            """
            UPDATE recycle_orders
            SET inspection_result=?, quoted_amount=?, status=?, updated_at=CURRENT_TIMESTAMP
            WHERE recycle_order_id=?
            """,
            (inspection_result, quoted_amount, status, recycle_order_id),
        )

    def update_recycle_order_price(self, recycle_order_id: int, quoted_amount: float) -> None:
        self.conn.execute(
            "UPDATE recycle_orders SET quoted_amount=?, updated_at=CURRENT_TIMESTAMP WHERE recycle_order_id=?",
            (quoted_amount, recycle_order_id),
        )

    def stock_in_recycle_order(self, recycle_order_id: int, paid_amount: float, status: str) -> None:
        self.conn.execute(
            """
            UPDATE recycle_orders
            SET paid_amount=?, status=?, updated_at=CURRENT_TIMESTAMP
            WHERE recycle_order_id=?
            """,
            (paid_amount, status, recycle_order_id),
        )

    def create_inventory_item(self, machine_id: int, recycle_order_id: int, status: str, cost_amount: float, sale_price: float) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO inventory_items
            (machine_id, recycle_order_id, status, cost_amount, sale_price)
            VALUES (?, ?, ?, ?, ?)
            """,
            (machine_id, recycle_order_id, status, cost_amount, sale_price),
        )
        return int(cur.lastrowid)

    def list_inventory_items(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT i.*, m.machine_no, m.imei, m.model, m.color, m.current_status
            FROM inventory_items i
            JOIN machines m ON m.machine_id = i.machine_id
            ORDER BY i.updated_at DESC, i.inventory_item_id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def get_inventory_item(self, inventory_item_id: int) -> dict[str, Any] | None:
        return row_to_dict(
            self.conn.execute(
                """
                SELECT i.*, m.machine_no, m.imei, m.model
                FROM inventory_items i
                JOIN machines m ON m.machine_id = i.machine_id
                WHERE i.inventory_item_id=?
                """,
                (inventory_item_id,),
            ).fetchone()
        )

    def mark_inventory_sold(self, inventory_item_id: int) -> None:
        self.conn.execute(
            "UPDATE inventory_items SET status='已售出', updated_at=CURRENT_TIMESTAMP WHERE inventory_item_id=?",
            (inventory_item_id,),
        )

    def create_sales_order(self, inventory_item_id: int, machine_id: int, customer_id: int | None, status: str, sale_price: float, salesperson: str, remark: str, created_by: str) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO sales_orders
            (inventory_item_id, machine_id, customer_id, status, sale_price, salesperson, remark, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (inventory_item_id, machine_id, customer_id, status, sale_price, salesperson, remark, created_by),
        )
        return int(cur.lastrowid)

    def get_sales_order(self, sales_order_id: int) -> dict[str, Any] | None:
        return row_to_dict(self.conn.execute("SELECT * FROM sales_orders WHERE sales_order_id=?", (sales_order_id,)).fetchone())

    def create_payment(self, data: dict[str, Any]) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO payments
            (source_type, source_id, direction, amount, method, payer, payee, operator, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["source_type"],
                data["source_id"],
                data["direction"],
                data["amount"],
                data.get("method", ""),
                data.get("payer", ""),
                data.get("payee", ""),
                data.get("operator", ""),
                data.get("remark", ""),
            ),
        )
        return int(cur.lastrowid)

    def payments_for_source(self, source_type: str, source_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT * FROM payments
            WHERE source_type=? AND source_id=?
            ORDER BY payment_id
            """,
            (source_type, source_id),
        ).fetchall()
        return [dict(row) for row in rows]

    def payment_total_for_source(self, source_type: str, source_id: int, direction: str | None = None) -> float:
        if direction is None:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE source_type=? AND source_id=?",
                (source_type, source_id),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE source_type=? AND source_id=? AND direction=?",
                (source_type, source_id, direction),
            ).fetchone()
        return float(row["total"] if row else 0)

    def list_payments(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM payments ORDER BY payment_id DESC LIMIT 200").fetchall()
        return [dict(row) for row in rows]

    def close_source_by_payment(self, source_type: str, source_id: int) -> int | None:
        if source_type == "repair":
            order = self.get_repair_order(source_id)
            if not order:
                return None
            if self.payment_total_for_source("repair", source_id, "收入") < float(order["quoted_amount"]):
                return int(order["machine_id"])
            self.conn.execute(
                "UPDATE repair_orders SET status='已结单', closed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?",
                (source_id,),
            )
            self.close_machine(int(order["machine_id"]), "已结单")
            return int(order["machine_id"])
        if source_type == "sale":
            order = self.get_sales_order(source_id)
            if not order:
                return None
            self.conn.execute("UPDATE sales_orders SET status='已结单', closed_at=CURRENT_TIMESTAMP WHERE sales_order_id=?", (source_id,))
            self.close_machine(int(order["machine_id"]), "已结单")
            return int(order["machine_id"])
        if source_type == "recycle":
            order = self.get_recycle_order(source_id)
            return int(order["machine_id"]) if order else None
        return None

    def repair_order_events(self, machine_id: int, repair_order_id: int) -> list[dict[str, Any]]:
        item_ids = [int(item["repair_item_id"]) for item in self.list_repair_items(repair_order_id)]
        note_ids = [int(note["note_id"]) for note in self.list_repair_order_notes(repair_order_id, include_deleted=True)]
        item_filter = ""
        params: list[Any] = [machine_id, repair_order_id]
        if item_ids:
            placeholders = ",".join("?" for _ in item_ids)
            item_filter = f" OR (related_type='repair_item' AND related_id IN ({placeholders}))"
            params.extend(item_ids)
        note_filter = ""
        if note_ids:
            placeholders = ",".join("?" for _ in note_ids)
            note_filter = f" OR (related_type='repair_note' AND related_id IN ({placeholders}))"
            params.extend(note_ids)
        rows = self.conn.execute(
            f"""
            SELECT * FROM machine_events
            WHERE machine_id=? AND (
                (related_type='repair' AND related_id=?)
                {item_filter}
                {note_filter}
                OR related_type='payment'
                OR (related_type='machine' AND title IN ('编辑订单', '缂栬緫璁㈠崟'))
            )
            ORDER BY event_id
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def repair_order_detail(self, repair_order_id: int, include_archived: bool = False) -> dict[str, Any] | None:
        order = self.get_repair_order(repair_order_id, include_archived=include_archived)
        if not order:
            return None
        machine_id = int(order["machine_id"])
        customer_id = order.get("customer_id")
        order["machine"] = self.get_machine(machine_id)
        order["customer"] = self.get_customer(int(customer_id)) if customer_id else None
        order["items"] = self.list_repair_items(repair_order_id)
        order["payments"] = self.payments_for_source("repair", repair_order_id)
        order["events"] = self.repair_order_events(machine_id, repair_order_id)
        order["inspections"] = self.list_repair_order_inspections(repair_order_id)
        order["notes"] = self.list_repair_order_notes(repair_order_id)
        return order

    def add_repair_order_photo(self, repair_order_id: int, stage: str, filename: str, url: str, uploaded_by: str) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO repair_order_photos (repair_order_id, stage, filename, url, uploaded_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (repair_order_id, stage, filename, url, uploaded_by),
        )
        return int(cur.lastrowid)

    def list_repair_order_photos(self, repair_order_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM repair_order_photos WHERE repair_order_id=? ORDER BY photo_id",
            (repair_order_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_repair_order_inspections(self, repair_order_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM repair_order_inspections WHERE repair_order_id=? ORDER BY stage, inspection_id",
            (repair_order_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_repair_order_notes(self, repair_order_id: int, include_deleted: bool = False) -> list[dict[str, Any]]:
        clause = "" if include_deleted else " AND is_deleted=0"
        rows = self.conn.execute(
            f"SELECT * FROM repair_order_notes WHERE repair_order_id=?{clause} ORDER BY note_id",
            (repair_order_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_repair_order_note(self, note_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM repair_order_notes WHERE note_id=?", (note_id,)).fetchone()
        return dict(row) if row else None

    def add_repair_order_note(self, repair_order_id: int, note_type: str, content: str, created_by: str) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO repair_order_notes (repair_order_id, note_type, content, created_by)
            VALUES (?, ?, ?, ?)
            """,
            (repair_order_id, note_type, content, created_by),
        )
        return int(cur.lastrowid)

    def update_repair_order_note(self, note_id: int, note_type: str, content: str, updated_by: str) -> None:
        self.conn.execute(
            """
            UPDATE repair_order_notes
            SET note_type=?, content=?, updated_by=?, updated_at=CURRENT_TIMESTAMP
            WHERE note_id=? AND is_deleted=0
            """,
            (note_type, content, updated_by, note_id),
        )

    def delete_repair_order_note(self, note_id: int, deleted_by: str, reason: str = "") -> None:
        self.conn.execute(
            """
            UPDATE repair_order_notes
            SET is_deleted=1, deleted_by=?, deleted_at=CURRENT_TIMESTAMP, deleted_reason=?
            WHERE note_id=? AND is_deleted=0
            """,
            (deleted_by, reason, note_id),
        )

    def replace_repair_order_inspections(self, repair_order_id: int, stage: str, items: list[dict[str, Any]], updated_by: str) -> None:
        self.conn.execute("DELETE FROM repair_order_inspections WHERE repair_order_id=? AND stage=?", (repair_order_id, stage))
        self.conn.executemany(
            """
            INSERT INTO repair_order_inspections (repair_order_id, stage, item, abnormal, note, updated_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    repair_order_id,
                    stage,
                    str(item.get("item") or ""),
                    1 if item.get("abnormal") else 0,
                    str(item.get("note") or ""),
                    updated_by,
                )
                for item in items
                if str(item.get("item") or "").strip()
            ],
        )

    def add_machine_event(self, machine_id: int, event_type: str, title: str, detail: str, operator: str, related_type: str = "", related_id: int | None = None) -> None:
        self.conn.execute(
            """
            INSERT INTO machine_events
            (machine_id, event_type, title, detail, operator, related_type, related_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (machine_id, event_type, title, detail, operator, related_type, related_id),
        )

    def machine_timeline(self, machine_id: int) -> dict[str, Any]:
        machine = self.get_machine(machine_id)
        events = self.conn.execute(
            "SELECT * FROM machine_events WHERE machine_id=? ORDER BY event_id",
            (machine_id,),
        ).fetchall()
        repairs = self.conn.execute("SELECT * FROM repair_orders WHERE machine_id=? AND archived_at='' ORDER BY repair_order_id", (machine_id,)).fetchall()
        repair_items: list[dict[str, Any]] = []
        repair_payments: list[dict[str, Any]] = []
        for row in repairs:
            repair_id = int(row["repair_order_id"])
            repair_items.extend(self.list_repair_items(repair_id))
            repair_payments.extend(self.payments_for_source("repair", repair_id))
        recycle = self.conn.execute("SELECT * FROM recycle_orders WHERE machine_id=? ORDER BY recycle_order_id", (machine_id,)).fetchall()
        inventory = self.conn.execute("SELECT * FROM inventory_items WHERE machine_id=? ORDER BY inventory_item_id", (machine_id,)).fetchall()
        sales = self.conn.execute("SELECT * FROM sales_orders WHERE machine_id=? ORDER BY sales_order_id", (machine_id,)).fetchall()
        notes = self.conn.execute("SELECT * FROM machine_notes WHERE machine_id=? ORDER BY note_id", (machine_id,)).fetchall()
        customer_id = machine.get("customer_id") if machine else None
        if not customer_id:
            for rows in (repairs, recycle, sales):
                customer_id = next((row["customer_id"] for row in rows if row["customer_id"]), None)
                if customer_id:
                    break
        customer = self.get_customer(int(customer_id)) if customer_id else None
        return {
            "machine": machine,
            "customer": customer,
            "events": [dict(row) for row in events],
            "notes": [dict(row) for row in notes],
            "repair_orders": [dict(row) for row in repairs],
            "repair_items": repair_items,
            "repair_payments": repair_payments,
            "recycle_orders": [dict(row) for row in recycle],
            "inventory_items": [dict(row) for row in inventory],
            "sales_orders": [dict(row) for row in sales],
        }

    def machine_reports(self) -> dict[str, Any]:
        status_rows = self.conn.execute(
            "SELECT current_status, COUNT(*) AS count FROM machines GROUP BY current_status ORDER BY current_status"
        ).fetchall()
        payment_rows = self.conn.execute(
            "SELECT direction, COALESCE(SUM(amount), 0) AS amount FROM payments GROUP BY direction"
        ).fetchall()
        inventory = self.list_inventory_items()
        return {
            "machine_status_counts": [dict(row) for row in status_rows],
            "payment_totals": [dict(row) for row in payment_rows],
            "inventory_count": len([item for item in inventory if item["status"] != "已售出"]),
            "inventory_cost": sum(float(item["cost_amount"]) for item in inventory if item["status"] != "已售出"),
            "inventory": inventory,
        }
