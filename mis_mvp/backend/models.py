from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class Role(str, Enum):
    admin = "admin"
    staff = "staff"
    finance = "finance"


class DeviceStatus(str, Enum):
    in_stock = "在库"
    sold = "已出"
    pending = "待处理"


class RepairStatus(str, Enum):
    received = "接机"
    repairing = "维修中"
    completed = "完成"
    picked_up = "取机"
    settled = "已结账"


class SettlementStatus(str, Enum):
    unsettled = "未结"
    settled = "已结"


class MachineStatus(str, Enum):
    arrived = "到店"
    diagnosing = "检测中"
    quoted = "已报价"
    repairing = "维修中"
    ready_for_delivery = "待交付"
    delivered = "已交付"
    recycled = "已回收"
    in_recycle_stock = "回收库存"
    priced_for_sale = "待销售"
    sold = "已售出"
    closed = "已结单"


class BusinessLine(str, Enum):
    repair = "维修"
    recycle = "回收"
    sale = "销售"


class OrderStatus(str, Enum):
    opened = "已开单"
    diagnosing = "检测中"
    quoted = "已报价"
    processing = "处理中"
    ready = "待交付"
    delivered = "已交付"
    stocked = "已入库"
    sold = "已售出"
    closed = "已结单"
    cancelled = "已作废"


class PaymentDirection(str, Enum):
    income = "收入"
    expense = "支出"


class CustomerInput(BaseModel):
    name: str = Field(min_length=1)
    phone: str = ""
    wechat: str = ""
    category: str = "个人客户"
    shop_name: str = ""
    address: str = ""
    tags: str = ""
    vip_level: str = ""
    discount_policy: str = ""
    remark: str = ""


class Customer(CustomerInput):
    customer_id: int


class MachineInput(BaseModel):
    imei: str = ""
    serial: str = ""
    model: str = Field(min_length=1)
    memory: str = ""
    color: str = ""
    condition: str = ""
    source_type: BusinessLine | None = None
    customer_id: int | None = None
    customer: CustomerInput | None = None
    remark: str = ""


class MachineUpdateInput(BaseModel):
    imei: str = ""
    serial: str = ""
    model: str = Field(min_length=1)
    memory: str = ""
    color: str = ""
    condition: str = ""
    source_type: BusinessLine | None = None
    current_status: MachineStatus


class MachineNoteInput(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class Machine(BaseModel):
    machine_id: int
    machine_no: str
    imei: str = ""
    serial: str = ""
    model: str
    memory: str = ""
    color: str = ""
    condition: str = ""
    source_type: str = ""
    current_status: str
    customer_id: int | None = None
    remark: str = ""


class RepairOrderInput(BaseModel):
    machine_id: int | None = None
    machine: MachineInput | None = None
    customer_id: int | None = None
    customer: CustomerInput | None = None
    fault_description: str = ""
    remark: str = ""


class RepairQuoteInput(BaseModel):
    diagnosis: str = Field(min_length=1)
    quoted_amount: float = Field(ge=0)


class RepairItemInput(BaseModel):
    item_name: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1)
    cost_amount: float = Field(default=0, ge=0)
    charge_amount: float = Field(default=0, ge=0)
    remark: str = ""


class RepairDeliverInput(BaseModel):
    delivery_check: str = Field(min_length=1)
    remark: str = ""


class RepairOrderStatusInput(BaseModel):
    status: OrderStatus
    remark: str = ""


class RecycleOrderInput(BaseModel):
    machine_id: int | None = None
    machine: MachineInput | None = None
    customer_id: int | None = None
    customer: CustomerInput | None = None
    inspection_note: str = ""
    remark: str = ""


class RecycleQuoteInput(BaseModel):
    inspection_result: str = Field(min_length=1)
    quoted_amount: float = Field(ge=0)


class StockInInput(BaseModel):
    pay_amount: float = Field(ge=0)
    sale_price: float = Field(default=0, ge=0)
    remark: str = ""


class SalesOrderInput(BaseModel):
    inventory_item_id: int
    customer_id: int | None = None
    customer: CustomerInput | None = None
    sale_price: float = Field(ge=0)
    salesperson: str = Field(min_length=1)
    remark: str = ""


class PaymentInput(BaseModel):
    source_type: str = Field(min_length=1)
    source_id: int
    direction: PaymentDirection
    amount: float = Field(gt=0)
    method: str = ""
    payer: str = ""
    payee: str = ""
    remark: str = ""


class PurchaseInput(BaseModel):
    imei: str = Field(min_length=5)
    serial: str = ""
    model: str = Field(min_length=1)
    memory: str = ""
    battery: str = ""
    color: str = ""
    country: str = ""
    version: str = ""
    warranty: str = ""
    condition: str = ""
    seller: str = ""
    recycler: str = ""
    recycle_price: float = Field(ge=0)
    recycle_time: str = ""
    settlement_status: SettlementStatus = SettlementStatus.unsettled
    remark: str = ""
    customer: CustomerInput | None = None
    customer_id: int | None = None


class Device(BaseModel):
    imei: str
    serial: str = ""
    model: str
    memory: str = ""
    battery: str = ""
    color: str = ""
    country: str = ""
    version: str = ""
    warranty: str = ""
    condition: str = ""
    status: DeviceStatus
    seller: str = ""
    recycler: str = ""
    recycle_price: float = 0
    recycle_time: str = ""
    buyer_customer_id: int | None = None
    buyer_name: str = ""
    salesperson: str = ""
    sale_price: float = 0
    sale_time: str = ""
    settlement_status: SettlementStatus = SettlementStatus.unsettled
    remark: str = ""


class SellDeviceInput(BaseModel):
    imei: str
    buyer_customer_id: int | None = None
    buyer: str = Field(min_length=1)
    salesperson: str = Field(min_length=1)
    sale_time: str = ""
    sale_price: float = Field(ge=0)
    settlement_status: SettlementStatus = SettlementStatus.unsettled


class RepairInput(BaseModel):
    customer_id: int | None = None
    customer: CustomerInput | None = None
    customer_name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    solution: str = ""
    quote: float = Field(ge=0)
    payment_method: str = ""
    status: RepairStatus = RepairStatus.received
    settlement_status: SettlementStatus = SettlementStatus.unsettled
    remark: str = ""


class RepairBill(RepairInput):
    repair_id: int
    created_at: str


class RepairStatusInput(BaseModel):
    repair_id: int
    status: RepairStatus


class SettlementInput(BaseModel):
    customer_id: int
    sale_imeis: list[str] = []
    repair_ids: list[int] = []
    remark: str = ""


class LoginInput(BaseModel):
    username: str
    password: str


class User(BaseModel):
    username: str
    role: Role
