from __future__ import annotations

import random
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.db import connect, migrate
from backend.models import (
    CustomerInput,
    MachineInput,
    PaymentDirection,
    PaymentInput,
    RecycleOrderInput,
    RecycleQuoteInput,
    RepairDeliverInput,
    RepairItemInput,
    RepairOrderInput,
    RepairQuoteInput,
    Role,
    SalesOrderInput,
    StockInInput,
    User,
)
from backend.service import MisService


MODELS = [
    "iPhone 15 Pro Max",
    "iPhone 15 Pro",
    "iPhone 15",
    "iPhone 14 Pro",
    "iPhone 14",
    "iPhone 13 Pro",
    "iPhone 13",
    "iPhone 12",
]
COLORS = ["黑色", "白色", "蓝色", "原色", "金色", "紫色"]
MEMORY = ["128G", "256G", "512G", "1T"]
CONDITIONS = ["外观优秀", "轻微磕碰", "屏幕划痕", "后盖破损", "主板故障", "无法开机"]
CUSTOMERS = ["张三", "李四", "王五", "赵六", "同行客户A", "数码店B", "维修客户C", "老客户D"]
STAFF = ["小王", "小陈", "小李", "小周"]


def customer(idx: int) -> CustomerInput:
    name = f"{CUSTOMERS[idx % len(CUSTOMERS)]}-{idx:03d}"
    return CustomerInput(
        name=name,
        phone=f"13{idx % 10}{idx:08d}"[:11],
        category="商家客户" if "店" in name or "同行" in name else "个人客户",
        shop_name=name if "店" in name or "同行" in name else "",
        tags="测试数据",
    )


def machine(idx: int, with_imei: bool = True) -> MachineInput:
    imei = f"86{idx:013d}" if with_imei else ""
    return MachineInput(
        imei=imei,
        serial=f"SN{idx:08d}",
        model=MODELS[idx % len(MODELS)],
        memory=MEMORY[idx % len(MEMORY)],
        color=COLORS[idx % len(COLORS)],
        condition=CONDITIONS[idx % len(CONDITIONS)],
    )


def seed(count: int = 200) -> None:
    random.seed(20260522)
    conn = connect(settings.database_path)
    migrate(conn)
    service = MisService(conn)
    admin = User(username="admin", role=Role.admin)
    staff = User(username="staff", role=Role.staff)
    finance = User(username="finance", role=Role.finance)

    start = int(conn.execute("SELECT COALESCE(MAX(machine_id), 0) FROM machines").fetchone()[0]) + 1
    created = 0

    for offset in range(count):
        idx = start + offset
        branch = idx % 4
        with_imei = idx % 17 != 0

        if branch == 0:
            order = service.create_repair_order(
                staff,
                RepairOrderInput(
                    machine=machine(idx, with_imei),
                    customer=customer(idx),
                    fault_description=random.choice(["不开机", "屏幕异常", "电池不耐用", "进水检测", "刷机解锁"]),
                ),
            )
            repair_id = order["repair_order_id"]
            quote = random.randint(120, 980)
            service.quote_repair_order(
                staff,
                repair_id,
                RepairQuoteInput(diagnosis=random.choice(["主板故障", "屏幕损坏", "电池老化", "系统异常"]), quoted_amount=quote),
            )
            if idx % 2 == 0:
                service.add_repair_item(
                    staff,
                    repair_id,
                    RepairItemInput(
                        item_name=random.choice(["更换电池", "屏幕总成", "主板维修", "软件刷机"]),
                        quantity=1,
                        cost_amount=round(quote * 0.35, 2),
                        charge_amount=quote,
                    ),
                )
            if idx % 3 == 0:
                service.deliver_repair_order(staff, repair_id, RepairDeliverInput(delivery_check="交付检测通过"))
            if idx % 5 == 0:
                service.create_payment(
                    finance,
                    PaymentInput(source_type="repair", source_id=repair_id, direction=PaymentDirection.income, amount=quote),
                )

        else:
            recycle = service.create_recycle_order(
                staff,
                RecycleOrderInput(
                    machine=machine(idx, with_imei),
                    customer=customer(idx),
                    inspection_note=random.choice(["外观检查完成", "功能初检完成", "电池效率待确认", "需进一步验机"]),
                ),
            )
            recycle_id = recycle["recycle_order_id"]
            cost = random.randint(900, 6200)
            sale_price = cost + random.randint(180, 1200)
            service.quote_recycle_order(
                staff,
                recycle_id,
                RecycleQuoteInput(inspection_result=random.choice(["功能正常", "轻微维修后可售", "外观瑕疵", "电池需更换"]), quoted_amount=cost),
            )
            if idx % 3 != 1:
                inventory = service.stock_in_recycle_order(
                    admin,
                    recycle_id,
                    StockInInput(pay_amount=cost, sale_price=sale_price),
                )
                if idx % 4 == 2:
                    sale = service.create_sales_order(
                        staff,
                        SalesOrderInput(
                            inventory_item_id=inventory["inventory_item_id"],
                            customer=customer(idx + 5000),
                            sale_price=sale_price,
                            salesperson=random.choice(STAFF),
                        ),
                    )
                    if idx % 8 == 2:
                        service.create_payment(
                            finance,
                            PaymentInput(source_type="sale", source_id=sale["sales_order_id"], direction=PaymentDirection.income, amount=sale_price),
                        )

        created += 1

    conn.commit()
    conn.close()
    print(f"Seeded {created} machine lifecycle records.")


if __name__ == "__main__":
    amount = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    seed(amount)
