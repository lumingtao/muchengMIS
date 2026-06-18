#!/bin/zsh
set -u

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$ROOT_DIR/mis_mvp"
HOST="127.0.0.1"
PORT="${MIS_PORT:-8090}"
OPEN_BROWSER="${MIS_OPEN_BROWSER:-1}"
REAL_DB="$APP_DIR/data/mis_mvp.sqlite3"
TEST_DB="$APP_DIR/data/member_demo_500.sqlite3"
LOG_DIR="$ROOT_DIR/outputs"
PID_FILE="$LOG_DIR/mis_mvp_${PORT}.pid"
LOG_FILE="$LOG_DIR/mis_mvp_${PORT}.log"

mkdir -p "$LOG_DIR"

resolve_python() {
  local candidate
  local candidates=("$ROOT_DIR/.venv/bin/python")

  if command -v python3 >/dev/null 2>&1; then
    candidates+=("$(command -v python3)")
  fi
  if command -v python >/dev/null 2>&1; then
    candidates+=("$(command -v python)")
  fi

  for candidate in "${candidates[@]}"; do
    if [[ -x "$candidate" ]] && "$candidate" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

PYTHON="$(resolve_python)" || {
  echo "未找到可用的 Python 解释器。"
  echo "请创建 .venv，或确保 python3 已安装 fastapi 和 uvicorn。"
  exit 1
}

find_pids() {
  lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true
}

is_running() {
  [[ -n "$(find_pids)" ]]
}

stop_app() {
  local pids
  pids="$(find_pids)"
  if [[ -z "$pids" ]]; then
    echo "端口 $PORT 当前没有运行中的服务。"
    rm -f "$PID_FILE"
    return 0
  fi

  echo "停止端口 $PORT 上的服务：$pids"
  echo "$pids" | while read -r pid; do
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done

  for _ in {1..20}; do
    if ! is_running; then
      rm -f "$PID_FILE"
      echo "服务已停止。"
      return 0
    fi
    sleep 0.2
  done

  echo "普通停止超时，强制停止。"
  pids="$(find_pids)"
  echo "$pids" | while read -r pid; do
    [[ -n "$pid" ]] && kill -9 "$pid" 2>/dev/null || true
  done
  rm -f "$PID_FILE"
}

ensure_test_db() {
  if [[ -f "$TEST_DB" ]]; then
    return 0
  fi
  echo "未找到测试数据库，正在生成 500 条会员测试数据..."
  (cd "$APP_DIR" && "$PYTHON" tools/seed_member_demo_500.py --path "$TEST_DB" --count 500)
}

start_app() {
  local db_path="$1"
  local label="$2"

  if is_running; then
    echo "端口 $PORT 已有服务运行：$(find_pids)"
    echo "访问地址：http://$HOST:$PORT/"
    return 0
  fi

  mkdir -p "$(dirname "$db_path")"
  echo "启动沐辰 MIS ($label)"
  echo "数据库：$db_path"
  echo "日志：$LOG_FILE"

  (
    cd "$APP_DIR" || exit 1
    MIS_DATABASE_PATH="$db_path" nohup "$PYTHON" -B -m uvicorn backend.app:app --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
  )

  for _ in {1..30}; do
    if is_running; then
      echo "服务已启动：http://$HOST:$PORT/"
      if [[ "$OPEN_BROWSER" != "0" ]] && command -v open >/dev/null 2>&1; then
        open "http://$HOST:$PORT/" >/dev/null 2>&1 || true
      fi
      return 0
    fi
    sleep 0.3
  done

  echo "服务启动失败，请查看日志：$LOG_FILE"
  tail -40 "$LOG_FILE" 2>/dev/null || true
  return 1
}

restart_app() {
  local db_path="$1"
  local label="$2"
  stop_app
  sleep 0.5
  start_app "$db_path" "$label"
}

show_status() {
  echo
  echo "项目目录：$ROOT_DIR"
  echo "端口：$PORT"
  echo "真实数据库：$REAL_DB"
  echo "测试数据库：$TEST_DB"
  if is_running; then
    echo "当前状态：运行中，PID: $(find_pids)"
    echo "访问地址：http://$HOST:$PORT/"
  else
    echo "当前状态：未运行"
  fi
  echo
}

pause_enter() {
  echo
  read "unused?按回车键继续..."
}

while true; do
  clear
  echo "========================================"
  echo " 沐辰 MIS macOS 项目启动菜单"
  echo "========================================"
  show_status
  echo "1) 启动（默认真实数据库）"
  echo "2) 重启（沿用真实数据库）"
  echo "3) 停止"
  echo "4) 绑定测试数据库启动（500 条虚拟会员数据）"
  echo "5) 绑定真实数据库启动"
  echo "6) 退出脚本"
  echo
  read "choice?请选择操作 [1-6]: "

  case "$choice" in
    1)
      start_app "$REAL_DB" "真实数据库"
      pause_enter
      ;;
    2)
      restart_app "$REAL_DB" "真实数据库"
      pause_enter
      ;;
    3)
      stop_app
      pause_enter
      ;;
    4)
      ensure_test_db && restart_app "$TEST_DB" "测试数据库"
      pause_enter
      ;;
    5)
      restart_app "$REAL_DB" "真实数据库"
      pause_enter
      ;;
    6)
      echo "已退出。"
      exit 0
      ;;
    *)
      echo "无效选项，请输入 1-6。"
      pause_enter
      ;;
  esac
done
