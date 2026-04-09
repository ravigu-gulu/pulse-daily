#!/usr/bin/env bash
# PulseDaily 自动运行脚本（由 launchd 调用）
# launchd: com.ravigu.pulsedaily，每天 07:00

DIR="$(cd "$(dirname "$0")" && pwd)"

# launchd 不继承用户 PATH，需显式设置
export PATH="/Users/ravigu/.local/bin:/Users/ravigu/.nvm/versions/node/v24.14.0/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
PYTHON="$DIR/.venv/bin/python3"
LOG="$DIR/run.log"

echo "==============================" >> "$LOG"
echo "$(date '+%Y-%m-%d %H:%M:%S')  PulseDaily 开始" >> "$LOG"

# 检查虚拟环境
if [ ! -x "$PYTHON" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S')  错误：虚拟环境不存在" >> "$LOG"
    exit 1
fi

# 等待网络 + DNS 就绪（最多等 10 分钟，每 10 秒检测一次）
echo "$(date '+%Y-%m-%d %H:%M:%S')  等待网络和 DNS..." >> "$LOG"
for i in $(seq 1 60); do
    if nslookup github.com 8.8.8.8 >/dev/null 2>&1; then
        echo "$(date '+%Y-%m-%d %H:%M:%S')  网络和 DNS 就绪（第 ${i} 次检测）" >> "$LOG"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S')  警告：10分钟后 DNS 仍不可用，继续尝试运行" >> "$LOG"
    fi
    sleep 10
done

# caffeinate 防止运行期间进入睡眠
cd "$DIR" && caffeinate -s "$PYTHON" main.py >> "$LOG" 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S')  PulseDaily 结束" >> "$LOG"
