from __future__ import annotations

import json
import sqlite3
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from .auth import hash_password, permissions_for, require_permission
from .config import ROOT_DIR
from .order_numbers import repair_order_date_key, repair_order_no
from .models import (
    BusinessLine,
    CustomerInput,
    DeviceModelInput,
    DeviceStatus,
    LoginInput,
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
    MaterialReturnInspectInput,
    OrderStatus,
    PaymentDirection,
    PaymentInput,
    PriceChangeInput,
    PurchaseInput,
    RecycleOrderInput,
    RecycleQuoteInput,
    RepairAssignInput,
    RepairInput,
    RepairDeliverInput,
    RepairEngineerCloseInput,
    RepairInspectionInput,
    RepairItemInput,
    RepairOrderInput,
    RepairOrderNoteDeleteInput,
    RepairOrderNoteInput,
    RepairOrderNoteUpdateInput,
    RepairRemarkInput,
    RepairOrderStatusInput,
    RepairQuoteConfirmInput,
    RepairQuoteInput,
    RepairSkuInput,
    RepairWorkflowActionInput,
    RepairFaultMaterialInput,
    RepairStatusInput,
    Role,
    SalesOrderInput,
    SellDeviceInput,
    SettlementInput,
    SettlementStatus,
    StockInInput,
    StockAdjustmentInput,
    StockCountInput,
    User,
    WarehouseAreaInput,
    WarehouseLocationInput,
)
from .repository import Repository


class BusinessError(ValueError):
    pass


REPAIR_MODULE_DEFINITIONS = [
    ("create", "建单", 1, "待开始", "frontdesk"),
    ("quote", "检测报价", 2, "锁定", "engineer"),
    ("repair_qc", "维修与质检", 3, "锁定", "engineer"),
    ("payment", "收费结单", 4, "锁定", "frontdesk"),
]

REPAIR_MODULE_ALIASES = {
    "create": "create",
    "quote": "quote",
    "repair": "repair_qc",
    "qc": "repair_qc",
    "repair_qc": "repair_qc",
    "payment": "payment",
}

REPAIR_ACTION_ALIASES = {
    "complete": "complete",
    "start": "start",
    "save": "save",
    "submit": "submit",
    "confirm": "confirm",
    "register": "register",
    "prepay": "prepay",
    "credit": "credit",
    "reopen": "reopen",
    "return": "return",
    "review": "review",
}


