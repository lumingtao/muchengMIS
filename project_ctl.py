from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
APP_DIR = ROOT_DIR / "mis_mvp"
RUNTIME_DIR = Path(tempfile.gettempdir()) / "MuchenMIS"
LOG_DIR = RUNTIME_DIR / "logs"
DEFAULT_DB = ROOT_DIR / "mis_mvp" / "data" / "mis_mvp.sqlite3"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8088


def ensure_runtime_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def port_pids(port: int) -> list[int]:
    result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, errors="ignore", check=False)
    pids: set[int] = set()
    for line in result.stdout.splitlines():
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr = parts[1]
        if local_addr.endswith(f":{port}"):
            try:
                pids.add(int(parts[-1]))
            except ValueError:
                pass
    return sorted(pids)


def stop_port(port: int) -> None:
    pids = port_pids(port)
    if not pids:
        print(f"No service is listening on port {port}.")
        return
    for pid in pids:
        result = subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False, capture_output=True, text=True)
        if result.returncode != 0:
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"],
                check=False,
                capture_output=True,
                text=True,
            )
        print(f"Stopped process PID={pid} on port {port}.")
    for _ in range(20):
        if not port_pids(port):
            return
        time.sleep(0.2)


def start_app(host: str, port: int, database_path: str, open_browser: bool) -> None:
    ensure_runtime_dirs()
    db_path = Path(database_path).expanduser()
    if not db_path.is_absolute():
        db_path = ROOT_DIR / db_path
    database_path = str(db_path.resolve())
    existing = port_pids(port)
    browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{browser_host}:{port}/"
    if existing:
        print(f"Port {port} is already running. PID: {', '.join(map(str, existing))}")
    else:
        env = os.environ.copy()
        env["MIS_DATABASE_PATH"] = database_path
        out_log = LOG_DIR / f"mis_mvp_{port}.log"
        err_log = LOG_DIR / f"mis_mvp_{port}.err.log"
        with out_log.open("ab") as stdout, err_log.open("ab") as stderr:
            subprocess.Popen(
                [sys.executable, "-B", "-m", "uvicorn", "backend.app:app", "--host", host, "--port", str(port)],
                cwd=APP_DIR,
                env=env,
                stdout=stdout,
                stderr=stderr,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        for _ in range(20):
            if port_pids(port):
                break
            time.sleep(0.3)
        if not port_pids(port):
            print("Service failed to start. Check logs:")
            print(f"  {out_log}")
            print(f"  {err_log}")
            raise SystemExit(1)
        print(f"Service started: {url}")
        if host in {"0.0.0.0", "::"}:
            print(f"LAN access: http://<this-computer-LAN-IP>:{port}/")
        print(f"Database: {database_path}")
        print(f"Log: {out_log}")
    if open_browser:
        webbrowser.open(url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start, restart, or stop the Muchen MIS service.")
    parser.add_argument("action", nargs="?", choices=["start", "restart", "stop"], default="start")
    parser.add_argument("port", nargs="?", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--database-path", default=str(DEFAULT_DB))
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.action == "stop":
        stop_port(args.port)
    elif args.action == "restart":
        stop_port(args.port)
        time.sleep(1)
        start_app(args.host, args.port, args.database_path, not args.no_browser)
    else:
        start_app(args.host, args.port, args.database_path, not args.no_browser)


if __name__ == "__main__":
    main()
