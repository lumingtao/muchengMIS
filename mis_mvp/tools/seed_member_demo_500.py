from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import connect, migrate
from backend.models import CustomerInput, MachineInput, RepairItemInput, RepairOrderInput, Role, User
from backend.service import MisService


SURNAMES = ["张", "李", "王", "赵", "陈", "刘", "杨", "黄", "周", "吴", "徐", "孙", "马", "朱", "胡", "郭"]
GIVEN_NAMES = ["明", "磊", "芳", "娜", "强", "敏", "杰", "静", "伟", "丽", "超", "洋", "欣", "鑫", "晨", "宇"]
SHOP_WORDS = ["数码", "通讯", "手机", "电子", "维修", "科技", "优品", "严选"]
MODELS = ["iPhone 16 Pro Max", "iPhone 16 Pro", "iPhone 15 Pro", "iPhone 15", "iPhone 14 Pro", "iPhone 14", "iPhone 13", "iPhone 12"]
MEMORY = ["64GB", "128GB", "256GB", "512GB", "1TB"]
COLORS = ["黑色", "白色", "蓝色", "粉色", "银色", "金色", "原色钛金属"]
CONDITIONS = ["外观良好", "轻微磕碰", "屏幕破损", "进水", "不开机", "待检测"]
VIP_LEVELS = ["普通", "银卡", "金卡", "铂金", "黑金"]
CATEGORIES = ["个人客户", "同行客户", "企业客户", "VIP客户"]
SOURCES = ["到店", "电话", "微信", "转介绍", "平台", "老客户"]
TAGS = ["高价值", "需回访", "屏幕维修", "电池客户", "同行", "老客户", "寄修", "挂账"]
FAULTS = ["屏幕不亮", "电池健康低", "无法充电", "进水不开机", "后盖破裂", "摄像头异常", "听筒无声"]
INTERACTIONS = ["确认维修报价", "提醒客户取机", "客户咨询保修", "回访使用情况", "记录客户偏好", "约定下次到店"]


def build_customer(index: int, rng: random.Random) -> CustomerInput:
    category = rng.choices(CATEGORIES, weights=[58, 18, 8, 16], k=1)[0]
    surname = rng.choice(SURNAMES)
    given = rng.choice(GIVEN_NAMES) + rng.choice(GIVEN_NAMES)
    name = f"{surname}{given}{index:03d}"
    shop_name = ""
    if category in {"同行客户", "企业客户"}:
        shop_name = f"{rng.choice(SHOP_WORDS)}{rng.choice(SHOP_WORDS)}-{index:03d}"
        name = f"{shop_name}联系人"
    vip_level = rng.choices(VIP_LEVELS, weights=[45, 20, 18, 12, 5], k=1)[0]
    picked_tags = "、".join(rng.sample(TAGS, k=rng.randint(1, 3)))
    return CustomerInput(
        name=name,
        phone=f"13{rng.randint(0, 9)}{index:08d}"[:11],
        wechat=f"wx_member_{index:04d}",
        category=category,
        shop_name=shop_name,
        address=f"深圳市华强北测试街道 {index % 30 + 1} 号",
        tags=picked_tags,
        vip_level=vip_level,
        discount_policy="维修工时 9 折" if vip_level in {"金卡", "铂金", "黑金"} else "",
        status=rng.choices(["正常", "待跟进", "停用"], weights=[86, 11, 3], k=1)[0],
        source=rng.choice(SOURCES),
        birthday=f"19{rng.randint(78, 99):02d}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        remark=f"测试会员 {index:03d}，用于会员管理列表、详情和筛选验收。",
    )


def build_machine(index: int, customer_id: int, rng: random.Random) -> MachineInput:
    return MachineInput(
        imei=f"86{index:013d}",
        serial=f"MBR{index:08d}",
        model=rng.choice(MODELS),
        memory=rng.choice(MEMORY),
        color=rng.choice(COLORS),
        condition=rng.choice(CONDITIONS),
        customer_id=customer_id,
        remark="会员演示机器",
    )


def add_interactions(conn: sqlite3.Connection, customer_id: int, index: int, rng: random.Random) -> None:
    count = rng.randint(1, 4)
    for offset in range(count):
        conn.execute(
            """
            INSERT INTO customer_interactions
            (customer_id, interaction_type, content, next_follow_at, completed, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                rng.choice(["回访", "电话", "微信", "到店", "备注"]),
                f"{rng.choice(INTERACTIONS)}，会员样本 {index:03d}-{offset + 1}",
                "" if rng.random() < 0.55 else f"2026-07-{rng.randint(1, 28):02d}",
                1 if rng.random() < 0.45 else 0,
                rng.choice(["admin", "frontdesk", "staff"]),
            ),
        )


def seed_database(path: Path, count: int) -> dict[str, int]:
    if path.exists():
        path.unlink()
    rng = random.Random(20260614)
    conn = connect(path)
    migrate(conn)
    service = MisService(conn)
    admin = User(username="admin", role=Role.admin)

    repair_orders = 0
    machines = 0
    for index in range(1, count + 1):
        customer_id = service.repo.create_customer(build_customer(index, rng))
        if index % 2 == 0:
            machine = service.create_machine(admin, build_machine(index, customer_id, rng))
            machines += 1
            if index % 3 == 0:
                service.create_repair_order(
                    admin,
                    RepairOrderInput(
                        machine_id=int(machine["machine_id"]),
                        customer_id=customer_id,
                        fault_description=rng.choice(FAULTS),
                        repair_items=[
                            RepairItemInput(
                                item_name=rng.choice(["屏幕维修", "电池更换", "主板检测", "尾插维修"]),
                                quantity=1,
                                cost_amount=float(rng.randint(60, 380)),
                                charge_amount=float(rng.randint(120, 680)),
                                remark="会员演示维修项目",
                            )
                        ],
                    ),
                )
                repair_orders += 1
        add_interactions(conn, customer_id, index, rng)

    conn.commit()
    counts = {
        "customers": int(conn.execute("SELECT COUNT(*) AS c FROM customers").fetchone()["c"]),
        "machines": int(conn.execute("SELECT COUNT(*) AS c FROM machines").fetchone()["c"]),
        "repair_orders": int(conn.execute("SELECT COUNT(*) AS c FROM repair_orders").fetchone()["c"]),
        "customer_interactions": int(conn.execute("SELECT COUNT(*) AS c FROM customer_interactions").fetchone()["c"]),
    }
    conn.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a temporary member CRM demo SQLite database.")
    parser.add_argument("--path", type=Path, default=ROOT / "data" / "member_demo_500.sqlite3")
    parser.add_argument("--count", type=int, default=500)
    args = parser.parse_args()
    counts = seed_database(args.path, args.count)
    print(f"created={args.path}")
    for key, value in counts.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