class MisService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.repo = Repository(conn)

    def login(self, data: LoginInput) -> dict[str, Any]:
        user = self.repo.get_user(data.username)
        if not user or user["password_hash"] != hash_password(data.password):
            raise BusinessError("用户名或密码错误")
        role = Role(user["role"])
        return {"username": data.username, "role": role.value}

    def get_user(self, username: str) -> User:
        user = self.repo.get_user(username)
        if not user:
            raise BusinessError("用户不存在")
        return User(username=user["username"], role=Role(user["role"]))

    def user_profile(self, user: User) -> dict[str, Any]:
        return {
            "username": user.username,
            "role": user.role.value,
            "permissions": list(permissions_for(user.role)),
        }

    def _allowed(self, user: User, permission: str) -> None:
        require_permission(user.role, permission)

    def _log_success(self, user: User, action: str, target_type: str, target_id: str, **kwargs: Any) -> None:
        self.repo.add_log(user.username, user.role.value, action, target_type, target_id, "success", **kwargs)

    def _customer_id(self, customer_id: int | None, customer: CustomerInput | None) -> int | None:
        if customer:
            return self.repo.upsert_customer(customer)
        return customer_id

    def _machine_no(self, imei: str = "") -> str:
        if imei:
            suffix = imei[-6:] if len(imei) >= 6 else imei
            return f"MC-{suffix}-{uuid4().hex[:4].upper()}"
        return f"TMP-{uuid4().hex[:10].upper()}"

    def _ensure_machine(self, user: User, machine_id: int | None, machine: MachineInput | None, default_line: BusinessLine) -> dict[str, Any]:
        if machine_id:
            existing = self.repo.get_machine(machine_id)
            if not existing:
                raise BusinessError("机器档案不存在")
            return existing
        if not machine:
            raise BusinessError("必须提供机器档案或 machine_id")
        return self.create_machine(user, machine, default_line=default_line)

    def create_machine(self, user: User, data: MachineInput, default_line: BusinessLine | None = None) -> dict[str, Any]:
        self._allowed(user, "machine:create")
        imei = data.imei.strip()
        if imei and self.repo.get_machine_by_imei(imei):
            raise BusinessError("IMEI 已存在，不能重复创建机器档案")
        customer_id = self._customer_id(data.customer_id, data.customer)
        source_type = (data.source_type or default_line or BusinessLine.repair).value
        machine_id = self.repo.create_machine(
            {
                "machine_no": self._machine_no(imei),
                "imei": imei,
                "serial": data.serial,
                "model": data.model,
                "memory": data.memory,
                "color": data.color,
                "condition": data.condition,
                "source_type": source_type,
                "current_status": MachineStatus.arrived.value,
                "customer_id": customer_id,
                "created_by": user.username,
                "remark": data.remark,
            }
        )
        self.repo.add_machine_event(machine_id, "machine", "机器到店建档", data.model, user.username, "machine", machine_id)
        self._log_success(user, "machine:create", "machine", str(machine_id), imei=imei, customer_id=customer_id, request_summary=data.model)
        self.conn.commit()
        return self.repo.get_machine(machine_id) or {}

    def search_machines(self, user: User, keyword: str = "") -> list[dict[str, Any]]:
        self._allowed(user, "machine:read")
        assigned_to = user.username if user.role == Role.engineer else None
        return self.repo.search_machines(keyword, assigned_to=assigned_to)

    def machine_timeline(self, user: User, machine_id: int) -> dict[str, Any]:
        self._allowed(user, "machine:read")
        timeline = self.repo.machine_timeline(machine_id)
        if not timeline["machine"]:
            raise BusinessError("机器档案不存在")
        if user.role == Role.engineer:
            assigned = timeline["machine"].get("assigned_to") or ""
            repair_assigned = any(order.get("assigned_to") == user.username for order in timeline.get("repair_orders", []))
            if assigned != user.username and not repair_assigned:
                raise PermissionError("工程师只能查看指派给自己的订单")
        return timeline

    def update_machine(self, user: User, machine_id: int, data: MachineUpdateInput) -> dict[str, Any]:
        self._allowed(user, "machine:update")
        machine = self.repo.get_machine(machine_id)
        if not machine:
            raise BusinessError("机器档案不存在")
        imei = data.imei.strip()
        existing = self.repo.get_machine_by_imei(imei) if imei else None
        if existing and int(existing["machine_id"]) != machine_id:
            raise BusinessError("IMEI 已存在，不能重复使用")
        customer_before = self.repo.get_customer(int(machine["customer_id"])) if machine.get("customer_id") else None
        customer_id = machine.get("customer_id")
        if data.customer:
            if data.customer_id:
                existing_customer = self.repo.get_customer(data.customer_id)
                if not existing_customer:
                    raise BusinessError("客户档案不存在")
                customer_id = data.customer_id
                customer_before = existing_customer
                self.repo.update_customer(customer_id, data.customer)
            else:
                customer_id = self.repo.upsert_customer(data.customer)
        payload = {
            "imei": imei,
            "serial": data.serial,
            "model": data.model,
            "memory": data.memory,
            "color": data.color,
            "condition": data.condition,
            "source_type": data.source_type.value if data.source_type else "",
            "current_status": data.current_status.value,
            "customer_id": customer_id,
        }
        changes = []
        labels = {
            "imei": "IMEI",
            "serial": "序列号",
            "model": "机型",
            "memory": "内存",
            "color": "颜色",
            "condition": "机况",
            "source_type": "业务线",
            "current_status": "状态",
            "customer_id": "客户",
        }
        for key, label in labels.items():
            before = machine.get(key) or ""
            after = payload.get(key) or ""
            if str(before) != str(after):
                changes.append(f"{label}：{before or '空'} → {after or '空'}")
        if data.customer:
            customer_labels = {
                "name": "客户姓名",
                "phone": "客户电话",
                "category": "客户类型",
            }
            for key, label in customer_labels.items():
                before = (customer_before or {}).get(key) or ""
                after = getattr(data.customer, key) or ""
                if str(before) != str(after):
                    changes.append(f"{label}：{before or '空'} → {after or '空'}")
        if not changes:
            return machine
        self.repo.update_machine(machine_id, payload)
        detail = "；".join(changes)
        self.repo.add_machine_event(machine_id, "machine", "编辑订单", detail, user.username, "machine", machine_id)
        self._log_success(user, "machine:update", "machine", str(machine_id), imei=imei, customer_id=customer_id, request_summary=detail)
        self.conn.commit()
        return self.repo.get_machine(machine_id) or {}

    def add_machine_note(self, user: User, machine_id: int, data: MachineNoteInput) -> dict[str, Any]:
        self._allowed(user, "machine:update")
        machine = self.repo.get_machine(machine_id)
        if not machine:
            raise BusinessError("机器档案不存在")
        content = data.content.strip()
        if not content:
            raise BusinessError("备注内容不能为空")
        note_id = self.repo.add_machine_note(machine_id, content, user.username)
        self._log_success(user, "machine:note", "machine", str(machine_id), imei=machine.get("imei") or "", customer_id=machine.get("customer_id"), request_summary=content)
        self.conn.commit()
        return {"note_id": note_id, "machine_id": machine_id, "content": content, "operator": user.username}

    def delete_machine(self, user: User, machine_id: int) -> dict[str, Any]:
        self._allowed(user, "machine:delete")
        machine = self.repo.get_machine(machine_id)
        if not machine:
            raise BusinessError("机器档案不存在")
        summary = f"{machine.get('machine_no')} / {machine.get('model')}"
        self.repo.delete_machine(machine_id)
        self._log_success(user, "machine:delete", "machine", str(machine_id), imei=machine.get("imei") or "", customer_id=machine.get("customer_id"), request_summary=summary)
        self.conn.commit()
        return {"machine_id": machine_id, "deleted": True}

    def _repair_machine_status(self, status: OrderStatus) -> MachineStatus:
        mapping = {
            OrderStatus.opened: MachineStatus.diagnosing,
            OrderStatus.diagnosing: MachineStatus.diagnosing,
            OrderStatus.quoted: MachineStatus.quoted,
            OrderStatus.processing: MachineStatus.repairing,
            OrderStatus.ready: MachineStatus.ready_for_delivery,
            OrderStatus.delivered: MachineStatus.delivered,
            OrderStatus.closed: MachineStatus.closed,
        }
        return mapping.get(status, MachineStatus.diagnosing)

    def _repair_order_status(self, order: dict[str, Any]) -> OrderStatus:
        try:
            return OrderStatus(order["status"])
        except ValueError as exc:
            raise BusinessError(f"维修单状态异常：{order['status']}") from exc

    def _ensure_repair_transition(self, order: dict[str, Any], target: OrderStatus, allowed_from: set[OrderStatus]) -> None:
        current = self._repair_order_status(order)
        if current in {OrderStatus.closed, OrderStatus.cancelled}:
            raise BusinessError("维修单已结束，不能继续操作")
        if current not in allowed_from:
            allowed = "、".join(status.value for status in allowed_from)
            raise BusinessError(f"维修单当前为 {current.value}，只能从 {allowed} 进入 {target.value}")

    def _ensure_engineer_owns_repair(self, user: User, order: dict[str, Any]) -> None:
        if user.role == Role.engineer and order.get("assigned_to") != user.username:
            raise PermissionError("工程师只能处理指派给自己的订单")

    def _ensure_frontdesk_or_admin(self, user: User) -> None:
        if user.role not in {Role.admin, Role.boss, Role.frontdesk, Role.staff}:
            raise PermissionError("当前角色不能执行前台协作动作")

    def _repair_order_response(self, repair_order_id: int) -> dict[str, Any]:
        detail = self.repo.repair_order_detail(repair_order_id)
        if not detail:
            return {}
        detail["order_no"] = detail.get("order_no") or repair_order_no(repair_order_date_key(detail.get("created_at")), 1)
        detail["available_actions"] = self._repair_available_actions(detail)
        return detail

    def _repair_available_actions(self, order: dict[str, Any]) -> list[str]:
        status = self._repair_order_status(order)
        actions_by_status = {
            OrderStatus.opened: ["assign", "start_diagnosis", "cancel"],
            OrderStatus.diagnosing: ["quote", "cancel"],
            OrderStatus.quoted: ["confirm_quote", "cancel"],
            OrderStatus.processing: ["add_item", "engineer_close", "mark_ready", "cancel"],
            OrderStatus.ready: ["deliver", "engineer_close", "cancel"],
            OrderStatus.delivered: ["payment"],
        }
        return actions_by_status.get(status, [])

    def _normalize_inspection_input(self, data: RepairInspectionInput) -> tuple[str, list[dict[str, Any]], str]:
        stage = data.stage.strip().lower()
        if stage not in {"pre", "post"}:
            raise BusinessError("检测阶段必须是 pre 或 post")
        note = data.note.strip()
        normalized_items: list[dict[str, Any]] = []
        for item in data.items:
            name = item.item.strip()
            if not name:
                continue
            normalized_items.append({"item": name, "abnormal": bool(item.abnormal), "note": note})
        has_other_abnormal = any(row["item"] == "其他异常" and row["abnormal"] for row in normalized_items)
        if has_other_abnormal and not note:
            raise BusinessError("选择其他异常后必须填写备注")
        return stage, normalized_items, note

    def _input_has_field(self, data: Any, field: str) -> bool:
        return field in getattr(data, "model_fields_set", set())

    def create_repair_order(self, user: User, data: RepairOrderInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:create")
        repair_items: list[dict[str, Any]] = []
        for item in data.repair_items:
            sku = self.repo.get_repair_sku(item.sku_id) if item.sku_id else None
            if item.sku_id and (not sku or not int(sku.get("enabled", 1))):
                raise BusinessError("维修 SKU 不存在或已停用")
            item_name = item.item_name
            cost_amount = float(item.cost_amount or 0)
            charge_amount = float(item.charge_amount or 0)
            if sku:
                item_name = item_name or str(sku["solution_name"])
                if not self._input_has_field(item, "cost_amount"):
                    cost_amount = float(sku["cost_amount"] or 0)
                if not self._input_has_field(item, "charge_amount"):
                    charge_amount = float(sku["charge_amount"] or 0)
            repair_items.append(
                {
                    "sku_id": item.sku_id,
                    "item_name": item_name,
                    "quantity": int(item.quantity or 1),
                    "cost_amount": cost_amount,
                    "charge_amount": charge_amount,
                    "remark": item.remark,
                }
            )
        inspection_payloads = [self._normalize_inspection_input(item) for item in data.inspections]
        customer_id = self._customer_id(data.customer_id, data.customer)
        machine = self._ensure_machine(user, data.machine_id, data.machine, BusinessLine.repair)
        if not customer_id:
            customer_id = machine.get("customer_id")
        machine_id = int(machine["machine_id"])
        assigned_to = user.username if user.role == Role.engineer else ""
        workflow_status = "工程师待检测" if assigned_to else "待指派工程师"
        order_id = self.repo.create_repair_order(
            machine_id,
            customer_id,
            OrderStatus.opened.value,
            data.fault_description,
            data.remark,
            user.username,
            workflow_status,
            assigned_to,
        )
        self.repo.update_machine_status(machine_id, MachineStatus.diagnosing.value, BusinessLine.repair.value)
        self.repo.add_machine_event(machine_id, "repair", "维修开单", data.fault_description, user.username, "repair", order_id)
        quoted_amount = 0.0
        for item in repair_items:
            item_id = self.repo.add_repair_item(
                order_id,
                item["item_name"],
                item["quantity"],
                item["cost_amount"],
                item["charge_amount"],
                item["remark"],
                item["sku_id"],
            )
            quoted_amount += (float(item["cost_amount"]) + float(item["charge_amount"])) * int(item["quantity"])
            self.repo.add_machine_event(machine_id, "repair", "维修项目", f"{item['item_name']} x{item['quantity']}", user.username, "repair_item", item_id)
        if repair_items:
            self.repo.update_repair_order_price(order_id, quoted_amount)
        for note in data.notes:
            note_type = note.note_type.strip() or "内部备注"
            content = note.content.strip()
            if not content:
                continue
            note_id = self.repo.add_repair_order_note(order_id, note_type, content, user.username)
            self.repo.add_machine_event(machine_id, "repair", "新增工单备注", f"{note_type}：{content}", user.username, "repair_note", note_id)
        for log in data.note_logs:
            title = log.title.strip()
            if title:
                self.repo.add_machine_event(machine_id, "repair", title, log.detail.strip(), user.username, "repair", order_id)
        for stage, normalized_items, note in inspection_payloads:
            self.repo.replace_repair_order_inspections(order_id, stage, normalized_items, user.username)
            abnormal_items = [row["item"] for row in normalized_items if row["abnormal"]]
            title = "更新维修前检测" if stage == "pre" else "更新维修后检测"
            detail = "、".join(abnormal_items) if abnormal_items else "无异常功能"
            if note:
                detail = f"{detail}；备注：{note}"
            self.repo.add_machine_event(machine_id, "repair", title, detail, user.username, "repair", order_id)
        if assigned_to:
            self.repo.assign_machine(machine_id, assigned_to)
            self.repo.add_machine_event(machine_id, "repair", "指派工程师", f"系统自动指派给 {assigned_to}", user.username, "repair", order_id)
        for key, name, sequence, _default_status, owner_role in REPAIR_MODULE_DEFINITIONS:
            self.repo.ensure_repair_order_module(
                order_id,
                {
                    "module_key": key,
                    "module_name": name,
                    "sequence": sequence,
                    "status": "待开始" if key == "create" else "锁定",
                    "owner_role": owner_role,
                    "blocked_reason": "" if key == "create" else "等待建单模块完成",
                },
            )
        self._log_success(user, "repair_order:create", "repair_order", str(order_id), customer_id=customer_id, request_summary=data.fault_description)
        self.conn.commit()
        return self._repair_order_response(order_id)

    def list_repair_skus(self, user: User, model: str = "", keyword: str = "") -> list[dict[str, Any]]:
        self._allowed(user, "repair_sku:read")
        return self.repo.list_repair_skus(include_disabled=user.role in {Role.admin, Role.boss, Role.staff}, model=model, keyword=keyword)

    def list_device_models(self, user: User, keyword: str = "", enabled_only: bool = False) -> list[dict[str, Any]]:
        self._allowed(user, "device_model:read")
        return self.repo.list_device_models(keyword=keyword, enabled_only=enabled_only)

    def upsert_device_model(self, user: User, data: DeviceModelInput) -> dict[str, Any]:
        self._allowed(user, "device_model:write")
        device_model_id = self.repo.upsert_device_model(data.model_dump())
        self._log_success(user, "device_model:upsert", "device_model", str(device_model_id), request_summary=data.model_name)
        self.conn.commit()
        return self.repo.get_device_model(device_model_id) or {}

    def _rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def _one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _repair_unknown_fields(self, order: dict[str, Any]) -> list[str]:
        checks = [
            ("工程师", order.get("assigned_to")),
            ("付款方式", order.get("method")),
            ("流水号", order.get("transaction_no")),
            ("财务确认人", order.get("confirmed_by")),
        ]
        if float(order.get("quoted_amount") or 0) == 0 and "待补" in (order.get("remark") or ""):
            checks.append(("金额", ""))
        return [label for label, value in checks if not str(value or "").strip()]

    def repair_workbench(self, user: User) -> dict[str, Any]:
        self._allowed(user, "repair_order:read")
        orders = self._rows(
            """
            SELECT ro.*, m.machine_no, m.imei, m.serial, m.model, m.memory, m.color,
                   m.current_status, c.name AS linked_customer_name, c.phone AS customer_phone,
                   c.category AS linked_customer_type
            FROM repair_orders ro
            JOIN machines m ON m.machine_id = ro.machine_id
            LEFT JOIN customers c ON c.customer_id = ro.customer_id
            ORDER BY ro.updated_at DESC, ro.repair_order_id DESC
            """
        )
        for order in orders:
            order["order_no"] = order.get("order_no") or repair_order_no(repair_order_date_key(order.get("created_at")), 1)
            order["customer_name"] = order.get("customer_name") or order.get("linked_customer_name") or "待补"
            order["customer_type"] = order.get("customer_type") or order.get("linked_customer_type") or "待确认"
            order["payment_status"] = order.get("payment_status") or "未收款"
            order["settlement_status"] = order.get("settlement_status") or "未结"
            order["unknown_fields"] = self._repair_unknown_fields(order)
            order["is_overdue"] = bool(order.get("due_at")) and not order.get("closed_at") and order.get("status") not in {"已完结", "已结单"}
        return {
            "orders": orders,
            "status_cards": self._rows(
                """
                SELECT status, payment_status, settlement_status, COUNT(*) AS count,
                       COALESCE(SUM(quoted_amount), 0) AS quoted_amount
                FROM repair_orders
                GROUP BY status, payment_status, settlement_status
                ORDER BY status, payment_status
                """
            ),
            "finance_pending": self._rows(
                """
                SELECT p.*, ro.order_no, ro.customer_name
                FROM payments p
                LEFT JOIN repair_orders ro ON ro.repair_order_id = p.source_id AND p.source_type='repair'
                WHERE p.source_type='repair' AND p.status='已付款待财务确认'
                ORDER BY p.paid_at DESC, p.payment_id DESC
                """
            ),
            "receivable_summary": self._rows(
                """
                SELECT customer_name, counter_no, receivable_type, status, COUNT(*) AS count,
                       COALESCE(SUM(amount), 0) AS amount
                FROM receivables
                WHERE status <> '已结'
                GROUP BY customer_name, counter_no, receivable_type, status
                ORDER BY customer_name
                """
            ),
            "material_summary": self._rows(
                """
                SELECT sku, name, compatible_range, current_qty, avg_cost, status, remark
                FROM materials
                ORDER BY sku
                """
            ),
        }

    def repair_workbench_detail(self, user: User, repair_order_id: int) -> dict[str, Any]:
        self._allowed(user, "repair_order:read")
        order = self._one(
            """
            SELECT ro.*, m.machine_no, m.imei, m.serial, m.model, m.memory, m.color,
                   m.condition, m.current_status, c.name AS linked_customer_name,
                   c.phone AS customer_phone, c.category AS linked_customer_type
            FROM repair_orders ro
            JOIN machines m ON m.machine_id = ro.machine_id
            LEFT JOIN customers c ON c.customer_id = ro.customer_id
            WHERE ro.repair_order_id=?
            """,
            (repair_order_id,),
        )
        if not order:
            raise BusinessError("维修单不存在")
        order["order_no"] = order.get("order_no") or repair_order_no(repair_order_date_key(order.get("created_at")), 1)
        order["customer_name"] = order.get("customer_name") or order.get("linked_customer_name") or "待补"
        order["customer_type"] = order.get("customer_type") or order.get("linked_customer_type") or "待确认"
        order["unknown_fields"] = self._repair_unknown_fields(order)
        payments = self.repo.payments_for_source("repair", repair_order_id)
        inspections = self.repo.list_repair_order_inspections(repair_order_id)
        repair_items = self.repo.list_repair_items(repair_order_id)
        self._ensure_repair_modules(order, repair_items, payments, inspections)
        modules = self._repair_modules(order, repair_items, payments, inspections)
        return {
            "order": order,
            "modules": modules,
            "available_actions": self._repair_module_available_actions(order, modules, repair_items),
            "current_module": self._repair_current_module(modules),
            "audit_logs": self.repo.list_repair_order_module_actions(repair_order_id),
            "income_items": self._rows("SELECT * FROM repair_income_items WHERE repair_order_id=? ORDER BY income_item_id", (repair_order_id,)),
            "cost_items": self._rows("SELECT * FROM repair_cost_items WHERE repair_order_id=? ORDER BY cost_item_id", (repair_order_id,)),
            "repair_items": repair_items,
            "materials": self._rows(
                """
                SELECT rm.*, mt.sku, mt.name, mt.compatible_range
                FROM repair_materials rm
                JOIN materials mt ON mt.material_id=rm.material_id
                WHERE rm.repair_order_id=?
                ORDER BY rm.repair_material_id
                """,
                (repair_order_id,),
            ),
            "payments": payments,
            "receivables": self._rows("SELECT * FROM receivables WHERE repair_order_id=? ORDER BY receivable_id", (repair_order_id,)),
            "events": self.repo.repair_order_events(int(order["machine_id"]), repair_order_id),
            "inspections": inspections,
            "notes": self.repo.list_repair_order_notes(repair_order_id),
        }

    def repair_module_workflow(self, user: User, repair_order_id: int) -> dict[str, Any]:
        return self.repair_workbench_detail(user, repair_order_id)

    def _repair_payload(self, data: RepairWorkflowActionInput) -> dict[str, Any]:
        payload = dict(data.payload or {})
        for key in (
            "status",
            "payment_status",
            "settlement_status",
            "amount",
            "method",
            "account",
            "transaction_no",
            "received_by",
            "confirmed_by",
            "confirmed_at",
            "remark",
            "reason",
            "owner_user_id",
            "approver_user_id",
            "approval_reason",
            "credit_term_days",
            "credit_limit",
            "credit_amount",
            "receivable_amount",
            "received_amount",
            "discount_amount",
            "rounding_amount",
        ):
            value = getattr(data, key, None)
            if value not in (None, ""):
                payload.setdefault(key, value)
        return payload

    def _module_payload_json(self, module: dict[str, Any]) -> dict[str, Any]:
        try:
            return json.loads(module.get("payload_json") or "{}")
        except json.JSONDecodeError:
            return {}

    def _initial_module_statuses(
        self,
        order: dict[str, Any],
        repair_items: list[dict[str, Any]],
        payments: list[dict[str, Any]],
        inspections: list[dict[str, Any]],
    ) -> dict[str, str]:
        status = str(order.get("status") or "")
        workflow = str(order.get("workflow_status") or "")
        quote_confirm = str(order.get("quote_confirm_status") or "")
        quoted_amount = float(order.get("quoted_amount") or 0)
        paid_amount = sum(float(row.get("amount") or 0) for row in payments if row.get("direction") == "收入")
        closed = status in {"已完结", "已结单"} or bool(order.get("closed_at"))
        create_status = "待开始" if status == "已开单" and quoted_amount <= 0 and not repair_items else "已完成"
        quote_status = "锁定"
        repair_status = "锁定"
        payment_status = "锁定"
        if create_status == "已完成":
            quote_status = "待开始"
        if quoted_amount > 0 or status in {"已报价", "处理中", "待交付", "已交付", "财务待确认"}:
            quote_status = "待客户确认"
        if quote_confirm == "客户同意维修" or status in {"处理中", "待交付", "已交付", "财务待确认"}:
            quote_status = "客户已确认"
            repair_status = "待开始"
        if "质检不通过" in workflow:
            repair_status = "质检不通过"
        elif "质检通过" in workflow or status == "已交付":
            repair_status = "质检通过"
            payment_status = "待开始"
        elif status == "待交付" or order.get("engineer_closed_at"):
            repair_status = "待质检"
        elif status == "处理中" and (repair_items or "维修中" in workflow):
            repair_status = "维修中"
        if paid_amount > 0 and payment_status == "锁定":
            payment_status = "已预收"
        if paid_amount >= quoted_amount and quoted_amount > 0 and payment_status != "锁定":
            payment_status = "已收款待确认" if str(order.get("payment_status") or "") == "已付款待财务确认" else "已完成"
        elif paid_amount > 0 and payment_status not in {"锁定", "已完成"}:
            payment_status = "部分收款"
        if closed:
            return {"create": "已完成", "quote": "客户已确认" if quoted_amount > 0 else "已完成", "repair_qc": "质检通过", "payment": "已完成"}
        return {"create": create_status, "quote": quote_status, "repair_qc": repair_status, "payment": payment_status}

    def _ensure_repair_modules(
        self,
        order: dict[str, Any],
        repair_items: list[dict[str, Any]],
        payments: list[dict[str, Any]],
        inspections: list[dict[str, Any]],
    ) -> None:
        repair_order_id = int(order["repair_order_id"])
        initial_statuses = self._initial_module_statuses(order, repair_items, payments, inspections)
        existing_keys = {row["module_key"] for row in self.repo.list_repair_order_modules(repair_order_id)}
        for key, name, sequence, default_status, owner_role in REPAIR_MODULE_DEFINITIONS:
            status = initial_statuses.get(key, default_status)
            blocked_reason = self._repair_module_blocked_reason(key, status, initial_statuses)
            self.repo.ensure_repair_order_module(
                repair_order_id,
                {
                    "module_key": key,
                    "module_name": name,
                    "sequence": sequence,
                    "status": status,
                    "owner_role": owner_role,
                    "blocked_reason": blocked_reason,
                    "readonly": status == "已完成" or str(order.get("status") or "") in {"已完结", "已结单"},
                    "summary": "",
                    "payload_json": "{}",
                },
            )
            if key in existing_keys:
                module = self.repo.get_repair_order_module(repair_order_id, key)
                if module and module.get("status") == "锁定" and status != "锁定":
                    self.repo.update_repair_order_module(repair_order_id, key, status=status, blocked_reason=blocked_reason)

    def _repair_module_blocked_reason(self, key: str, status: str, statuses: dict[str, str]) -> str:
        if status != "锁定":
            return ""
        if key == "quote":
            return "建单完成后开放检测报价"
        if key == "repair_qc":
            return "客户确认报价后开放维修"
        if key == "payment":
            return "维修后质检通过后开放最终收费结单"
        return ""

    def _repair_current_module(self, modules: dict[str, Any]) -> str:
        for key in ("create", "quote", "repair_qc", "payment"):
            status = str((modules.get(key) or {}).get("status") or "")
            if status not in {"已完成", "客户已确认", "质检通过"}:
                return key
        return "payment"

    def _repair_modules(
        self,
        order: dict[str, Any],
        repair_items: list[dict[str, Any]],
        payments: list[dict[str, Any]],
        inspections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        quoted_amount = float(order.get("quoted_amount") or 0)
        paid_amount = sum(float(row.get("amount") or 0) for row in payments if row.get("direction") == "收入")
        post_inspections = [row for row in inspections if row.get("stage") == "post"]
        post_has_abnormal = any(int(row.get("abnormal") or 0) for row in post_inspections)
        result: dict[str, Any] = {}
        summaries = {
            "create": f"{order.get('order_no') or order.get('repair_order_id')} / {order.get('model') or ''}",
            "quote": order.get("diagnosis") or order.get("fault_description") or "等待检测报价",
            "repair_qc": order.get("repair_solution") or order.get("engineer_close_remark") or "等待维修记录",
            "payment": f"已收 {paid_amount:.2f} / 应收 {quoted_amount:.2f}",
        }
        for module in self.repo.list_repair_order_modules(int(order["repair_order_id"])):
            key = str(module["module_key"])
            payload = self._module_payload_json(module)
            item = {
                "key": key,
                "title": module["module_name"],
                "status": module["status"],
                "summary": module.get("summary") or summaries.get(key, ""),
                "owner_role": module.get("owner_role") or "",
                "owner_user_id": module.get("owner_user_id") or "",
                "started_at": module.get("started_at") or "",
                "started_by": module.get("started_by") or "",
                "completed_at": module.get("completed_at") or "",
                "completed_by": module.get("completed_by") or "",
                "reopen_count": int(module.get("reopen_count") or 0),
                "blocked_reason": module.get("blocked_reason") or "",
                "readonly": bool(module.get("readonly")),
                "payload": payload,
            }
            if key == "quote":
                item["amount"] = quoted_amount
            elif key == "repair_qc":
                item["post_has_abnormal"] = post_has_abnormal
            elif key == "payment":
                item["paid_amount"] = paid_amount
                item["receivable_amount"] = max(quoted_amount - paid_amount, 0)
            result[key] = item
        return result

    def _repair_module_available_actions(self, order: dict[str, Any], modules: dict[str, Any], repair_items: list[dict[str, Any]]) -> list[str]:
        status = str(order.get("status") or "")
        if status in {"已完结", "已结单", "已作废"}:
            return []
        create = str(modules.get("create", {}).get("status") or "")
        quote = str(modules.get("quote", {}).get("status") or "")
        repair = str(modules.get("repair_qc", {}).get("status") or "")
        payment = str(modules.get("payment", {}).get("status") or "")
        actions: list[str] = []
        if create in {"待开始"}:
            actions.append("create.start")
        if create in {"待开始", "建单中", "已重开"}:
            actions.append("create.save")
        if create in {"待开始", "建单中", "已重开"}:
            actions.append("create.complete")
        if create == "已完成":
            actions.append("payment.prepay")
        if quote == "待开始":
            actions.append("quote.start")
        if quote in {"待开始", "检测中", "已重开"}:
            actions.append("quote.save")
        if quote in {"待开始", "检测中", "已重开"}:
            actions.append("quote.complete")
            actions.append("quote.submit")
        if quote in {"已报价", "待客户确认"}:
            actions.append("quote.confirm")
        if quote == "客户已确认" and repair in {"待开始", "质检不通过", "返修中"}:
            actions.append("repair.start")
        if repair in {"维修中", "返修中"}:
            actions.append("repair.save")
            actions.append("repair.complete")
        if repair == "待质检":
            actions.append("qc.start")
            actions.append("qc.complete")
        if repair == "质检中":
            actions.append("qc.complete")
        if repair == "质检通过" and payment in {"待开始", "已预收"}:
            actions.append("payment.start")
        if repair == "质检通过" and payment in {"待开始", "收费中", "部分收款", "已预收"}:
            actions.append("payment.register")
            actions.append("payment.credit")
        if payment in {"已收款待确认", "挂账待确认"} or str(order.get("payment_status") or "") == "已付款待财务确认":
            actions.append("payment.confirm")
        for key, module in modules.items():
            if str(module.get("status") or "") in {"已完成", "客户已确认", "质检通过"}:
                actions.append(f"{key}.reopen")
        return actions

    def _repair_action_names(self, module_key: str, route_module: str, action_key: str) -> set[str]:
        names = {f"{module_key}.{action_key}", f"{route_module}.{action_key}"}
        if module_key == "repair_qc":
            names.add(f"repair.{action_key}")
            names.add(f"qc.{action_key}")
        if module_key == "quote" and action_key == "submit":
            names.add("quote.complete")
        return names

    def _set_repair_module(
        self,
        repair_order_id: int,
        module_key: str,
        status: str,
        user: User,
        action_key: str,
        action_name: str,
        payload: dict[str, Any],
        reason: str = "",
        owner_user_id: str = "",
        complete: bool = False,
        start: bool = False,
        reopen: bool = False,
    ) -> None:
        module = self.repo.get_repair_order_module(repair_order_id, module_key)
        if not module:
            raise BusinessError("维修模块不存在")
        fields: dict[str, Any] = {
            "status": status,
            "payload_json": json.dumps(payload, ensure_ascii=False),
            "blocked_reason": "" if status != "锁定" else module.get("blocked_reason") or "",
            "readonly": 1 if complete else 0,
        }
        if owner_user_id:
            fields["owner_user_id"] = owner_user_id
        if start and not module.get("started_at"):
            self.conn.execute(
                "UPDATE repair_order_modules SET started_at=CURRENT_TIMESTAMP, started_by=?, owner_user_id=?, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=? AND module_key=?",
                (user.username, owner_user_id or user.username, repair_order_id, module_key),
            )
        if complete:
            self.conn.execute(
                "UPDATE repair_order_modules SET completed_at=CURRENT_TIMESTAMP, completed_by=?, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=? AND module_key=?",
                (user.username, repair_order_id, module_key),
            )
        if reopen:
            self.conn.execute(
                "UPDATE repair_order_modules SET reopened_at=CURRENT_TIMESTAMP, reopened_by=?, reopen_count=reopen_count+1, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=? AND module_key=?",
                (user.username, repair_order_id, module_key),
            )
        self.repo.update_repair_order_module(repair_order_id, module_key, **fields)
        self.repo.add_repair_order_module_action(
            repair_order_id,
            int(module["module_id"]),
            module_key,
            action_key,
            action_name,
            str(module.get("status") or ""),
            status,
            user.username,
            json.dumps(payload, ensure_ascii=False),
            reason,
            str(payload.get("idempotency_key") or ""),
        )

    def _create_repair_payment_record(self, user: User, repair_order_id: int, amount: float, method: str, remark: str, status: str) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO payments
            (source_type, source_id, direction, amount, method, operator, received_by, status, remark)
            VALUES ('repair', ?, '收入', ?, ?, ?, ?, ?, ?)
            """,
            (repair_order_id, amount, method, user.username, user.username, status, remark),
        )
        return int(cur.lastrowid)

    def apply_repair_module_action(self, user: User, repair_order_id: int, module: str, action: str, data: RepairWorkflowActionInput) -> dict[str, Any]:
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        module_key = REPAIR_MODULE_ALIASES.get(module, module)
        action_key = REPAIR_ACTION_ALIASES.get(action, action)
        if module_key not in {item[0] for item in REPAIR_MODULE_DEFINITIONS}:
            raise BusinessError("未知维修模块")
        detail = self.repair_workbench_detail(user, repair_order_id)
        available = set(detail.get("available_actions", []))
        accepted = self._repair_action_names(module_key, module, action_key)
        if not available.intersection(accepted):
            raise BusinessError("当前模块状态不允许执行该动作")
        payload = self._repair_payload(data)
        reason = data.reason or data.remark or payload.get("reason") or ""
        module_row = self.repo.get_repair_order_module(repair_order_id, module_key)
        if not module_row:
            raise BusinessError("维修模块不存在")

        if action_key == "start":
            next_status = {"create": "建单中", "quote": "检测中", "repair_qc": "质检中" if module == "qc" else "维修中", "payment": "收费中"}[module_key]
            self._set_repair_module(repair_order_id, module_key, next_status, user, action_key, "开始模块", payload, owner_user_id=data.owner_user_id or user.username, start=True)
            if module_key == "quote":
                self.repo.update_repair_order_status(repair_order_id, OrderStatus.diagnosing.value, data.remark)
            elif module_key == "repair_qc":
                self.repo.update_repair_order_status(repair_order_id, OrderStatus.processing.value, data.remark)
                self.conn.execute("UPDATE repair_orders SET workflow_status='工程师维修中', updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?", (repair_order_id,))
                self.repo.update_machine_status(int(order["machine_id"]), MachineStatus.repairing.value)
            self.repo.add_machine_event(int(order["machine_id"]), "repair", "开始模块", f"{module_key}:{next_status}", user.username, "repair", repair_order_id)
            self.conn.commit()
            return self.repair_workbench_detail(user, repair_order_id)

        if action_key == "save":
            current = str(module_row.get("status") or "")
            self._set_repair_module(repair_order_id, module_key, current, user, action_key, "保存草稿", payload, reason)
            self.conn.commit()
            return self.repair_workbench_detail(user, repair_order_id)

        if module_key == "create" and action_key == "complete":
            self._set_repair_module(repair_order_id, "create", "已完成", user, action_key, "完成建单", payload, reason, complete=True)
            quote_module = self.repo.get_repair_order_module(repair_order_id, "quote")
            if quote_module and quote_module["status"] == "锁定":
                self.repo.update_repair_order_module(repair_order_id, "quote", status="待开始", blocked_reason="", readonly=0)
            self.repo.update_repair_order_status(repair_order_id, OrderStatus.diagnosing.value, data.remark)
            self.repo.update_machine_status(int(order["machine_id"]), MachineStatus.diagnosing.value)
            self.repo.add_machine_event(int(order["machine_id"]), "repair", "完成建单", data.remark, user.username, "repair", repair_order_id)
            self.conn.commit()
            return self.repair_workbench_detail(user, repair_order_id)

        if module_key == "payment" and action_key == "prepay":
            amount = float(data.amount or payload.get("amount") or 0)
            if amount <= 0:
                raise BusinessError("预收款金额必须大于 0")
            payment_id = self._create_repair_payment_record(user, repair_order_id, amount, data.method or payload.get("payment_method") or "", data.remark or "维修预收款", "预收款")
            payload["payment_id"] = payment_id
            self._set_repair_module(repair_order_id, "payment", "已预收", user, action_key, "登记预收款", payload, reason)
            self.repo.add_machine_event(int(order["machine_id"]), "payment", "登记预收款", f"{amount:.2f}", user.username, "payment", payment_id)
            self.conn.commit()
            return self.repair_workbench_detail(user, repair_order_id)

        if module_key == "quote" and action_key in {"complete", "submit"}:
            before_amount = float(order.get("quoted_amount") or 0)
            quoted_amount = float(data.amount or payload.get("total_quote_amount") or payload.get("after_total_amount") or before_amount or 0)
            if quoted_amount <= 0:
                raise BusinessError("报价金额必须大于 0")
            payload.setdefault("before_total_amount", before_amount)
            payload.setdefault("after_total_amount", quoted_amount)
            self.repo.quote_repair_order(
                repair_order_id,
                data.remark or payload.get("inspection_result") or order.get("diagnosis") or order.get("fault_description") or "检测完成",
                quoted_amount,
                OrderStatus.quoted.value,
                data.remark or payload.get("fault_cause") or order.get("fault_detail") or "",
                payload.get("repair_plan") or order.get("repair_solution") or "",
                "待客户确认",
            )
            self._set_repair_module(repair_order_id, "quote", "待客户确认", user, action_key, "提交报价", payload, reason)
            self.repo.update_machine_status(int(order["machine_id"]), MachineStatus.quoted.value)
            self.repo.add_machine_event(int(order["machine_id"]), "repair", "提交检测报价", f"{quoted_amount:.2f}", user.username, "repair", repair_order_id)
            self.conn.commit()
            return self.repair_workbench_detail(user, repair_order_id)

        if module_key == "quote" and action_key == "confirm":
            self.repo.confirm_repair_quote(
                repair_order_id,
                OrderStatus.processing.value,
                "客户已确认，待维修",
                "客户同意维修",
                data.method or payload.get("confirm_method") or "现场",
                data.received_by or payload.get("contact_person") or "",
                data.remark or "",
            )
            self._set_repair_module(repair_order_id, "quote", "客户已确认", user, action_key, "客户确认报价", payload, reason, complete=True)
            repair_module = self.repo.get_repair_order_module(repair_order_id, "repair_qc")
            if repair_module and repair_module["status"] == "锁定":
                self.repo.update_repair_order_module(repair_order_id, "repair_qc", status="待开始", blocked_reason="", readonly=0)
            self.repo.add_machine_event(int(order["machine_id"]), "repair", "客户确认报价", data.method or "现场", user.username, "repair", repair_order_id)
            self.conn.commit()
            return self.repair_workbench_detail(user, repair_order_id)

        if module_key == "repair_qc" and action_key == "complete" and module == "repair":
            # 完成维修进入待质检，库存扣减在后续接入实际库存明细时由 used_parts 驱动。
            self.repo.engineer_close_repair_order(repair_order_id, data.remark or "维修完成，待维修后质检")
            self._set_repair_module(repair_order_id, "repair_qc", "待质检", user, action_key, "完成维修", payload, reason)
            self.repo.add_machine_event(int(order["machine_id"]), "repair", "完成维修", data.remark, user.username, "repair", repair_order_id)
            self.conn.commit()
            return self.repair_workbench_detail(user, repair_order_id)

        if module_key == "repair_qc" and action_key == "complete":
            qc_status = data.status or payload.get("qc_result") or "质检通过"
            if qc_status not in {"质检通过", "质检不通过", "通过", "不通过"}:
                raise BusinessError("维修后质检结果必须是 质检通过 或 质检不通过")
            passed = qc_status in {"质检通过", "通过"}
            if passed:
                self.repo.deliver_repair_order(repair_order_id, data.remark or "维修后质检通过", data.remark, OrderStatus.delivered.value)
                self.conn.execute("UPDATE repair_orders SET workflow_status='质检通过，待收费', updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?", (repair_order_id,))
                self.repo.update_machine_status(int(order["machine_id"]), MachineStatus.delivered.value)
                self._set_repair_module(repair_order_id, "repair_qc", "质检通过", user, action_key, "质检通过", payload, reason, complete=True)
                payment_module = self.repo.get_repair_order_module(repair_order_id, "payment")
                if payment_module and payment_module["status"] in {"锁定", "已预收"}:
                    self.repo.update_repair_order_module(repair_order_id, "payment", status="待开始", blocked_reason="", readonly=0)
            else:
                self.repo.update_repair_order_status(repair_order_id, OrderStatus.processing.value, data.remark)
                self.conn.execute("UPDATE repair_orders SET workflow_status='质检不通过，工程师返修', updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?", (repair_order_id,))
                self.repo.update_machine_status(int(order["machine_id"]), MachineStatus.repairing.value)
                self._set_repair_module(repair_order_id, "repair_qc", "质检不通过", user, action_key, "质检不通过", payload, reason)
            self.repo.add_machine_event(int(order["machine_id"]), "repair", "维修后质检", "质检通过" if passed else "质检不通过", user.username, "repair", repair_order_id)
            self.conn.commit()
            return self.repair_workbench_detail(user, repair_order_id)

        if module_key == "payment" and action_key == "start":
            self._set_repair_module(repair_order_id, "payment", "收费中", user, action_key, "开始收费结单", payload, reason, owner_user_id=data.owner_user_id or user.username, start=True)
            self.conn.commit()
            return self.repair_workbench_detail(user, repair_order_id)

        if module_key == "payment" and action_key == "register":
            amount = float(data.amount or payload.get("received_amount") or payload.get("amount") or 0)
            if amount <= 0:
                raise BusinessError("登记收费金额必须大于 0")
            payment_id = self._create_repair_payment_record(user, repair_order_id, amount, data.method or payload.get("payment_method") or "", data.remark or "维修收费登记", "已收款待确认")
            paid = self.repo.payment_total_for_source("repair", repair_order_id, "收入")
            quoted = float(order.get("quoted_amount") or 0)
            next_status = "已收款待确认" if paid >= quoted and quoted > 0 else "部分收款"
            payload["payment_id"] = payment_id
            payload["paid_amount"] = paid
            self._set_repair_module(repair_order_id, "payment", next_status, user, action_key, "登记收款", payload, reason)
            self.conn.execute("UPDATE repair_orders SET payment_status=?, status='财务待确认', updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?", ("已付款待财务确认" if next_status == "已收款待确认" else "部分收款", repair_order_id))
            self.repo.add_machine_event(int(order["machine_id"]), "payment", "登记维修收款", f"{amount:.2f}", user.username, "payment", payment_id)
            self.conn.commit()
            return self.repair_workbench_detail(user, repair_order_id)

        if module_key == "payment" and action_key == "credit":
            customer_type = str(order.get("customer_type") or order.get("linked_customer_type") or "")
            if customer_type not in {"同行客户", "企业客户"}:
                raise BusinessError("只有同行客户和企业客户允许欠款挂账")
            if not (data.approver_user_id or payload.get("approver_user_id")):
                raise BusinessError("欠款挂账必须选择审批人")
            self._set_repair_module(repair_order_id, "payment", "挂账待确认", user, action_key, "登记欠款挂账", payload, reason)
            self.conn.execute("UPDATE repair_orders SET payment_status='挂账待确认', status='财务待确认', updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?", (repair_order_id,))
            self.conn.commit()
            return self.repair_workbench_detail(user, repair_order_id)

        if module_key == "payment" and action_key == "confirm":
            self._set_repair_module(repair_order_id, "payment", "已完成", user, action_key, "财务确认收费", payload, reason, complete=True)
            self.conn.execute(
                "UPDATE payments SET status='财务已确认', confirmed_by=?, confirmed_at=CURRENT_TIMESTAMP WHERE source_type='repair' AND source_id=? AND status IN ('已收款待确认', '预收款', '已登记')",
                (data.confirmed_by or user.username, repair_order_id),
            )
            self.conn.execute(
                "UPDATE repair_orders SET payment_status='财务已确认', settlement_status='已结', status='已完结', closed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?",
                (repair_order_id,),
            )
            self.repo.close_machine(int(order["machine_id"]), MachineStatus.closed.value)
            self.repo.add_machine_event(int(order["machine_id"]), "payment", "财务确认收费", data.remark, user.username, "repair", repair_order_id)
            self.conn.commit()
            return self.repair_workbench_detail(user, repair_order_id)

        if action_key == "reopen":
            if user.role not in {Role.admin, Role.boss}:
                raise PermissionError("只有店长或管理员可以重开模块")
            if not reason:
                raise BusinessError("重开模块必须填写原因")
            self._set_repair_module(repair_order_id, module_key, "已重开", user, action_key, "重开模块", payload, reason, reopen=True)
            self.conn.commit()
            return self.repair_workbench_detail(user, repair_order_id)

        raise BusinessError("未知维修模块动作")

    def list_repair_order_photos(self, user: User, repair_order_id: int) -> list[dict[str, Any]]:
        self._allowed(user, "repair_order:read")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        return self.repo.list_repair_order_photos(repair_order_id)

    def add_repair_order_photo(self, user: User, repair_order_id: int, stage: str, filename: str, content_type: str, content: bytes) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        self._ensure_engineer_owns_repair(user, order)
        normalized_stage = stage.strip().lower()
        if normalized_stage not in {"pre", "post"}:
            raise BusinessError("照片阶段必须是 pre 或 post")
        if not content:
            raise BusinessError("照片内容不能为空")
        if len(content) > 10 * 1024 * 1024:
            raise BusinessError("照片不能超过 10MB")
        allowed_types = {"image/jpeg", "image/png", "image/webp"}
        suffix = Path(filename or "").suffix.lower()
        allowed_suffixes = {".jpg", ".jpeg", ".png", ".webp"}
        if content_type not in allowed_types and suffix not in allowed_suffixes:
            raise BusinessError("仅支持 jpg、png、webp 图片")
        if suffix not in allowed_suffixes:
            suffix = ".jpg" if content_type == "image/jpeg" else ".png" if content_type == "image/png" else ".webp"

        directory = ROOT_DIR / "uploads" / "repair_orders" / str(repair_order_id) / normalized_stage
        directory.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid4().hex}{suffix}"
        (directory / stored_name).write_bytes(content)
        url = f"/uploads/repair_orders/{repair_order_id}/{normalized_stage}/{stored_name}"
        photo_id = self.repo.add_repair_order_photo(repair_order_id, normalized_stage, stored_name, url, user.username)
        title = "上传维修前照片" if normalized_stage == "pre" else "上传维修后照片"
        self.repo.add_machine_event(int(order["machine_id"]), "repair", title, Path(filename or stored_name).name, user.username, "repair", repair_order_id)
        self._log_success(user, "repair_order:photo", "repair_order", str(repair_order_id), customer_id=order.get("customer_id"), request_summary=title)
        self.conn.commit()
        photo = next((row for row in self.repo.list_repair_order_photos(repair_order_id) if int(row["photo_id"]) == photo_id), {})
        return {
            "photo_id": photo_id,
            "repair_order_id": repair_order_id,
            "stage": normalized_stage,
            "filename": stored_name,
            "url": url,
            "uploaded_by": user.username,
            "uploaded_at": photo.get("uploaded_at", ""),
        }

    def save_repair_order_inspection(self, user: User, repair_order_id: int, data: RepairInspectionInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        self._ensure_engineer_owns_repair(user, order)
        stage, normalized_items, note = self._normalize_inspection_input(data)
        self.repo.replace_repair_order_inspections(repair_order_id, stage, normalized_items, user.username)
        abnormal_items = [row["item"] for row in normalized_items if row["abnormal"]]
        title = "更新维修前检测" if stage == "pre" else "更新维修后检测"
        detail = "、".join(abnormal_items) if abnormal_items else "无异常功能"
        if note:
            detail = f"{detail}；备注：{note}"
        self.repo.add_machine_event(int(order["machine_id"]), "repair", title, detail, user.username, "repair", repair_order_id)
        self._log_success(user, "repair_order:inspection", "repair_order", str(repair_order_id), customer_id=order.get("customer_id"), request_summary=detail)
        self.conn.commit()
        return {"repair_order_id": repair_order_id, "stage": stage, "items": normalized_items, "note": note}

    def list_materials(self, user: User) -> dict[str, Any]:
        self._allowed(user, "inventory:read")
        return {
            "materials": self._rows("SELECT * FROM materials ORDER BY sku"),
            "batches": self._rows(
                """
                SELECT b.*, m.sku, m.name
                FROM material_batches b
                JOIN materials m ON m.material_id=b.material_id
                ORDER BY b.purchased_at DESC, b.batch_id DESC
                """
            ),
            "movements": self._rows(
                """
                SELECT sm.*, m.sku, m.name, ro.order_no
                FROM stock_movements sm
                JOIN materials m ON m.material_id=sm.material_id
                LEFT JOIN repair_orders ro ON ro.repair_order_id=sm.repair_order_id
                ORDER BY sm.happened_at DESC, sm.stock_movement_id DESC
                LIMIT 200
                """
            ),
        }

    def _warehouse_code(self, prefix: str, table: str, column: str) -> str:
        like = f"{prefix}-%"
        rows = self._rows(f"SELECT {column} AS code FROM {table} WHERE {column} LIKE ? ORDER BY {column} DESC", (like,))
        next_no = 1
        for row in rows:
            tail = str(row["code"]).rsplit("-", 1)[-1]
            if tail.isdigit():
                next_no = int(tail) + 1
                break
        return f"{prefix}-{next_no:04d}"

    def _normalize_code_part(self, value: str, fallback: str = "GEN") -> str:
        cleaned = "".join(ch.upper() for ch in value if ch.isalnum())
        return (cleaned or fallback)[:16]

    def _update_material_qty(self, material_id: int) -> None:
        qty = self.conn.execute(
            "SELECT COUNT(*) AS qty FROM material_units WHERE material_id=? AND current_status='在库可用'",
            (material_id,),
        ).fetchone()["qty"]
        self.conn.execute(
            "UPDATE materials SET current_qty=?, updated_at=CURRENT_TIMESTAMP WHERE material_id=?",
            (qty, material_id),
        )

    def _stock_movement(
        self,
        material_id: int,
        movement_type: str,
        qty: float,
        actor: str,
        *,
        batch_id: int | None = None,
        unit_id: int | None = None,
        request_id: int | None = None,
        repair_order_id: int | None = None,
        location_id: int | None = None,
        unit_cost: float = 0,
        counterparty: str = "",
        note: str = "",
        source_type: str = "",
        source_id: int | None = None,
    ) -> None:
        direction = "入库" if qty > 0 else "出库" if qty < 0 else "记录"
        self.conn.execute(
            """
            INSERT INTO stock_movements
            (material_id, batch_id, unit_id, request_id, repair_order_id, location_id,
             movement_type, direction, source_type, source_id, qty, unit_cost, actor, counterparty, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                material_id,
                batch_id,
                unit_id,
                request_id,
                repair_order_id,
                location_id,
                movement_type,
                direction,
                source_type,
                source_id,
                qty,
                unit_cost,
                actor,
                counterparty,
                note,
            ),
        )

    def warehouse_overview(self, user: User) -> dict[str, Any]:
        self._allowed(user, "warehouse:read")
        return {
            "categories": self._rows("SELECT * FROM material_categories ORDER BY category_code"),
            "areas": self._rows("SELECT * FROM warehouse_areas ORDER BY area_code"),
            "locations": self._rows(
                """
                SELECT l.*, a.area_code, a.name AS area_name
                FROM warehouse_locations l
                LEFT JOIN warehouse_areas a ON a.area_id=l.area_id
                ORDER BY l.location_code
                """
            ),
            "materials": self._rows(
                """
                SELECT m.*, c.category_code, c.name AS category_name, l.location_code AS default_location_code
                FROM materials m
                LEFT JOIN material_categories c ON c.category_id=m.category_id
                LEFT JOIN warehouse_locations l ON l.location_id=m.default_location_id
                ORDER BY COALESCE(NULLIF(m.material_code, ''), m.sku)
                """
            ),
            "units": self.material_units(user),
            "batches": self.material_batches(user),
            "requests": self.material_requests(user),
            "returns": self._rows(
                """
                SELECT r.*, u.unit_code, m.sku, m.material_code, m.name
                FROM material_returns r
                JOIN material_units u ON u.unit_id=r.unit_id
                JOIN materials m ON m.material_id=u.material_id
                ORDER BY r.created_at DESC, r.return_id DESC
                LIMIT 200
                """
            ),
            "movements": self.stock_movements(user),
            "low_stock": self._rows(
                """
                SELECT material_id, sku, material_code, name, current_qty, min_qty
                FROM materials
                WHERE min_qty > 0 AND current_qty <= min_qty
                ORDER BY current_qty ASC, name
                """
            ),
            "mine": self.material_requests(user, mine=True),
        }

    def create_warehouse_area(self, user: User, data: WarehouseAreaInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:write")
        area_code = data.area_code.strip() or self._warehouse_code("AREA", "warehouse_areas", "area_code")
        self.conn.execute(
            """
            INSERT INTO warehouse_areas (area_code, name, status, remark)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(area_code) DO UPDATE SET name=excluded.name, status=excluded.status,
                remark=excluded.remark, updated_at=CURRENT_TIMESTAMP
            """,
            (area_code, data.name, data.status, data.remark),
        )
        self.conn.commit()
        return self._one("SELECT * FROM warehouse_areas WHERE area_code=?", (area_code,)) or {}

    def create_warehouse_location(self, user: User, data: WarehouseLocationInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:write")
        location_code = data.location_code.strip() or self._warehouse_code("LOC", "warehouse_locations", "location_code")
        self.conn.execute(
            """
            INSERT INTO warehouse_locations (area_id, location_code, name, status, remark)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(location_code) DO UPDATE SET area_id=excluded.area_id, name=excluded.name,
                status=excluded.status, remark=excluded.remark, updated_at=CURRENT_TIMESTAMP
            """,
            (data.area_id, location_code, data.name, data.status, data.remark),
        )
        self.conn.commit()
        return self._one("SELECT * FROM warehouse_locations WHERE location_code=?", (location_code,)) or {}

    def create_material_category(self, user: User, data: MaterialCategoryInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:write")
        category_code = data.category_code.strip().upper() or self._warehouse_code("CAT", "material_categories", "category_code")
        self.conn.execute(
            """
            INSERT INTO material_categories (category_code, name, parent_id, remark)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(category_code) DO UPDATE SET name=excluded.name, parent_id=excluded.parent_id,
                remark=excluded.remark, updated_at=CURRENT_TIMESTAMP
            """,
            (category_code, data.name, data.parent_id, data.remark),
        )
        self.conn.commit()
        return self._one("SELECT * FROM material_categories WHERE category_code=?", (category_code,)) or {}

    def _material_code(self, data: MaterialInput) -> str:
        if data.material_code.strip():
            return data.material_code.strip().upper()
        cat = "MAT"
        if data.category_id:
            row = self._one("SELECT category_code FROM material_categories WHERE category_id=?", (data.category_id,))
            cat = (row or {}).get("category_code") or cat
        spec = self._normalize_code_part(data.compatible_range or data.brand or data.name)
        size = self._normalize_code_part(data.spec, "STD")
        return self._warehouse_code(f"{cat}-{spec}-{size}", "materials", "material_code")

    def create_material(self, user: User, data: MaterialInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:write")
        material_code = self._material_code(data)
        sku = data.sku.strip() or material_code
        self.conn.execute(
            """
            INSERT INTO materials
            (sku, material_code, category_id, default_location_id, min_qty, track_unit,
             name, brand, spec, compatible_range, unit, avg_cost, status, remark)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, '在库', ?)
            ON CONFLICT(sku) DO UPDATE SET material_code=excluded.material_code,
                category_id=excluded.category_id, default_location_id=excluded.default_location_id,
                min_qty=excluded.min_qty, name=excluded.name, brand=excluded.brand, spec=excluded.spec,
                compatible_range=excluded.compatible_range, unit=excluded.unit, avg_cost=excluded.avg_cost,
                remark=excluded.remark, updated_at=CURRENT_TIMESTAMP
            """,
            (
                sku,
                material_code,
                data.category_id,
                data.default_location_id,
                data.min_qty,
                data.name,
                data.brand,
                data.spec,
                data.compatible_range,
                data.unit,
                data.avg_cost,
                data.remark,
            ),
        )
        self.conn.commit()
        return self._one("SELECT * FROM materials WHERE sku=?", (sku,)) or {}

    def _ensure_material(self, user: User, material_id: int | None, material: MaterialInput | None) -> dict[str, Any]:
        if material_id:
            row = self._one("SELECT * FROM materials WHERE material_id=?", (material_id,))
            if not row:
                raise BusinessError("物料不存在")
            return row
        if not material:
            raise BusinessError("必须选择物料或提供新物料档案")
        return self.create_material(user, material)

    def create_material_batch(self, user: User, data: MaterialBatchInput, batch_type: str) -> dict[str, Any]:
        self._allowed(user, "warehouse:write")
        material = self._ensure_material(user, data.material_id, data.material)
        material_id = int(material["material_id"])
        batch_no = data.batch_no.strip() or self._warehouse_code("BATCH", "material_batches", "batch_no")
        purchase_type = "临采入库" if batch_type == "ad_hoc" else "采购入库"
        location_id = data.location_id or material.get("default_location_id")
        cur = self.conn.execute(
            """
            INSERT INTO material_batches
            (material_id, batch_no, supplier, purchase_type, batch_type, location_id, purchase_no,
             handler, qty, unit_cost, remaining_qty, payment_status, purchased_at, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(NULLIF(?, ''), CURRENT_TIMESTAMP), ?)
            """,
            (
                material_id,
                batch_no,
                data.supplier,
                purchase_type,
                batch_type,
                location_id,
                data.purchase_no,
                data.handler or user.username,
                data.qty,
                data.unit_cost,
                data.qty,
                data.payment_status,
                data.purchased_at,
                data.remark,
            ),
        )
        batch_id = int(cur.lastrowid)
        code = material.get("material_code") or material.get("sku")
        day = (data.purchased_at or "").replace("-", "")[:8] or batch_no[-8:] if batch_no[-8:].isdigit() else "TODAY"
        for index in range(1, data.qty + 1):
            unit_code = f"{code}-{day}-{index:04d}"
            while self._one("SELECT unit_id FROM material_units WHERE unit_code=?", (unit_code,)):
                unit_code = f"{code}-{day}-{uuid4().hex[:4].upper()}"
            unit_cur = self.conn.execute(
                """
                INSERT INTO material_units
                (material_id, batch_id, unit_code, current_status, location_id, unit_cost, remark)
                VALUES (?, ?, ?, '在库可用', ?, ?, ?)
                """,
                (material_id, batch_id, unit_code, location_id, data.unit_cost, data.remark),
            )
            self._stock_movement(
                material_id,
                purchase_type,
                1,
                user.username,
                batch_id=batch_id,
                unit_id=int(unit_cur.lastrowid),
                location_id=location_id,
                unit_cost=data.unit_cost,
                counterparty=data.supplier,
                note=data.remark,
                source_type="material_batch",
                source_id=batch_id,
            )
        self._update_material_qty(material_id)
        self.conn.commit()
        return self._one("SELECT * FROM material_batches WHERE batch_id=?", (batch_id,)) or {}

    def return_material_batch(self, user: User, batch_id: int, data: MaterialBatchReturnInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:write")
        batch = self._one("SELECT * FROM material_batches WHERE batch_id=?", (batch_id,))
        if not batch:
            raise BusinessError("入库批次不存在")
        units = data.unit_ids
        if not units and data.qty:
            units = [
                int(row["unit_id"])
                for row in self._rows(
                    """
                    SELECT unit_id FROM material_units
                    WHERE batch_id=? AND current_status IN ('在库可用', '拆回验收可退')
                    ORDER BY unit_id LIMIT ?
                    """,
                    (batch_id, data.qty),
                )
            ]
        if not units:
            raise BusinessError("请选择要退货的单件码")
        for unit_id in units:
            unit = self._one("SELECT * FROM material_units WHERE unit_id=? AND batch_id=?", (unit_id, batch_id))
            if not unit or unit["current_status"] not in {"在库可用", "拆回验收可退"}:
                raise BusinessError("只有在库可用或拆回验收可退物料可以采购退货")
            self.conn.execute(
                "UPDATE material_units SET current_status='已退货', updated_at=CURRENT_TIMESTAMP WHERE unit_id=?",
                (unit_id,),
            )
            self._stock_movement(
                int(unit["material_id"]),
                "采购退货",
                -1,
                user.username,
                batch_id=batch_id,
                unit_id=unit_id,
                location_id=unit.get("location_id"),
                unit_cost=float(unit.get("unit_cost") or 0),
                counterparty=batch.get("supplier") or "待确认",
                note=data.remark,
                source_type="material_batch_return",
                source_id=batch_id,
            )
        self.conn.execute(
            """
            UPDATE material_batches SET remaining_qty=remaining_qty-?, refund_status=?, refund_amount=?,
                refund_method=?, refund_transaction_no=?
            WHERE batch_id=?
            """,
            (len(units), data.refund_status, data.refund_amount, data.refund_method, data.refund_transaction_no, batch_id),
        )
        self._update_material_qty(int(batch["material_id"]))
        self.conn.commit()
        return {"batch_id": batch_id, "returned_units": units, "refund_status": data.refund_status}

    def material_batches(self, user: User) -> list[dict[str, Any]]:
        self._allowed(user, "warehouse:read")
        return self._rows(
            """
            SELECT b.*, m.sku, m.material_code, m.name, l.location_code
            FROM material_batches b
            JOIN materials m ON m.material_id=b.material_id
            LEFT JOIN warehouse_locations l ON l.location_id=b.location_id
            ORDER BY b.purchased_at DESC, b.batch_id DESC
            """
        )

    def material_units(self, user: User) -> list[dict[str, Any]]:
        self._allowed(user, "warehouse:read")
        return self._rows(
            """
            SELECT u.*, m.sku, m.material_code, m.name, l.location_code
            FROM material_units u
            JOIN materials m ON m.material_id=u.material_id
            LEFT JOIN warehouse_locations l ON l.location_id=u.location_id
            ORDER BY u.updated_at DESC, u.unit_id DESC
            LIMIT 500
            """
        )

    def create_material_request(self, user: User, data: MaterialRequestInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:request")
        if not data.items:
            raise BusinessError("申领单必须至少包含一项物料")
        engineer_user = data.engineer_user or user.username
        request_no = self._warehouse_code("MR", "material_requests", "request_no")
        cur = self.conn.execute(
            """
            INSERT INTO material_requests (request_no, repair_order_id, engineer_user, requested_by, remark)
            VALUES (?, ?, ?, ?, ?)
            """,
            (request_no, data.repair_order_id, engineer_user, user.username, data.remark),
        )
        request_id = int(cur.lastrowid)
        for item in data.items:
            if not self._one("SELECT material_id FROM materials WHERE material_id=?", (item.material_id,)):
                raise BusinessError("申领物料不存在")
            self.conn.execute(
                """
                INSERT INTO material_request_items
                (request_id, material_id, repair_sku_id, qty, approved_qty, remark)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (request_id, item.material_id, item.repair_sku_id, item.qty, item.remark),
            )
        self.conn.commit()
        return self.material_request_detail(user, request_id)

    def material_requests(self, user: User, mine: bool = False) -> list[dict[str, Any]]:
        self._allowed(user, "warehouse:read")
        params: tuple[Any, ...] = ()
        where = ""
        if mine or user.role == Role.engineer:
            where = "WHERE r.engineer_user=? OR r.requested_by=?"
            params = (user.username, user.username)
        requests = self._rows(
            f"""
            SELECT r.*, ro.order_no
            FROM material_requests r
            LEFT JOIN repair_orders ro ON ro.repair_order_id=r.repair_order_id
            {where}
            ORDER BY r.created_at DESC, r.request_id DESC
            """,
            params,
        )
        for row in requests:
            row["items"] = self._rows(
                """
                SELECT i.*, m.sku, m.material_code, m.name, m.current_qty
                FROM material_request_items i
                JOIN materials m ON m.material_id=i.material_id
                WHERE i.request_id=?
                ORDER BY i.request_item_id
                """,
                (row["request_id"],),
            )
        return requests

    def material_request_detail(self, user: User, request_id: int) -> dict[str, Any]:
        row = self._one("SELECT * FROM material_requests WHERE request_id=?", (request_id,))
        if not row:
            raise BusinessError("申领单不存在")
        if user.role == Role.engineer and row.get("engineer_user") != user.username and row.get("requested_by") != user.username:
            raise PermissionError("工程师只能查看自己的申领单")
        row["items"] = self._rows(
            """
            SELECT i.*, m.sku, m.material_code, m.name, m.current_qty
            FROM material_request_items i
            JOIN materials m ON m.material_id=i.material_id
            WHERE i.request_id=?
            ORDER BY i.request_item_id
            """,
            (request_id,),
        )
        row["units"] = self._rows(
            "SELECT * FROM material_units WHERE request_id=? ORDER BY unit_id",
            (request_id,),
        )
        return row

    def approve_material_request(self, user: User, request_id: int, data: MaterialRequestActionInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:approve")
        req = self._one("SELECT * FROM material_requests WHERE request_id=?", (request_id,))
        if not req:
            raise BusinessError("申领单不存在")
        if req["status"] != "待审核":
            raise BusinessError("只有待审核申领单可以审核")
        for item in self._rows("SELECT * FROM material_request_items WHERE request_id=?", (request_id,)):
            approved = data.approved_qty if data.approved_qty is not None else item["qty"]
            self.conn.execute(
                "UPDATE material_request_items SET approved_qty=? WHERE request_item_id=?",
                (approved, item["request_item_id"]),
            )
        self.conn.execute(
            "UPDATE material_requests SET status='已审核待发放', approved_by=?, approved_at=CURRENT_TIMESTAMP WHERE request_id=?",
            (user.username, request_id),
        )
        self.conn.commit()
        return self.material_request_detail(user, request_id)

    def reject_material_request(self, user: User, request_id: int, data: MaterialRequestActionInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:approve")
        self.conn.execute(
            "UPDATE material_requests SET status='已拒绝', rejected_by=?, closed_at=CURRENT_TIMESTAMP, remark=? WHERE request_id=? AND status='待审核'",
            (user.username, data.remark, request_id),
        )
        self.conn.commit()
        return self.material_request_detail(user, request_id)

    def cancel_material_request(self, user: User, request_id: int, data: MaterialRequestActionInput) -> dict[str, Any]:
        req = self.material_request_detail(user, request_id)
        if req["status"] not in {"待审核", "已审核待发放"}:
            raise BusinessError("已发放或已关闭申领单不能取消，只能走退料/冲销")
        self.conn.execute(
            "UPDATE material_requests SET status='已取消', cancelled_by=?, closed_at=CURRENT_TIMESTAMP, remark=? WHERE request_id=?",
            (user.username, data.remark, request_id),
        )
        self.conn.commit()
        return self.material_request_detail(user, request_id)

    def issue_material_request(self, user: User, request_id: int, data: MaterialRequestActionInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:issue")
        req = self._one("SELECT * FROM material_requests WHERE request_id=?", (request_id,))
        if not req:
            raise BusinessError("申领单不存在")
        if req["status"] != "已审核待发放":
            raise BusinessError("申领单必须审核通过后才能发放")
        units = data.unit_ids
        if not units:
            for item in self._rows("SELECT * FROM material_request_items WHERE request_id=?", (request_id,)):
                rows = self._rows(
                    """
                    SELECT unit_id FROM material_units
                    WHERE material_id=? AND current_status='在库可用'
                    ORDER BY unit_id LIMIT ?
                    """,
                    (item["material_id"], int(item["approved_qty"] or item["qty"])),
                )
                units.extend(int(row["unit_id"]) for row in rows)
        if not units:
            raise BusinessError("没有选择可发放的单件码")
        issued_by_material: dict[int, int] = {}
        for unit_id in units:
            unit = self._one("SELECT * FROM material_units WHERE unit_id=?", (unit_id,))
            if not unit or unit["current_status"] != "在库可用":
                raise BusinessError("发放只能选择在库可用物料")
            item = self._one(
                """
                SELECT * FROM material_request_items
                WHERE request_id=? AND material_id=?
                ORDER BY request_item_id LIMIT 1
                """,
                (request_id, unit["material_id"]),
            )
            if not item:
                raise BusinessError("单件码不属于本申领单物料")
            allowed_qty = int(item["approved_qty"] or item["qty"])
            already = issued_by_material.get(int(unit["material_id"]), 0)
            if already >= allowed_qty:
                raise BusinessError("发放数量超过审核数量")
            issued_by_material[int(unit["material_id"])] = already + 1
            self.conn.execute(
                """
                UPDATE material_units
                SET current_status='已发放', engineer_user=?, repair_order_id=?, request_id=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE unit_id=?
                """,
                (req["engineer_user"], req["repair_order_id"], request_id, unit_id),
            )
            self.conn.execute(
                "UPDATE material_request_items SET issued_qty=issued_qty+1 WHERE request_item_id=?",
                (item["request_item_id"],),
            )
            if req.get("repair_order_id"):
                self.conn.execute(
                    """
                    INSERT INTO repair_materials
                    (repair_order_id, material_id, qty, unit_cost, total_cost, source_type, issued_by, issued_to, remark, source_key)
                    VALUES (?, ?, 1, ?, ?, '库存发放', ?, ?, ?, ?)
                    """,
                    (
                        req["repair_order_id"],
                        unit["material_id"],
                        unit["unit_cost"],
                        unit["unit_cost"],
                        user.username,
                        req["engineer_user"],
                        data.remark,
                        f"material_unit:{unit_id}",
                    ),
                )
                self.conn.execute(
                    """
                    INSERT INTO repair_cost_items
                    (repair_order_id, item_type, item_name, qty, unit_cost, total_cost, status, remark, source_key)
                    SELECT ?, '库存物料', name, 1, ?, ?, '已确认', ?, ?
                    FROM materials WHERE material_id=?
                    """,
                    (
                        req["repair_order_id"],
                        unit["unit_cost"],
                        unit["unit_cost"],
                        data.remark,
                        f"material_unit:{unit_id}",
                        unit["material_id"],
                    ),
                )
            self._stock_movement(
                int(unit["material_id"]),
                "仓库发放",
                -1,
                user.username,
                batch_id=unit.get("batch_id"),
                unit_id=unit_id,
                request_id=request_id,
                repair_order_id=req.get("repair_order_id"),
                location_id=unit.get("location_id"),
                unit_cost=float(unit.get("unit_cost") or 0),
                counterparty=req["engineer_user"],
                note=data.remark,
                source_type="material_request",
                source_id=request_id,
            )
            self._update_material_qty(int(unit["material_id"]))
        self.conn.execute(
            "UPDATE material_requests SET status='已发放', issued_by=?, issued_at=CURRENT_TIMESTAMP WHERE request_id=?",
            (user.username, request_id),
        )
        self.conn.commit()
        return self.material_request_detail(user, request_id)

    def request_material_return(self, user: User, unit_id: int, data: MaterialIssueReturnInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:request")
        unit = self._one("SELECT * FROM material_units WHERE unit_id=?", (unit_id,))
        if not unit:
            raise BusinessError("单件物料不存在")
        if unit["current_status"] not in {"已发放", "已使用", "拆回待检"}:
            raise BusinessError("只有已发放、已使用或拆回待检物料可以发起退料")
        if user.role == Role.engineer and unit.get("engineer_user") != user.username:
            raise PermissionError("工程师只能退回自己名下物料")
        cur = self.conn.execute(
            """
            INSERT INTO material_returns
            (unit_id, request_id, repair_order_id, engineer_user, return_type, remark)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (unit_id, unit.get("request_id"), unit.get("repair_order_id"), unit.get("engineer_user"), data.return_type, data.remark),
        )
        self.conn.execute(
            "UPDATE material_units SET current_status='退料待验收', updated_at=CURRENT_TIMESTAMP WHERE unit_id=?",
            (unit_id,),
        )
        self.conn.commit()
        return self._one("SELECT * FROM material_returns WHERE return_id=?", (int(cur.lastrowid),)) or {}

    def inspect_material_return(self, user: User, return_id: int, data: MaterialReturnInspectInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:issue")
        ret = self._one("SELECT * FROM material_returns WHERE return_id=?", (return_id,))
        if not ret:
            raise BusinessError("退料单不存在")
        if ret["status"] != "待验收":
            raise BusinessError("退料单已验收，不能重复处理")
        unit = self._one("SELECT * FROM material_units WHERE unit_id=?", (ret["unit_id"],))
        if not unit:
            raise BusinessError("退料单件不存在")
        result = data.inspect_result
        movement_qty = 0
        new_status = "已报损"
        status = "已报损"
        if result == "可复用":
            new_status = "在库可用"
            status = "已重新入库"
            movement_qty = 1
        elif result == "已损坏":
            new_status = "已报损"
            status = "已报损"
        elif result == "已使用拆回":
            new_status = "拆回待检"
            status = "拆回待检"
        elif result == "可退供应商":
            new_status = "拆回验收可退"
            status = "拆回验收可退"
        else:
            raise BusinessError("验收结果只能是 可复用、已损坏、已使用拆回 或 可退供应商")
        self.conn.execute(
            """
            UPDATE material_units
            SET current_status=?, engineer_user=CASE WHEN ?='在库可用' THEN '' ELSE engineer_user END,
                updated_at=CURRENT_TIMESTAMP
            WHERE unit_id=?
            """,
            (new_status, new_status, unit["unit_id"]),
        )
        self.conn.execute(
            """
            UPDATE material_returns
            SET status=?, inspect_result=?, inspected_by=?, inspected_at=CURRENT_TIMESTAMP, remark=?
            WHERE return_id=?
            """,
            (status, result, user.username, data.remark, return_id),
        )
        if movement_qty:
            self._stock_movement(
                int(unit["material_id"]),
                "工程师退料入库",
                movement_qty,
                user.username,
                batch_id=unit.get("batch_id"),
                unit_id=unit["unit_id"],
                request_id=unit.get("request_id"),
                repair_order_id=unit.get("repair_order_id"),
                location_id=unit.get("location_id"),
                unit_cost=float(unit.get("unit_cost") or 0),
                counterparty=ret.get("engineer_user") or "",
                note=data.remark,
                source_type="material_return",
                source_id=return_id,
            )
            if ret.get("repair_order_id"):
                self.conn.execute(
                    """
                    INSERT INTO repair_cost_items
                    (repair_order_id, item_type, item_name, qty, unit_cost, total_cost, status, remark, source_key)
                    SELECT ?, '退料冲减', name, -1, ?, -?, '已确认', ?, ?
                    FROM materials WHERE material_id=?
                    """,
                    (
                        ret["repair_order_id"],
                        unit["unit_cost"],
                        unit["unit_cost"],
                        data.remark or "可复用退料冲减成本",
                        f"material_return:{return_id}",
                        unit["material_id"],
                    ),
                )
        self._update_material_qty(int(unit["material_id"]))
        self.conn.commit()
        return self._one("SELECT * FROM material_returns WHERE return_id=?", (return_id,)) or {}

    def create_stock_count(self, user: User, data: StockCountInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:count")
        count_no = self._warehouse_code("COUNT", "stock_counts", "count_no")
        cur = self.conn.execute(
            "INSERT INTO stock_counts (count_no, counted_by, remark) VALUES (?, ?, ?)",
            (count_no, user.username, data.remark),
        )
        count_id = int(cur.lastrowid)
        for item in data.items:
            book_qty = item.book_qty
            if book_qty == 0:
                row = self._one(
                    "SELECT COUNT(*) AS qty FROM material_units WHERE material_id=? AND current_status='在库可用'",
                    (item.material_id,),
                )
                book_qty = float((row or {}).get("qty") or 0)
            self.conn.execute(
                """
                INSERT INTO stock_count_items
                (count_id, material_id, location_id, book_qty, actual_qty, diff_qty, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (count_id, item.material_id, item.location_id, book_qty, item.actual_qty, item.actual_qty - book_qty, item.reason),
            )
        self.conn.commit()
        return self._one("SELECT * FROM stock_counts WHERE count_id=?", (count_id,)) or {}

    def confirm_stock_count(self, user: User, count_id: int) -> dict[str, Any]:
        self._allowed(user, "warehouse:count")
        count = self._one("SELECT * FROM stock_counts WHERE count_id=?", (count_id,))
        if not count:
            raise BusinessError("盘点单不存在")
        if count["status"] != "草稿":
            raise BusinessError("盘点确认后不可删除或重复确认，只能做反向调整")
        for item in self._rows("SELECT * FROM stock_count_items WHERE count_id=?", (count_id,)):
            diff = int(item["diff_qty"])
            if diff > 0:
                self.create_stock_adjustment(
                    user,
                    StockAdjustmentInput(
                        material_id=item["material_id"],
                        location_id=item.get("location_id"),
                        qty=diff,
                        adjustment_type="盘盈入库",
                        reason=item.get("reason") or "盘点盘盈",
                    ),
                )
            elif diff < 0:
                self.create_stock_adjustment(
                    user,
                    StockAdjustmentInput(
                        material_id=item["material_id"],
                        location_id=item.get("location_id"),
                        qty=abs(diff),
                        adjustment_type="盘亏出库",
                        reason=item.get("reason") or "盘点盘亏",
                    ),
                )
        self.conn.execute(
            "UPDATE stock_counts SET status='已确认', confirmed_by=?, confirmed_at=CURRENT_TIMESTAMP WHERE count_id=?",
            (user.username, count_id),
        )
        self.conn.commit()
        return self._one("SELECT * FROM stock_counts WHERE count_id=?", (count_id,)) or {}

    def create_stock_adjustment(self, user: User, data: StockAdjustmentInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:count")
        material = self._one("SELECT * FROM materials WHERE material_id=?", (data.material_id,))
        if not material:
            raise BusinessError("物料不存在")
        adjustment_no = self._warehouse_code("ADJ", "stock_adjustments", "adjustment_no")
        movement_qty = data.qty
        unit_ids: list[int] = []
        if data.adjustment_type in {"盘盈入库", "反向调整入库"}:
            for index in range(1, data.qty + 1):
                unit_code = f"{material.get('material_code') or material.get('sku')}-ADJ-{uuid4().hex[:6].upper()}"
                cur = self.conn.execute(
                    """
                    INSERT INTO material_units
                    (material_id, unit_code, current_status, location_id, unit_cost, remark)
                    VALUES (?, ?, '在库可用', ?, ?, ?)
                    """,
                    (data.material_id, unit_code, data.location_id, material.get("avg_cost") or 0, data.reason),
                )
                unit_ids.append(int(cur.lastrowid))
        elif data.adjustment_type in {"盘亏出库", "报损出库", "反向调整出库"}:
            rows = self._rows(
                """
                SELECT unit_id FROM material_units
                WHERE material_id=? AND current_status='在库可用'
                ORDER BY unit_id LIMIT ?
                """,
                (data.material_id, data.qty),
            )
            if len(rows) < data.qty:
                raise BusinessError("可用库存不足，不能盘亏/报损出库")
            unit_ids = [int(row["unit_id"]) for row in rows]
            for unit_id in unit_ids:
                self.conn.execute(
                    "UPDATE material_units SET current_status=?, updated_at=CURRENT_TIMESTAMP WHERE unit_id=?",
                    ("已报损" if data.adjustment_type == "报损出库" else "盘亏", unit_id),
                )
            movement_qty = -data.qty
        else:
            raise BusinessError("调整类型必须是盘盈入库、盘亏出库、报损出库或反向调整")
        cur = self.conn.execute(
            """
            INSERT INTO stock_adjustments
            (adjustment_no, material_id, unit_id, location_id, qty, adjustment_type, reason, operator)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (adjustment_no, data.material_id, data.unit_id or (unit_ids[0] if unit_ids else None), data.location_id, data.qty, data.adjustment_type, data.reason, user.username),
        )
        self._stock_movement(
            data.material_id,
            data.adjustment_type,
            movement_qty,
            user.username,
            unit_id=unit_ids[0] if unit_ids else data.unit_id,
            location_id=data.location_id,
            unit_cost=float(material.get("avg_cost") or 0),
            note=data.reason,
            source_type="stock_adjustment",
            source_id=int(cur.lastrowid),
        )
        self._update_material_qty(data.material_id)
        self.conn.commit()
        return self._one("SELECT * FROM stock_adjustments WHERE adjustment_id=?", (int(cur.lastrowid),)) or {}

    def stock_movements(self, user: User) -> list[dict[str, Any]]:
        self._allowed(user, "warehouse:read")
        return self._rows(
            """
            SELECT sm.*, m.sku, m.material_code, m.name, u.unit_code, ro.order_no, l.location_code
            FROM stock_movements sm
            JOIN materials m ON m.material_id=sm.material_id
            LEFT JOIN material_units u ON u.unit_id=sm.unit_id
            LEFT JOIN repair_orders ro ON ro.repair_order_id=sm.repair_order_id
            LEFT JOIN warehouse_locations l ON l.location_id=sm.location_id
            ORDER BY sm.happened_at DESC, sm.stock_movement_id DESC
            LIMIT 500
            """
        )

    def upsert_repair_fault_material(self, user: User, data: RepairFaultMaterialInput) -> dict[str, Any]:
        self._allowed(user, "warehouse:write")
        self.conn.execute(
            """
            INSERT INTO repair_fault_materials (repair_sku_id, material_id, qty, priority, remark)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(repair_sku_id, material_id) DO UPDATE SET qty=excluded.qty,
                priority=excluded.priority, remark=excluded.remark, updated_at=CURRENT_TIMESTAMP
            """,
            (data.repair_sku_id, data.material_id, data.qty, data.priority, data.remark),
        )
        self.conn.commit()
        return self._one(
            "SELECT * FROM repair_fault_materials WHERE repair_sku_id=? AND material_id=?",
            (data.repair_sku_id, data.material_id),
        ) or {}

    def repair_fault_materials(self, user: User) -> list[dict[str, Any]]:
        self._allowed(user, "warehouse:read")
        return self._rows(
            """
            SELECT b.*, rs.sku_code, rs.fault_name, rs.solution_name,
                   m.sku, m.material_code, m.name, m.current_qty, m.min_qty
            FROM repair_fault_materials b
            JOIN repair_skus rs ON rs.sku_id=b.repair_sku_id
            JOIN materials m ON m.material_id=b.material_id
            ORDER BY b.priority, rs.sku_code, m.name
            """
        )

    def material_hints_for_sku(self, user: User, sku_id: int) -> dict[str, Any]:
        self._allowed(user, "warehouse:read")
        sku = self._one("SELECT * FROM repair_skus WHERE sku_id=?", (sku_id,))
        if not sku:
            raise BusinessError("维修故障 SKU 不存在")
        hints = self._rows(
            """
            SELECT b.*, m.sku, m.material_code, m.name, m.current_qty, m.min_qty,
                   GROUP_CONCAT(DISTINCT l.location_code) AS locations,
                   SUM(CASE WHEN u.current_status='已发放' THEN 1 ELSE 0 END) AS pending_issue_qty
            FROM repair_fault_materials b
            JOIN materials m ON m.material_id=b.material_id
            LEFT JOIN material_units u ON u.material_id=m.material_id
            LEFT JOIN warehouse_locations l ON l.location_id=u.location_id
            WHERE b.repair_sku_id=?
            GROUP BY b.binding_id
            ORDER BY b.priority, m.name
            """,
            (sku_id,),
        )
        for hint in hints:
            hint["low_stock"] = float(hint.get("min_qty") or 0) > 0 and float(hint.get("current_qty") or 0) <= float(hint.get("min_qty") or 0)
            hint["stock_warning"] = "库存不足，需临采入库" if float(hint.get("current_qty") or 0) < float(hint.get("qty") or 0) else ""
        return {"repair_sku": sku, "materials": hints}

    def material_hints_for_order(self, user: User, repair_order_id: int) -> dict[str, Any]:
        self._allowed(user, "warehouse:read")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        sku_ids = [int(row["sku_id"]) for row in self._rows("SELECT DISTINCT sku_id FROM repair_items WHERE repair_order_id=? AND sku_id IS NOT NULL", (repair_order_id,))]
        hints = [self.material_hints_for_sku(user, sku_id) for sku_id in sku_ids]
        return {"repair_order": order, "hints": hints}

    def apply_repair_workflow_action(self, user: User, repair_order_id: int, data: RepairWorkflowActionInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        action = data.action.strip()
        machine_id = int(order["machine_id"])
        title = "维修流程"
        detail = data.remark or action
        if action == "repair_completed":
            self.conn.execute(
                "UPDATE repair_orders SET status='维修完成', workflow_status='待交付检测', completed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?",
                (repair_order_id,),
            )
            self.repo.update_machine_status(machine_id, "维修完成")
            title = "维修完成"
        elif action == "delivered":
            next_status = data.status or "已交付"
            if next_status not in {"已交付", "待取机", "待送机", "待返寄"}:
                raise BusinessError("交付动作只能进入 已交付、待取机、待送机 或 待返寄")
            self.conn.execute(
                "UPDATE repair_orders SET status=?, workflow_status='待收款/财务确认', delivered_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?",
                (next_status, repair_order_id),
            )
            self.repo.update_machine_status(machine_id, next_status)
            title = "交付流转"
            detail = next_status if not data.remark else f"{next_status}；{data.remark}"
        elif action == "register_payment":
            self._allowed(user, "payment:create")
            amount = float(data.amount or 0)
            if amount <= 0:
                raise BusinessError("登记收款金额必须大于 0")
            cur = self.conn.execute(
                """
                INSERT INTO payments
                (source_type, source_id, direction, amount, method, account, transaction_no,
                 payer, payee, operator, received_by, status, paid_at, remark)
                VALUES ('repair', ?, '收入', ?, ?, ?, ?, '', '', ?, ?, '已付款待财务确认',
                        CURRENT_TIMESTAMP, ?)
                """,
                (
                    repair_order_id,
                    amount,
                    data.method or "待确认",
                    data.account,
                    data.transaction_no,
                    user.username,
                    data.received_by or user.username,
                    data.remark or "前台收款，待财务确认",
                ),
            )
            self.conn.execute(
                "UPDATE repair_orders SET payment_status='已付款待财务确认', settlement_status='未结', status='财务待确认', updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?",
                (repair_order_id,),
            )
            self.repo.add_machine_event(machine_id, "payment", "登记收款", f"金额 {amount}，待财务确认", user.username, "payment", int(cur.lastrowid))
            title = "登记收款"
            detail = f"金额 {amount}，待财务确认"
        elif action == "finance_confirm":
            self._allowed(user, "payment:create")
            confirmed_by = data.confirmed_by or user.username
            self.conn.execute(
                """
                UPDATE payments
                SET status='财务已确认', confirmed_by=?,
                    confirmed_at=CASE WHEN ?='' THEN CURRENT_TIMESTAMP ELSE ? END
                WHERE source_type='repair' AND source_id=? AND status='已付款待财务确认'
                """,
                (confirmed_by, data.confirmed_at, data.confirmed_at, repair_order_id),
            )
            self.conn.execute(
                """
                UPDATE repair_orders
                SET payment_status='财务已确认', settlement_status='已结', status='已完结',
                    closed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                WHERE repair_order_id=?
                """,
                (repair_order_id,),
            )
            self.repo.close_machine(machine_id, "已结单")
            title = "财务确认"
            detail = f"确认人：{confirmed_by}"
        elif action == "mark_receivable":
            amount = float(data.amount if data.amount is not None else order.get("quoted_amount") or 0)
            receivable_type = data.payment_status or "同行挂账"
            self.conn.execute(
                """
                INSERT INTO receivables
                (repair_order_id, customer_id, customer_name, counter_no, receivable_type,
                 amount, status, remark, source_key)
                VALUES (?, ?, ?, ?, ?, ?, '未结', ?, ?)
                """,
                (
                    repair_order_id,
                    order.get("customer_id"),
                    order.get("customer_name") or "待补",
                    order.get("counter_no") or "",
                    receivable_type,
                    amount,
                    data.remark or "同行挂账/未收款",
                    f"manual-receivable-{repair_order_id}",
                ),
            )
            status = "同行挂账" if receivable_type == "同行挂账" else "已交付"
            self.conn.execute(
                "UPDATE repair_orders SET payment_status=?, settlement_status='未结', status=?, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?",
                (receivable_type, status, repair_order_id),
            )
            title = "挂账登记"
            detail = f"{receivable_type}：{amount}"
        elif action == "settle_receivable":
            self._allowed(user, "settlement:create")
            self.conn.execute(
                "UPDATE receivables SET status='已结', settled_at=CURRENT_TIMESTAMP, remark=CASE WHEN ?='' THEN remark ELSE ? END WHERE repair_order_id=? AND status<>'已结'",
                (data.remark, data.remark, repair_order_id),
            )
            self.conn.execute(
                "UPDATE repair_orders SET payment_status='财务已确认', settlement_status='已结', status='已完结', closed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?",
                (repair_order_id,),
            )
            self.repo.close_machine(machine_id, "已结单")
            title = "挂账结清"
        elif action == "close":
            refreshed = self.repo.get_repair_order(repair_order_id) or order
            if refreshed.get("status") == "维修完成":
                raise BusinessError("维修完成后必须先交付、收款/挂账或财务确认，不能直接完结")
            if refreshed.get("payment_status") not in {"财务已确认", "预付款已收", "无需收款"}:
                raise BusinessError("只有财务已确认、预付款已收或无需收款的工单可以完结")
            self.conn.execute(
                "UPDATE repair_orders SET status='已完结', settlement_status='已结', closed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?",
                (repair_order_id,),
            )
            self.repo.close_machine(machine_id, "已结单")
            title = "订单完结"
        else:
            raise BusinessError("未知维修闭环动作")
        self.repo.add_machine_event(machine_id, "repair", title, detail, user.username, "repair", repair_order_id)
        self._log_success(user, f"repair_order:{action}", "repair_order", str(repair_order_id), customer_id=order.get("customer_id"), request_summary=detail)
        self.conn.commit()
        return self.repair_workbench_detail(user, repair_order_id)

    def upsert_repair_sku(self, user: User, data: RepairSkuInput) -> dict[str, Any]:
        self._allowed(user, "repair_sku:write")
        sku_id = self.repo.upsert_repair_sku(data.model_dump())
        self._log_success(user, "repair_sku:upsert", "repair_sku", str(sku_id), request_summary=data.sku_code)
        self.conn.commit()
        return self.repo.get_repair_sku(sku_id) or {}

    def assign_repair_order(self, user: User, repair_order_id: int, data: RepairAssignInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:assign")
        self._ensure_frontdesk_or_admin(user)
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        status = self._repair_order_status(order)
        if status in {OrderStatus.closed, OrderStatus.cancelled}:
            raise BusinessError("维修单已结束，不能指派")
        engineer = self.repo.get_user(data.engineer_user_id)
        if not engineer or engineer["role"] not in {Role.engineer.value, Role.staff.value, Role.admin.value}:
            raise BusinessError("被指派账号不存在或不是工程师")
        before = order.get("assigned_to") or "未指派"
        workflow = "工程师待检测" if status == OrderStatus.opened else "工程师维修中"
        self.repo.assign_repair_order(repair_order_id, data.engineer_user_id, workflow)
        self.repo.assign_machine(int(order["machine_id"]), data.engineer_user_id)
        detail = f"{before} -> {data.engineer_user_id}"
        if data.remark:
            detail = f"{detail}；{data.remark}"
        self.repo.add_machine_event(int(order["machine_id"]), "repair", "指派工程师", detail, user.username, "repair", repair_order_id)
        self._log_success(user, "repair_order:assign", "repair_order", str(repair_order_id), customer_id=order["customer_id"], request_summary=detail)
        self.conn.commit()
        return self._repair_order_response(repair_order_id)

    def quote_repair_order(self, user: User, repair_order_id: int, data: RepairQuoteInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        self._ensure_engineer_owns_repair(user, order)
        self._ensure_repair_transition(order, OrderStatus.quoted, {OrderStatus.diagnosing})
        sku_total = 0.0
        sku_names: list[str] = []
        for sku_id in data.sku_ids:
            sku = self.repo.get_repair_sku(sku_id)
            if not sku or not int(sku.get("enabled", 1)):
                raise BusinessError(f"维修 SKU 不存在或已停用：{sku_id}")
            sku_total += float(sku["charge_amount"] or 0)
            sku_names.append(f"{sku['fault_name']}/{sku['solution_name']}")
        quoted_amount = data.quoted_amount or sku_total
        fault_detail = data.fault_detail or data.diagnosis
        repair_solution = data.repair_solution or "；".join(sku_names)
        self.repo.quote_repair_order(repair_order_id, data.diagnosis, quoted_amount, OrderStatus.quoted.value, fault_detail, repair_solution, "待客户确认")
        self.repo.update_machine_status(int(order["machine_id"]), MachineStatus.quoted.value)
        detail = f"{data.diagnosis}，报价 {quoted_amount}"
        if repair_solution:
            detail = f"{detail}；方案：{repair_solution}"
        self.repo.add_machine_event(int(order["machine_id"]), "repair", "检测报价", detail, user.username, "repair", repair_order_id)
        if sku_names:
            self.repo.add_machine_event(int(order["machine_id"]), "repair", "SKU 报价明细", "；".join(sku_names), user.username, "repair", repair_order_id)
        self._log_success(user, "repair_order:quote", "repair_order", str(repair_order_id), customer_id=order["customer_id"], request_summary=str(quoted_amount))
        self.conn.commit()
        return self._repair_order_response(repair_order_id)

    def confirm_repair_quote(self, user: User, repair_order_id: int, data: RepairQuoteConfirmInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:confirm")
        self._ensure_frontdesk_or_admin(user)
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        self._ensure_repair_transition(order, OrderStatus.processing, {OrderStatus.quoted})
        result = data.confirm_result.strip()
        if result not in {"客户同意维修", "客户拒修", "待考虑"}:
            raise BusinessError("确认结果必须是 客户同意维修、客户拒修 或 待考虑")
        if result == "客户同意维修":
            status = OrderStatus.processing.value
            workflow = "工程师维修中"
            machine_status = MachineStatus.repairing.value
            title = "报价确认"
        elif result == "客户拒修":
            status = OrderStatus.cancelled.value
            workflow = "待客户取回"
            machine_status = None
            title = "客户拒修"
        else:
            status = OrderStatus.quoted.value
            workflow = "待客户确认"
            machine_status = None
            title = "客户待考虑"
        self.repo.confirm_repair_quote(repair_order_id, status, workflow, result, data.confirm_method, data.contact_person, data.remark)
        if machine_status:
            self.repo.update_machine_status(int(order["machine_id"]), machine_status)
        detail = f"{result}；方式：{data.confirm_method or '未填'}；联系人：{data.contact_person or '未填'}"
        if data.remark:
            detail = f"{detail}；{data.remark}"
        self.repo.add_machine_event(int(order["machine_id"]), "repair", title, detail, user.username, "repair", repair_order_id)
        self._log_success(user, "repair_order:quote_confirm", "repair_order", str(repair_order_id), customer_id=order["customer_id"], request_summary=result)
        self.conn.commit()
        return self._repair_order_response(repair_order_id)

    def change_repair_order_price(self, user: User, repair_order_id: int, data: PriceChangeInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        self._ensure_engineer_owns_repair(user, order)
        old_amount = float(order["quoted_amount"] or 0)
        self.repo.update_repair_order_price(repair_order_id, data.quoted_amount)
        detail = f"报价 {old_amount} -> {data.quoted_amount}"
        if data.remark:
            detail = f"{detail}；{data.remark}"
        self.repo.add_machine_event(int(order["machine_id"]), "repair", "维修改价", detail, user.username, "repair", repair_order_id)
        self._log_success(user, "repair_order:price", "repair_order", str(repair_order_id), customer_id=order["customer_id"], request_summary=str(data.quoted_amount))
        self.conn.commit()
        return self._repair_order_response(repair_order_id)

    def append_repair_order_remark(self, user: User, repair_order_id: int, data: RepairRemarkInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        self._ensure_engineer_owns_repair(user, order)
        addition = data.remark.strip()
        if not addition:
            raise BusinessError("备注内容不能为空")
        note_type = "内部备注"
        content = addition
        match = re.match(r"^【(.+?)】(.+)$", addition)
        if match:
            note_type = match.group(1).strip() or note_type
            content = match.group(2).strip() or content
        note_id = self.repo.add_repair_order_note(repair_order_id, note_type, content, user.username)
        current = str(order.get("remark") or "").strip()
        merged = f"{current}\n{addition}" if current else addition
        self.repo.update_repair_order_remark(repair_order_id, merged)
        self.repo.add_machine_event(int(order["machine_id"]), "repair", "新增工单备注", addition, user.username, "repair_note", note_id)
        self._log_success(user, "repair_order:remark", "repair_order", str(repair_order_id), customer_id=order.get("customer_id"), request_summary=addition)
        self.conn.commit()
        return self._repair_order_response(repair_order_id)

    def update_repair_order_note(self, user: User, repair_order_id: int, note_id: int, data: RepairOrderNoteUpdateInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        note = self.repo.get_repair_order_note(note_id)
        if not order or not note or int(note["repair_order_id"]) != repair_order_id or int(note.get("is_deleted") or 0):
            raise BusinessError("备注不存在")
        self._ensure_engineer_owns_repair(user, order)
        note_type = data.note_type.strip() or "内部备注"
        content = data.content.strip()
        if not content:
            raise BusinessError("备注内容不能为空")
        old_detail = f"{note.get('note_type') or '内部备注'}：{note.get('content') or ''}"
        new_detail = f"{note_type}：{content}"
        self.repo.update_repair_order_note(note_id, note_type, content, user.username)
        self.repo.add_machine_event(int(order["machine_id"]), "repair", "修改工单备注", f"{old_detail} -> {new_detail}", user.username, "repair_note", note_id)
        self._log_success(user, "repair_order:note:update", "repair_note", str(note_id), customer_id=order.get("customer_id"), request_summary=new_detail)
        self.conn.commit()
        return self._repair_order_response(repair_order_id)

    def delete_repair_order_note(self, user: User, repair_order_id: int, note_id: int, data: RepairOrderNoteDeleteInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        note = self.repo.get_repair_order_note(note_id)
        if not order or not note or int(note["repair_order_id"]) != repair_order_id or int(note.get("is_deleted") or 0):
            raise BusinessError("备注不存在")
        self._ensure_engineer_owns_repair(user, order)
        reason = data.reason.strip()
        detail = f"{note.get('note_type') or '内部备注'}：{note.get('content') or ''}"
        if reason:
            detail = f"{detail}；原因：{reason}"
        self.repo.delete_repair_order_note(note_id, user.username, reason)
        self.repo.add_machine_event(int(order["machine_id"]), "repair", "删除工单备注", detail, user.username, "repair_note", note_id)
        self._log_success(user, "repair_order:note:delete", "repair_note", str(note_id), customer_id=order.get("customer_id"), request_summary=detail)
        self.conn.commit()
        return self._repair_order_response(repair_order_id)

    def add_repair_item(self, user: User, repair_order_id: int, data: RepairItemInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        self._ensure_engineer_owns_repair(user, order)
        self._ensure_repair_transition(order, OrderStatus.processing, {OrderStatus.quoted, OrderStatus.processing})
        if order.get("assigned_to") and not order.get("quote_confirm_status") and self._repair_order_status(order) == OrderStatus.quoted:
            raise BusinessError("报价需由前台确认后才能开始维修")
        item_name = data.item_name
        cost_amount = data.cost_amount
        charge_amount = data.charge_amount
        if data.sku_id:
            sku = self.repo.get_repair_sku(data.sku_id)
            if not sku or not int(sku.get("enabled", 1)):
                raise BusinessError("维修 SKU 不存在或已停用")
            item_name = data.item_name if data.item_name else sku["solution_name"]
            if not self._input_has_field(data, "cost_amount"):
                cost_amount = float(sku["cost_amount"] or 0)
            if not self._input_has_field(data, "charge_amount"):
                charge_amount = float(sku["charge_amount"] or 0)
        item_id = self.repo.add_repair_item(repair_order_id, item_name, data.quantity, cost_amount, charge_amount, data.remark, data.sku_id)
        self.repo.quote_repair_order(
            repair_order_id,
            order["diagnosis"],
            float(order["quoted_amount"]),
            OrderStatus.processing.value,
            order.get("fault_detail", ""),
            order.get("repair_solution", ""),
            "工程师维修中",
        )
        self.conn.execute("UPDATE repair_orders SET workflow_status='工程师维修中', updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?", (repair_order_id,))
        self.repo.update_machine_status(int(order["machine_id"]), MachineStatus.repairing.value)
        self.repo.add_machine_event(int(order["machine_id"]), "repair", "维修项目", f"{item_name} x{data.quantity}", user.username, "repair_item", item_id)
        self._log_success(user, "repair_order:item", "repair_item", str(item_id), customer_id=order["customer_id"], request_summary=item_name)
        self.conn.commit()
        detail = self._repair_order_response(repair_order_id)
        detail["repair_item_id"] = item_id
        return detail

    def update_repair_order_status(self, user: User, repair_order_id: int, data: RepairOrderStatusInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        self._ensure_engineer_owns_repair(user, order)
        allowed = {
            OrderStatus.diagnosing: {OrderStatus.opened},
            OrderStatus.ready: {OrderStatus.processing},
            OrderStatus.cancelled: {
                OrderStatus.opened,
                OrderStatus.diagnosing,
                OrderStatus.quoted,
                OrderStatus.processing,
                OrderStatus.ready,
            },
        }
        if data.status not in allowed:
            raise BusinessError("该状态必须通过报价、维修项目、交付或收款等专用动作进入")
        self._ensure_repair_transition(order, data.status, allowed[data.status])
        if data.status == OrderStatus.cancelled:
            issued = self._rows(
                """
                SELECT unit_code FROM material_units
                WHERE repair_order_id=? AND current_status IN ('已发放', '已使用', '退料待验收', '拆回待检')
                """,
                (repair_order_id,),
            )
            if issued:
                codes = "、".join(row["unit_code"] for row in issued[:3])
                raise BusinessError(f"工单已有未闭环领料，需先退料或确认报损后才能取消：{codes}")
        self.repo.update_repair_order_status(repair_order_id, data.status.value, data.remark)
        if data.status == OrderStatus.cancelled:
            self.repo.add_machine_event(int(order["machine_id"]), "repair", "维修作废", data.remark, user.username, "repair", repair_order_id)
        else:
            self.repo.update_machine_status(int(order["machine_id"]), self._repair_machine_status(data.status).value)
            self.repo.add_machine_event(int(order["machine_id"]), "repair", f"维修{data.status.value}", data.remark, user.username, "repair", repair_order_id)
        self._log_success(user, "repair_order:status", "repair_order", str(repair_order_id), customer_id=order["customer_id"], request_summary=data.status.value)
        self.conn.commit()
        return self._repair_order_response(repair_order_id)

    def engineer_close_repair_order(self, user: User, repair_order_id: int, data: RepairEngineerCloseInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:engineer_close")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        self._ensure_engineer_owns_repair(user, order)
        status = self._repair_order_status(order)
        if status not in {OrderStatus.processing, OrderStatus.ready}:
            raise BusinessError("只有维修中或待交付订单可以工程师结单")
        if not self.repo.list_repair_items(repair_order_id):
            raise BusinessError("请先记录维修项目后再工程师结单")
        self.repo.engineer_close_repair_order(repair_order_id, data.remark)
        self.repo.update_machine_status(int(order["machine_id"]), MachineStatus.ready_for_delivery.value)
        self.repo.add_machine_event(int(order["machine_id"]), "repair", "工程师结单", data.remark, user.username, "repair", repair_order_id)
        self._log_success(user, "repair_order:engineer_close", "repair_order", str(repair_order_id), customer_id=order["customer_id"], request_summary=data.remark)
        self.conn.commit()
        return self._repair_order_response(repair_order_id)

    def deliver_repair_order(self, user: User, repair_order_id: int, data: RepairDeliverInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        self._ensure_repair_transition(order, OrderStatus.delivered, {OrderStatus.ready})
        self.repo.deliver_repair_order(repair_order_id, data.delivery_check, data.remark, OrderStatus.delivered.value)
        self.repo.update_machine_status(int(order["machine_id"]), MachineStatus.delivered.value)
        self.repo.add_machine_event(int(order["machine_id"]), "repair", "交付检测", data.delivery_check, user.username, "repair", repair_order_id)
        self._log_success(user, "repair_order:deliver", "repair_order", str(repair_order_id), customer_id=order["customer_id"], request_summary=data.delivery_check)
        self.conn.commit()
        return self._repair_order_response(repair_order_id)

    def create_recycle_order(self, user: User, data: RecycleOrderInput) -> dict[str, Any]:
        self._allowed(user, "recycle_order:create")
        customer_id = self._customer_id(data.customer_id, data.customer)
        machine = self._ensure_machine(user, data.machine_id, data.machine, BusinessLine.recycle)
        if not customer_id:
            customer_id = machine.get("customer_id")
        machine_id = int(machine["machine_id"])
        order_id = self.repo.create_recycle_order(
            machine_id,
            customer_id,
            OrderStatus.opened.value,
            data.inspection_note,
            data.remark,
            user.username,
        )
        self.repo.update_machine_status(machine_id, MachineStatus.diagnosing.value, BusinessLine.recycle.value)
        self.repo.add_machine_event(machine_id, "recycle", "回收开单", data.inspection_note, user.username, "recycle", order_id)
        self._log_success(user, "recycle_order:create", "recycle_order", str(order_id), customer_id=customer_id, request_summary=data.inspection_note)
        self.conn.commit()
        return self.repo.get_recycle_order(order_id) or {}

    def quote_recycle_order(self, user: User, recycle_order_id: int, data: RecycleQuoteInput) -> dict[str, Any]:
        self._allowed(user, "recycle_order:update")
        order = self.repo.get_recycle_order(recycle_order_id)
        if not order:
            raise BusinessError("回收单不存在")
        self.repo.quote_recycle_order(recycle_order_id, data.inspection_result, data.quoted_amount, OrderStatus.quoted.value)
        self.repo.update_machine_status(int(order["machine_id"]), MachineStatus.quoted.value)
        self.repo.add_machine_event(int(order["machine_id"]), "recycle", "验机报价", f"{data.inspection_result}，报价 {data.quoted_amount}", user.username, "recycle", recycle_order_id)
        self._log_success(user, "recycle_order:quote", "recycle_order", str(recycle_order_id), customer_id=order["customer_id"], request_summary=str(data.quoted_amount))
        self.conn.commit()
        return self.repo.get_recycle_order(recycle_order_id) or {}

    def change_recycle_order_price(self, user: User, recycle_order_id: int, data: PriceChangeInput) -> dict[str, Any]:
        self._allowed(user, "recycle_order:update")
        order = self.repo.get_recycle_order(recycle_order_id)
        if not order:
            raise BusinessError("回收单不存在")
        old_amount = float(order["quoted_amount"] or 0)
        self.repo.update_recycle_order_price(recycle_order_id, data.quoted_amount)
        detail = f"报价 {old_amount} -> {data.quoted_amount}"
        if data.remark:
            detail = f"{detail}；{data.remark}"
        self.repo.add_machine_event(int(order["machine_id"]), "recycle", "回收改价", detail, user.username, "recycle", recycle_order_id)
        self._log_success(user, "recycle_order:price", "recycle_order", str(recycle_order_id), customer_id=order["customer_id"], request_summary=str(data.quoted_amount))
        self.conn.commit()
        return self.repo.get_recycle_order(recycle_order_id) or {}

    def stock_in_recycle_order(self, user: User, recycle_order_id: int, data: StockInInput) -> dict[str, Any]:
        self._allowed(user, "recycle_order:update")
        order = self.repo.get_recycle_order(recycle_order_id)
        if not order:
            raise BusinessError("回收单不存在")
        if float(order["quoted_amount"]) <= 0:
            raise BusinessError("请先完成验机报价")
        self.repo.stock_in_recycle_order(recycle_order_id, data.pay_amount, OrderStatus.stocked.value)
        inventory_id = self.repo.create_inventory_item(int(order["machine_id"]), recycle_order_id, "可销售", data.pay_amount, data.sale_price)
        self.repo.update_machine_status(int(order["machine_id"]), MachineStatus.in_recycle_stock.value)
        self.repo.add_machine_event(int(order["machine_id"]), "inventory", "回收入库", f"成本 {data.pay_amount}，销售定价 {data.sale_price}", user.username, "inventory", inventory_id)
        self.create_payment(
            user,
            PaymentInput(
                source_type="recycle",
                source_id=recycle_order_id,
                direction=PaymentDirection.expense,
                amount=data.pay_amount,
                remark=data.remark or "回收付款",
            ),
            commit=False,
        )
        self._log_success(user, "recycle_order:stock_in", "inventory", str(inventory_id), customer_id=order["customer_id"], request_summary=str(data.pay_amount))
        self.conn.commit()
        return self.repo.get_inventory_item(inventory_id) or {}

    def list_inventory(self, user: User) -> list[dict[str, Any]]:
        self._allowed(user, "inventory:read")
        return self.repo.list_inventory_items()

    def create_sales_order(self, user: User, data: SalesOrderInput) -> dict[str, Any]:
        self._allowed(user, "sales_order:create")
        inventory = self.repo.get_inventory_item(data.inventory_item_id)
        if not inventory:
            raise BusinessError("库存项不存在")
        if inventory["status"] == "已售出":
            raise BusinessError("该机器已经售出")
        customer_id = self._customer_id(data.customer_id, data.customer)
        order_id = self.repo.create_sales_order(
            data.inventory_item_id,
            int(inventory["machine_id"]),
            customer_id,
            OrderStatus.sold.value,
            data.sale_price,
            data.salesperson,
            data.remark,
            user.username,
        )
        self.repo.mark_inventory_sold(data.inventory_item_id)
        self.repo.update_machine_status(int(inventory["machine_id"]), MachineStatus.sold.value)
        self.repo.add_machine_event(int(inventory["machine_id"]), "sale", "销售开单", f"销售价 {data.sale_price}", user.username, "sale", order_id)
        self._log_success(user, "sales_order:create", "sales_order", str(order_id), customer_id=customer_id, request_summary=str(data.sale_price))
        self.conn.commit()
        return self.repo.get_sales_order(order_id) or {}

    def create_payment(self, user: User, data: PaymentInput, commit: bool = True) -> dict[str, Any]:
        self._allowed(user, "payment:create")
        if data.source_type == "repair":
            order = self.repo.get_repair_order(data.source_id)
            if not order:
                raise BusinessError("维修单不存在")
            status = self._repair_order_status(order)
            if status == OrderStatus.cancelled:
                raise BusinessError("作废维修单不能收款")
            if status == OrderStatus.closed:
                raise BusinessError("维修单已结单，不能重复收款")
            if status != OrderStatus.delivered:
                raise BusinessError("维修单交付后才能收款结单")
            if order.get("assigned_to") and not order.get("engineer_closed_at"):
                raise BusinessError("工程师结单后才能由前台收费")
            if data.direction != PaymentDirection.income:
                raise BusinessError("维修单只能登记收入流水")
        payment_id = self.repo.create_payment(
            {
                "source_type": data.source_type,
                "source_id": data.source_id,
                "direction": data.direction.value,
                "amount": data.amount,
                "method": data.method,
                "payer": data.payer,
                "payee": data.payee,
                "operator": user.username,
                "remark": data.remark,
            }
        )
        machine_id = self.repo.close_source_by_payment(data.source_type, data.source_id)
        if machine_id:
            self.repo.add_machine_event(machine_id, "payment", f"{data.direction.value}流水", f"金额 {data.amount}", user.username, "payment", payment_id)
        self._log_success(user, "payment:create", "payment", str(payment_id), request_summary=f"{data.direction.value} {data.amount}")
        if commit:
            self.conn.commit()
        return {"payment_id": payment_id, "machine_id": machine_id}

    def list_payments(self, user: User) -> list[dict[str, Any]]:
        self._allowed(user, "payment:read")
        return self.repo.list_payments()

    def machine_reports(self, user: User) -> dict[str, Any]:
        self._allowed(user, "report:read")
        return self.repo.machine_reports()

    def create_purchase(self, user: User, data: PurchaseInput) -> dict[str, Any]:
        self._allowed(user, "purchase:create")
        if self.repo.get_device(data.imei):
            raise BusinessError("IMEI 已存在，不能重复入库")
        customer_id = data.customer_id
        if data.customer:
            customer_id = self.repo.upsert_customer(data.customer)
        self.repo.create_device(data, customer_id)
        self._log_success(user, "purchase:create", "device", data.imei, imei=data.imei, customer_id=customer_id, request_summary=data.model)
        self.conn.commit()
        return self.repo.get_device(data.imei) or {}

    def list_stock(self, user: User) -> list[dict[str, Any]]:
        self._allowed(user, "device:read")
        return self.repo.list_devices(DeviceStatus.in_stock.value)

    def sell_device(self, user: User, data: SellDeviceInput) -> dict[str, Any]:
        self._allowed(user, "device:sell")
        device = self.repo.get_device(data.imei)
        if not device:
            raise BusinessError("设备不存在")
        if device["status"] != DeviceStatus.in_stock.value:
            raise BusinessError("只有在库设备可以销售出库")
        self.repo.sell_device(
            data.imei,
            data.buyer_customer_id,
            data.buyer,
            data.salesperson,
            data.sale_time,
            data.sale_price,
            data.settlement_status,
        )
        self._log_success(user, "device:sell", "device", data.imei, imei=data.imei, customer_id=data.buyer_customer_id, request_summary=data.buyer)
        self.conn.commit()
        return self.repo.get_device(data.imei) or {}

    def create_repair(self, user: User, data: RepairInput) -> dict[str, Any]:
        self._allowed(user, "repair:create")
        customer_id = data.customer_id
        if data.customer:
            customer_id = self.repo.upsert_customer(data.customer)
        if not customer_id and data.customer_name:
            customer_id = self.repo.upsert_customer(CustomerInput(name=data.customer_name))
        repair_id = self.repo.create_repair(data, customer_id)
        self._log_success(user, "repair:create", "repair", str(repair_id), customer_id=customer_id, request_summary=data.customer_name)
        self.conn.commit()
        return self.repo.get_repair(repair_id) or {}

    def update_repair_status(self, user: User, data: RepairStatusInput) -> dict[str, Any]:
        self._allowed(user, "repair:update")
        repair = self.repo.get_repair(data.repair_id)
        if not repair:
            raise BusinessError("维修单不存在")
        self.repo.update_repair_status(data.repair_id, data.status)
        self._log_success(user, "repair:update", "repair", str(data.repair_id), customer_id=repair["customer_id"], request_summary=data.status.value)
        self.conn.commit()
        return self.repo.get_repair(data.repair_id) or {}

    def list_repairs(self, user: User) -> list[dict[str, Any]]:
        self._allowed(user, "repair:read")
        return self.repo.list_repairs()

    def search_customers(self, user: User, keyword: str = "") -> list[dict[str, Any]]:
        self._allowed(user, "customer:read")
        return self.repo.search_customers(keyword)

    def lookup_imei(self, user: User, imei: str) -> dict[str, Any]:
        self._allowed(user, "device:read")
        device = self.repo.get_device(imei)
        if not device:
            raise BusinessError("未找到该 IMEI")
        repairs = [r for r in self.repo.list_repairs() if imei and imei in (r.get("remark") or "")]
        return {"device": device, "related_repairs": repairs}

    def settlement_preview(self, user: User, customer_id: int) -> dict[str, Any]:
        self._allowed(user, "settlement:create")
        customer = self.repo.get_customer(customer_id)
        if not customer:
            raise BusinessError("客户不存在")
        sales = self.repo.unsettled_sales_for_customer(customer_id)
        repairs = self.repo.unsettled_repairs_for_customer(customer_id) + self.repo.unsettled_repair_orders_for_customer(customer_id)
        total = sum(float(item["sale_price"]) for item in sales) + sum(float(item["quote"]) for item in repairs)
        return {"customer": customer, "sales": sales, "repairs": repairs, "total_amount": total}

    def settle_customer(self, user: User, data: SettlementInput) -> dict[str, Any]:
        self._allowed(user, "settlement:create")
        preview = self.settlement_preview(user, data.customer_id)
        sale_map = {item["imei"]: item for item in preview["sales"]}
        repair_map = {int(item["repair_id"]): item for item in preview["repairs"]}
        selected_sales = [sale_map[imei] for imei in data.sale_imeis if imei in sale_map]
        selected_repairs = [repair_map[rid] for rid in data.repair_ids if rid in repair_map]
        if not selected_sales and not selected_repairs:
            raise BusinessError("没有选择可结账明细")
        total = sum(float(item["sale_price"]) for item in selected_sales) + sum(float(item["quote"]) for item in selected_repairs)
        settlement_id = self.repo.create_settlement(data.customer_id, user.username, total, data.remark)
        for sale in selected_sales:
            self.repo.add_settlement_item(settlement_id, "sale", sale["imei"], float(sale["sale_price"]), sale["settlement_status"], SettlementStatus.settled.value)
            self.repo.mark_sale_settled(sale["imei"])
        for repair in selected_repairs:
            previous_status = repair.get("settlement_status") or repair.get("status") or ""
            self.repo.add_settlement_item(settlement_id, "repair", str(repair["repair_id"]), float(repair["quote"]), previous_status, SettlementStatus.settled.value)
            if repair.get("repair_order_id"):
                self.repo.mark_repair_order_settled(int(repair["repair_order_id"]))
                if repair.get("machine_id"):
                    self.repo.close_machine(int(repair["machine_id"]), MachineStatus.closed.value)
            else:
                self.repo.mark_repair_settled(int(repair["repair_id"]))
        self._log_success(user, "settlement:create", "settlement", str(settlement_id), customer_id=data.customer_id, request_summary=str(total))
        self.conn.commit()
        return {"settlement_id": settlement_id, "total_amount": total}

    def reports(self, user: User) -> dict[str, Any]:
        self._allowed(user, "report:read")
        devices = self.repo.list_devices()
        repairs = self.repo.list_repairs()
        inventory = [d for d in devices if d["status"] == DeviceStatus.in_stock.value]
        unsettled_sales = [d for d in devices if d["status"] == DeviceStatus.sold.value and d["settlement_status"] == SettlementStatus.unsettled.value]
        repair_debt = [r for r in repairs if r["settlement_status"] == SettlementStatus.unsettled.value]
        status_counts: dict[str, int] = {}
        for d in devices:
            status_counts[d["status"]] = status_counts.get(d["status"], 0) + 1
        return {
            "inventory_cost": sum(float(d["recycle_price"]) for d in inventory),
            "unsettled_sales_amount": sum(float(d["sale_price"]) for d in unsettled_sales),
            "repair_debt_amount": sum(float(r["quote"]) for r in repair_debt),
            "inventory_count": len(inventory),
            "status_counts": status_counts,
            "details": {
                "inventory": inventory,
                "unsettled_sales": unsettled_sales,
                "repair_debt": repair_debt,
            },
        }

    def audit_logs(self, user: User) -> list[dict[str, Any]]:
        self._allowed(user, "audit:read")
        return self.repo.logs()
