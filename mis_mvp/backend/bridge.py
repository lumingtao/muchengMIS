from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import urlopen


class BridgeError(RuntimeError):
    pass


class MisBridgeClient:
    """Read-only bridge client placeholder for the real MIS adapter."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _get_json(self, path: str) -> list[dict]:
        try:
            with urlopen(f"{self.base_url}{path}", timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise BridgeError(f"MIS Bridge 读取失败: {exc}") from exc

    def stock(self) -> list[dict]:
        return self._get_json("/api/mis/stock")

    def unsettled_sales(self) -> list[dict]:
        return self._get_json("/api/mis/unsettled-sales")

    def repair_pending(self) -> list[dict]:
        return self._get_json("/api/mis/repair-pending")

    def inventory_summary(self) -> list[dict]:
        return self._get_json("/api/mis/inventory-summary")
