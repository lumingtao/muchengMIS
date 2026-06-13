from __future__ import annotations

import re
from datetime import datetime
from typing import Any


REPAIR_ORDER_NO_RE = re.compile(r"^R-\d{8}-\d{3}$")


def repair_order_date_key(created_at: Any) -> str:
    text = str(created_at or "").strip()
    if text:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text[:19] if "%S" in fmt else text[:10], fmt).strftime("%Y%m%d")
            except ValueError:
                pass
        compact = re.sub(r"\D", "", text)
        if len(compact) >= 8:
            return compact[:8]
    return datetime.now().strftime("%Y%m%d")


def repair_order_no(date_key: str, sequence: int) -> str:
    return f"R-{date_key}-{max(1, int(sequence)):03d}"


def is_repair_order_no(value: Any) -> bool:
    return bool(REPAIR_ORDER_NO_RE.match(str(value or "").strip()))
