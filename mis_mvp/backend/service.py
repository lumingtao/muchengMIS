from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from .auth import hash_password, permissions_for, require_permission
from .models import (
    BusinessLine,
    CustomerInput,
    DeviceStatus,
    LoginInput,
    MachineInput,
    MachineNoteInput,
    MachineStatus,
    MachineUpdateInput,
    OrderStatus,
    PaymentDirection,
    PaymentInput,
    PurchaseInput,
    RecycleOrderInput,
    RecycleQuoteInput,
    RepairInput,
    RepairDeliverInput,
    RepairItemInput,
    RepairOrderInput,
    RepairOrderStatusInput,
    RepairQuoteInput,
    RepairStatusInput,
    Role,
    SalesOrderInput,
    SellDeviceInput,
    SettlementInput,
    SettlementStatus,
    StockInInput,
    User,
)
from .repository import Repository


class BusinessError(ValueError):
    pass


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
        return self.repo.search_machines(keyword)

    def machine_timeline(self, user: User, machine_id: int) -> dict[str, Any]:
        self._allowed(user, "machine:read")
        timeline = self.repo.machine_timeline(machine_id)
        if not timeline["machine"]:
            raise BusinessError("机器档案不存在")
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
        payload = {
            "imei": imei,
            "serial": data.serial,
            "model": data.model,
            "memory": data.memory,
            "color": data.color,
            "condition": data.condition,
            "source_type": data.source_type.value if data.source_type else "",
            "current_status": data.current_status.value,
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
        }
        for key, label in labels.items():
            before = machine.get(key) or ""
            after = payload.get(key) or ""
            if str(before) != str(after):
                changes.append(f"{label}：{before or '空'} → {after or '空'}")
        if not changes:
            return machine
        self.repo.update_machine(machine_id, payload)
        detail = "；".join(changes)
        self.repo.add_machine_event(machine_id, "machine", "编辑订单", detail, user.username, "machine", machine_id)
        self._log_success(user, "machine:update", "machine", str(machine_id), imei=imei, customer_id=machine.get("customer_id"), request_summary=detail)
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

    def _repair_order_response(self, repair_order_id: int) -> dict[str, Any]:
        detail = self.repo.repair_order_detail(repair_order_id)
        if not detail:
            return {}
        detail["available_actions"] = self._repair_available_actions(detail)
        return detail

    def _repair_available_actions(self, order: dict[str, Any]) -> list[str]:
        status = self._repair_order_status(order)
        actions_by_status = {
            OrderStatus.opened: ["start_diagnosis", "cancel"],
            OrderStatus.diagnosing: ["quote", "cancel"],
            OrderStatus.quoted: ["add_item", "cancel"],
            OrderStatus.processing: ["mark_ready", "cancel"],
            OrderStatus.ready: ["deliver", "cancel"],
            OrderStatus.delivered: ["payment"],
        }
        return actions_by_status.get(status, [])

    def create_repair_order(self, user: User, data: RepairOrderInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:create")
        customer_id = self._customer_id(data.customer_id, data.customer)
        machine = self._ensure_machine(user, data.machine_id, data.machine, BusinessLine.repair)
        if not customer_id:
            customer_id = machine.get("customer_id")
        machine_id = int(machine["machine_id"])
        order_id = self.repo.create_repair_order(
            machine_id,
            customer_id,
            OrderStatus.opened.value,
            data.fault_description,
            data.remark,
            user.username,
        )
        self.repo.update_machine_status(machine_id, MachineStatus.diagnosing.value, BusinessLine.repair.value)
        self.repo.add_machine_event(machine_id, "repair", "维修开单", data.fault_description, user.username, "repair", order_id)
        self._log_success(user, "repair_order:create", "repair_order", str(order_id), customer_id=customer_id, request_summary=data.fault_description)
        self.conn.commit()
        return self._repair_order_response(order_id)

    def quote_repair_order(self, user: User, repair_order_id: int, data: RepairQuoteInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        self._ensure_repair_transition(order, OrderStatus.quoted, {OrderStatus.diagnosing})
        self.repo.quote_repair_order(repair_order_id, data.diagnosis, data.quoted_amount, OrderStatus.quoted.value)
        self.repo.update_machine_status(int(order["machine_id"]), MachineStatus.quoted.value)
        self.repo.add_machine_event(int(order["machine_id"]), "repair", "检测报价", f"{data.diagnosis}，报价 {data.quoted_amount}", user.username, "repair", repair_order_id)
        self._log_success(user, "repair_order:quote", "repair_order", str(repair_order_id), customer_id=order["customer_id"], request_summary=str(data.quoted_amount))
        self.conn.commit()
        return self._repair_order_response(repair_order_id)

    def add_repair_item(self, user: User, repair_order_id: int, data: RepairItemInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
        self._ensure_repair_transition(order, OrderStatus.processing, {OrderStatus.quoted})
        item_id = self.repo.add_repair_item(repair_order_id, data.item_name, data.quantity, data.cost_amount, data.charge_amount, data.remark)
        self.repo.quote_repair_order(repair_order_id, order["diagnosis"], float(order["quoted_amount"]), OrderStatus.processing.value)
        self.repo.update_machine_status(int(order["machine_id"]), MachineStatus.repairing.value)
        self.repo.add_machine_event(int(order["machine_id"]), "repair", "维修项目", f"{data.item_name} x{data.quantity}", user.username, "repair_item", item_id)
        self._log_success(user, "repair_order:item", "repair_item", str(item_id), customer_id=order["customer_id"], request_summary=data.item_name)
        self.conn.commit()
        detail = self._repair_order_response(repair_order_id)
        detail["repair_item_id"] = item_id
        return detail

    def update_repair_order_status(self, user: User, repair_order_id: int, data: RepairOrderStatusInput) -> dict[str, Any]:
        self._allowed(user, "repair_order:update")
        order = self.repo.get_repair_order(repair_order_id)
        if not order:
            raise BusinessError("维修单不存在")
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
        self.repo.update_repair_order_status(repair_order_id, data.status.value, data.remark)
        if data.status == OrderStatus.cancelled:
            self.repo.add_machine_event(int(order["machine_id"]), "repair", "维修作废", data.remark, user.username, "repair", repair_order_id)
        else:
            self.repo.update_machine_status(int(order["machine_id"]), self._repair_machine_status(data.status).value)
            self.repo.add_machine_event(int(order["machine_id"]), "repair", f"维修{data.status.value}", data.remark, user.username, "repair", repair_order_id)
        self._log_success(user, "repair_order:status", "repair_order", str(repair_order_id), customer_id=order["customer_id"], request_summary=data.status.value)
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
