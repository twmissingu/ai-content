#!/usr/bin/env bash
# System watchdog — runs every minute via crontab.
# Checks Hermes gateway + FastAPI + disk space.

set -euo pipefail

LOG="$HOME/hermes-watchdog.log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Watchdog check" >> "$LOG"

# 1. Hermes gateway
if ! pgrep -f "hermes gateway" > /dev/null 2>&1; then
    echo "  WARN: Hermes gateway not running. Restarting..." >> "$LOG"
    nohup hermes gateway --daemon > /dev/null 2>&1 &
    echo "  Hermes gateway restarted" >> "$LOG"
fi

# 2. FastAPI (Dashboard backend)
if ! pgrep -f "uvicorn.*dashboard" > /dev/null 2>&1; then
    echo "  WARN: FastAPI not running." >> "$LOG"
fi

# 3. Disk space check (alert if < 1GB free)
FREE_KB=$(df / | tail -1 | awk '{print $4}')
if [ "$FREE_KB" -lt 1048576 ]; then
    echo "  WARN: Low disk space: $(( FREE_KB / 1024 )) MB free" >> "$LOG"
fi

# 4. Queue backlog (alert if > 100 pending actions)
BACKLOG=$(ls ~/Documents/dev/ai-content/queue/actions/*.json 2>/dev/null | wc -l)
if [ "$BACKLOG" -gt 100 ]; then
    echo "  WARN: Action queue backlog: $BACKLOG files" >> "$LOG"
fi
