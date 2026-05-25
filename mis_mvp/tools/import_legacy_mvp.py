from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.db import connect, migrate
from backend.models import BusinessLine, MachineInput, Role, User
from backend.service import MisService


def main() -> int:
    conn = connect(settings.database_path)
    migrate(conn)
    service = MisService(conn)
    admin = User(username="admin", role=Role.admin)

    imported = 0
    for row in conn.execute("SELECT * FROM devices ORDER BY rowid").fetchall():
        imei = row["imei"]
        if imei and service.repo.get_machine_by_imei(imei):
            continue
        machine = service.create_machine(
            admin,
            MachineInput(
                imei=imei or "",
                serial=row["serial"] or "",
                model=row["model"],
                memory=row["memory"] or "",
                color=row["color"] or "",
                condition=row["condition"] or "",
                source_type=BusinessLine.recycle,
                remark=row["remark"] or "从旧 MVP devices 导入",
            ),
        )
        service.repo.add_machine_event(
            int(machine["machine_id"]),
            "legacy",
            "旧回收设备导入",
            f"旧状态：{row['status']}，成本：{row['recycle_price']}",
            "import",
            "devices",
            None,
        )
        imported += 1

    for row in conn.execute("SELECT * FROM repairs ORDER BY repair_id").fetchall():
        model = row["model"]
        machine = service.create_machine(
            admin,
            MachineInput(
                model=model,
                source_type=BusinessLine.repair,
                customer_id=row["customer_id"],
                remark=f"从旧 MVP repairs 导入：{row['remark'] or ''}",
            ),
        )
        service.repo.add_machine_event(
            int(machine["machine_id"]),
            "legacy",
            "旧维修单导入",
            f"旧维修单：{row['repair_id']}，状态：{row['status']}，报价：{row['quote']}",
            "import",
            "repairs",
            int(row["repair_id"]),
        )
        imported += 1

    conn.commit()
    conn.close()
    print(f"Imported {imported} legacy rows into machine timeline tables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
