"""Maintain repair-SKU defaults from recorded repair-order line prices.

This is deliberately a one-way maintenance utility: it updates only
``repair_skus``.  Historical repair orders and their line items are snapshotted
before the transaction and verified unchanged afterwards.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "mis_mvp.sqlite3"


def normalized(value: str) -> str:
    return "".join(str(value or "").lower().split())


def semantic_match(sku: sqlite3.Row, item_name: str) -> bool:
    """Accept only an item name that agrees with the selected SKU's meaning."""
    code = str(sku["sku_code"])
    expected = {
        "SCREEN-OLED": ("屏幕", "oled"),
        "BATTERY": ("电池",),
        "CHARGE-FLEX": ("充电", "尾插"),
        "BOARD-DIAG": ("主板", "不开机"),
        "WATER-CLEAN": ("进水",),
        "SSD-521": ("内存升级512", "512gb"),
        "SSD-256": ("内存升级256", "256gb"),
        "iPad_BATTERY": ("电池",),
        "ip-zb1401": ("不开机", "主板"),
        "PCB_CNC": ("主板打磨", "板底打磨"),
        "sj": ("软件", "刷机", "解锁"),
        "iPhone_BATTERY_01": ("电池",),
        "KT": ("无信号", "卡贴"),
        "HK_001": ("中框", "后壳"),
        "HK_002": ("后玻璃",),
    }.get(code)
    if not expected and code.startswith("AUTO-"):
        expected = (str(sku["fault_name"]), str(sku["solution_name"]))
    if not expected:
        expected = (str(sku["fault_name"]), str(sku["solution_name"]))
    text = normalized(item_name)
    return any(normalized(token) and normalized(token) in text for token in expected)


def table_fingerprint(conn: sqlite3.Connection, table: str, key: str) -> str:
    rows = [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY {key}")]
    encoded = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def unique_model_code(base_code: str, model: str) -> str:
    """Readable and deterministic; SQLite has no length restriction for TEXT."""
    return f"{base_code}::{model}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    db_path = args.db.resolve()
    if not db_path.is_file():
        raise SystemExit(f"Database not found: {db_path}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}.before-sku-price-maintenance-{timestamp}{db_path.suffix}")
    report_path = db_path.with_name(f"sku-price-maintenance-{timestamp}.json")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"Database integrity check failed before maintenance: {integrity}")
        before = {
            "repair_orders": table_fingerprint(conn, "repair_orders", "repair_order_id"),
            "repair_items": table_fingerprint(conn, "repair_items", "repair_item_id"),
        }
        sku_by_id = {row["sku_id"]: row for row in conn.execute("SELECT * FROM repair_skus")}
        samples: dict[int, list[dict[str, Any]]] = defaultdict(list)
        excluded: list[dict[str, Any]] = []
        query = """
            SELECT ri.repair_item_id, ri.sku_id, ri.item_name, ri.cost_amount,
                   ri.charge_amount, ri.created_at AS item_created_at,
                   ro.order_no, m.model
            FROM repair_items ri
            JOIN repair_orders ro ON ro.repair_order_id=ri.repair_order_id
            JOIN machines m ON m.machine_id=ro.machine_id
            ORDER BY ri.created_at, ri.repair_item_id
        """
        for row in conn.execute(query):
            item = dict(row)
            sku = sku_by_id.get(item["sku_id"])
            reason = ""
            if sku is None:
                reason = "未关联现存故障代码"
            elif not str(item["model"] or "").strip():
                reason = "缺少机型"
            elif float(item["cost_amount"] or 0) == 0 and float(item["charge_amount"] or 0) == 0:
                reason = "零价明细"
            elif not semantic_match(sku, str(item["item_name"])):
                reason = "故障代码与明细名称语义不一致"
            if reason:
                excluded.append({**item, "reason": reason})
            else:
                samples[int(item["sku_id"])].append(item)

        changes: list[dict[str, Any]] = []
        if not args.dry_run:
            shutil.copy2(db_path, backup_path)
            conn.execute("BEGIN IMMEDIATE")
        for sku_id, rows in samples.items():
            source = sku_by_id[sku_id]
            by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                by_model[str(row["model"]).strip()].append(row)
            part_median = float(statistics.median(float(row["cost_amount"]) for row in rows))
            labor_median = float(statistics.median(float(row["charge_amount"]) for row in rows))
            if not str(source["model"] or "").strip():
                changes.append({"action": "update_generic_median", "sku_code": source["sku_code"], "model": "", "cost_amount": part_median, "charge_amount": labor_median, "sample_count": len(rows)})
                if not args.dry_run:
                    conn.execute("UPDATE repair_skus SET cost_amount=?, charge_amount=?, updated_at=CURRENT_TIMESTAMP WHERE sku_id=?", (part_median, labor_median, sku_id))

            for model, model_rows in by_model.items():
                latest = max(model_rows, key=lambda row: (str(row["item_created_at"]), int(row["repair_item_id"])))
                cost_amount, charge_amount = float(latest["cost_amount"]), float(latest["charge_amount"])
                target_code = str(source["sku_code"]) if str(source["model"] or "").strip() == model else unique_model_code(str(source["sku_code"]), model)
                existing = conn.execute("SELECT sku_id FROM repair_skus WHERE sku_code=?", (target_code,)).fetchone()
                action = "update_model_specific" if existing else "create_model_specific"
                changes.append({"action": action, "sku_code": target_code, "model": model, "source_sku_code": source["sku_code"], "source_order_no": latest["order_no"], "cost_amount": cost_amount, "charge_amount": charge_amount})
                if args.dry_run:
                    continue
                if existing:
                    conn.execute("UPDATE repair_skus SET model=?, fault_name=?, solution_name=?, cost_amount=?, charge_amount=?, enabled=?, remark=?, updated_at=CURRENT_TIMESTAMP WHERE sku_id=?", (model, source["fault_name"], source["solution_name"], cost_amount, charge_amount, source["enabled"], source["remark"], existing["sku_id"]))
                else:
                    remark = f"真实订单报价维护；来源故障代码 {source['sku_code']}"
                    conn.execute("INSERT INTO repair_skus (model, sku_code, fault_name, solution_name, cost_amount, charge_amount, enabled, remark) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (model, target_code, source["fault_name"], source["solution_name"], cost_amount, charge_amount, source["enabled"], remark))

        if not args.dry_run:
            duplicate_codes = conn.execute("SELECT sku_code FROM repair_skus GROUP BY sku_code HAVING COUNT(*) > 1").fetchall()
            invalid_prices = conn.execute("SELECT sku_id FROM repair_skus WHERE cost_amount < 0 OR charge_amount < 0").fetchall()
            if duplicate_codes or invalid_prices:
                raise RuntimeError("Post-update SKU validation failed")
            after = {
                "repair_orders": table_fingerprint(conn, "repair_orders", "repair_order_id"),
                "repair_items": table_fingerprint(conn, "repair_items", "repair_item_id"),
            }
            if before != after:
                raise RuntimeError("Historical repair order data changed; restore the backup immediately")
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"Database integrity check failed after maintenance: {integrity}")
            conn.commit()
        else:
            after = before

        report = {"database": str(db_path), "dry_run": args.dry_run, "backup": None if args.dry_run else str(backup_path), "integrity_check": integrity, "historical_fingerprints": {"before": before, "after": after}, "changes": changes, "excluded": excluded}
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"backup": report["backup"], "report": str(report_path), "changes": len(changes), "excluded": len(excluded)}, ensure_ascii=False))
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
