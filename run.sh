#!/usr/bin/env bash
# PulseDaily 自动运行脚本（由 cron 调用）
# cron: 0 7 * * * /Users/ravigu/pulse_daily/run.sh

DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$DIR/.venv/bin/python3"
LOG="$DIR/run.log"

echo "==============================" >> "$LOG"
echo "$(date '+%Y-%m-%d %H:%M:%S')  PulseDaily 开始" >> "$LOG"

# 检查虚拟环境
if [ ! -x "$PYTHON" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S')  错误：虚拟环境不存在" >> "$LOG"
    exit 1
fi

# 等待网络就绪（最多 60 秒）
for i in $(seq 1 12); do
    if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
        echo "$(date '+%Y-%m-%d %H:%M:%S')  网络就绪" >> "$LOG"
        break
    fi
    sleep 5
done

cd "$DIR" && "$PYTHON" main.py >> "$LOG" 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S')  PulseDaily 结束" >> "$LOG"
