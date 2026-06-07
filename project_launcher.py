from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


ROOT_DIR = Path(__file__).resolve().parent
CONTROL_SCRIPT = ROOT_DIR / "project_ctl.py"
SETTINGS_PATH = ROOT_DIR / ".launcher_settings.json"
DEFAULT_DB = ROOT_DIR / "mis_mvp" / "data" / "mis_mvp.sqlite3"


class Launcher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("沐辰 MIS 项目启动入口")
        self.geometry("620x360")
        self.minsize(560, 330)
        self.resizable(True, False)

        settings = self.load_settings()
        self.port_var = tk.StringVar(value=str(settings.get("port", 8088)))
        self.db_var = tk.StringVar(value=self.normalized_database_path(settings.get("database_path")))
        self.open_browser_var = tk.BooleanVar(value=settings.get("open_browser", True))
        self.status_var = tk.StringVar(value="请选择数据库后启动、重启或停止服务。")

        self.build_ui()

    def load_settings(self) -> dict:
        if not SETTINGS_PATH.exists():
            return {}
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_settings(self) -> None:
        payload = {
            "port": int(self.port_var.get() or 8088),
            "database_path": self.db_var.get().strip(),
            "open_browser": bool(self.open_browser_var.get()),
        }
        SETTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def normalized_database_path(self, configured: str | None) -> str:
        if not configured:
            return str(DEFAULT_DB)
        path_text = str(Path(configured)).lower()
        if ("\\temp\\mis-mvp-runtime\\" in path_text) or ("\\temp\\muchenmis\\" in path_text):
            return str(DEFAULT_DB)
        return configured

    def build_ui(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(outer, text="沐辰科技 MIS 管理系统", font=("Microsoft YaHei UI", 16, "bold"))
        title.pack(anchor="w")
        subtitle = ttk.Label(outer, text="绑定运行数据库，控制 8088 服务启动、重启和停止。")
        subtitle.pack(anchor="w", pady=(4, 18))

        form = ttk.Frame(outer)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="服务端口").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=8)
        ttk.Entry(form, textvariable=self.port_var, width=12).grid(row=0, column=1, sticky="w", pady=8)

        ttk.Label(form, text="数据库文件").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=8)
        ttk.Entry(form, textvariable=self.db_var).grid(row=1, column=1, sticky="ew", pady=8)
        ttk.Button(form, text="选择...", command=self.pick_database).grid(row=1, column=2, padx=(10, 0), pady=8)

        ttk.Checkbutton(form, text="启动后打开浏览器主页", variable=self.open_browser_var).grid(
            row=2, column=1, sticky="w", pady=(4, 12)
        )

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(8, 16))
        ttk.Button(buttons, text="启动服务", command=lambda: self.run_action("start")).pack(side="left", expand=True, fill="x", padx=(0, 8))
        ttk.Button(buttons, text="重启服务", command=lambda: self.run_action("restart")).pack(side="left", expand=True, fill="x", padx=8)
        ttk.Button(buttons, text="停止服务", command=lambda: self.run_action("stop")).pack(side="left", expand=True, fill="x", padx=(8, 0))

        status_box = ttk.LabelFrame(outer, text="状态")
        status_box.pack(fill="x")
        ttk.Label(status_box, textvariable=self.status_var, wraplength=540, padding=10).pack(fill="x")

        tip = ttk.Label(
            outer,
            text="提示：数据库路径会被保存，下次打开会自动带出。默认主页：http://127.0.0.1:端口/",
            foreground="#555",
        )
        tip.pack(anchor="w", pady=(14, 0))

    def pick_database(self) -> None:
        initial = Path(self.db_var.get()).parent if self.db_var.get().strip() else ROOT_DIR
        selected = filedialog.asksaveasfilename(
            title="选择或创建 SQLite 数据库",
            initialdir=str(initial if initial.exists() else ROOT_DIR),
            defaultextension=".sqlite3",
            filetypes=[("SQLite 数据库", "*.sqlite3 *.db"), ("所有文件", "*.*")],
        )
        if selected:
            self.db_var.set(selected)

    def validated_port(self) -> int:
        try:
            port = int(self.port_var.get())
        except ValueError as exc:
            raise ValueError("端口必须是数字。") from exc
        if port < 1 or port > 65535:
            raise ValueError("端口必须在 1 到 65535 之间。")
        return port

    def run_action(self, action: str) -> None:
        try:
            port = self.validated_port()
            db_path = self.db_var.get().strip()
            if not db_path:
                raise ValueError("请先选择数据库文件。")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self.save_settings()

            cmd = [sys.executable, str(CONTROL_SCRIPT), action, str(port), "--database-path", db_path]
            if not self.open_browser_var.get() or action == "stop":
                cmd.append("--no-browser")
            result = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True, text=True, errors="ignore", check=False)
            output = (result.stdout or result.stderr or "").strip()
            if result.returncode != 0:
                self.status_var.set(output or "操作失败。")
                messagebox.showerror("操作失败", output or "操作失败，请查看日志。")
                return
            self.status_var.set(output or "操作完成。")
        except Exception as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("操作失败", str(exc))


if __name__ == "__main__":
    app = Launcher()
    app.mainloop()
