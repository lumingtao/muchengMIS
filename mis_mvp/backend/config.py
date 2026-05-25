from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    app_name: str = "沐辰 MIS MVP"
    database_path: Path = ROOT_DIR / "data" / "mis_mvp.sqlite3"
    data_provider: str = os.getenv("DATA_PROVIDER", "sqlite")
    bridge_url: str = os.getenv("BRIDGE_URL", "http://127.0.0.1:8090")


settings = Settings()
