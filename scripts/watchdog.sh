#!/usr/bin/env bash
# System watchdog — runs every minute via crontab.
# Checks Hermes gateway + FastAPI + disk space + queue backlog.
# Sends alerts to Feishu via webhook.

set -euo pipefail

# Configuration
LOG="${HOME}/hermes-watchdog.log"
FEISHU_WEBHOOK="${FEISHU_WEBHOOK_URL:-}"
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Documents/dev/ai-content}"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG")"

# Timestamp function
timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

# Log function
log() {
    echo "[$(timestamp)] $1" >> "$LOG"
}

# Send Feishu alert
send_alert() {
    local title="$1"
    local content="$2"
    local level="${3:-warning}"
    
    log "ALERT: $title - $content"
    
    if [ -n "$FEISHU_WEBHOOK" ]; then
        # Build Feishu card message
        local color="orange"
        local emoji="⚠️"
        
        case "$level" in
            error)
                color="red"
                emoji="🚨"
                ;;
            warning)
                color="orange"
                emoji="⚠️"
                ;;
            info)
                color="blue"
                emoji="ℹ️"
                ;;
        esac
        
        local timestamp_ms=$(date +%s)000
        local payload=$(cat <<EOF
{
    "msg_type": "interactive",
    "card": {
        "config": {"wide_screen_mode": true},
        "header": {
            "title": {"tag": "plain_text", "content": "${emoji} ${title}"},
            "template": "${color}"
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "${content}"}
            },
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": "稿定 AI 内容系统 | $(timestamp)"}
                ]
            }
        ]
    }
}
EOF
)
        
        curl -s -X POST "$FEISHU_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "$payload" > /dev/null 2>&1 || true
    fi
}

# Check if process is running
check_process() {
    local pattern="$1"
    local name="$2"
    
    if ! pgrep -f "$pattern" > /dev/null 2>&1; then
        return 1
    fi
    return 0
}

# Main watchdog checks
log "Watchdog check started"

# 1. Check Hermes gateway
if ! check_process "hermes gateway" "Hermes Gateway"; then
    log "WARN: Hermes gateway not running"
    
    # Try to restart
    if command -v hermes &> /dev/null; then
        log "Attempting to restart Hermes gateway..."
        nohup hermes gateway --daemon > /dev/null 2>&1 &
        sleep 2
        
        if check_process "hermes gateway" "Hermes Gateway"; then
            send_alert "服务恢复" "✅ Hermes gateway 已自动重启成功" "info"
            log "Hermes gateway restarted successfully"
        else
            send_alert "服务宕机" "❌ Hermes gateway 重启失败，请手动检查" "error"
            log "ERROR: Hermes gateway restart failed"
        fi
    else
        send_alert "服务宕机" "❌ Hermes gateway 未运行且 hermes 命令不可用" "error"
    fi
else
    log "OK: Hermes gateway running"
fi

# 2. Check FastAPI Dashboard
if ! check_process "uvicorn.*dashboard" "FastAPI Dashboard"; then
    log "WARN: FastAPI Dashboard not running"
    
    # Try to restart
    if [ -f "${PROJECT_ROOT}/dashboard/backend/main.py" ]; then
        log "Attempting to restart FastAPI Dashboard..."
        cd "${PROJECT_ROOT}"
        nohup python3 -m uvicorn dashboard.backend.main:app \
            --host 127.0.0.1 --port 8710 \
            > "${PROJECT_ROOT}/data/logs/dashboard.log" 2>&1 &
        sleep 3
        
        if check_process "uvicorn.*dashboard" "FastAPI Dashboard"; then
            send_alert "服务恢复" "✅ FastAPI Dashboard 已自动重启成功" "info"
            log "FastAPI Dashboard restarted successfully"
        else
            send_alert "服务宕机" "❌ FastAPI Dashboard 重启失败，请手动检查" "error"
            log "ERROR: FastAPI Dashboard restart failed"
        fi
    else
        send_alert "服务宕机" "❌ FastAPI Dashboard 未运行且启动脚本不存在" "error"
    fi
else
    log "OK: FastAPI Dashboard running"
fi

# 3. Check disk space (alert if < 1GB free)
FREE_KB=$(df / | tail -1 | awk '{print $4}')
FREE_MB=$((FREE_KB / 1024))

if [ "$FREE_KB" -lt 1048576 ]; then
    log "WARN: Low disk space: ${FREE_MB} MB free"
    send_alert "磁盘空间不足" "剩余空间: ${FREE_MB} MB\n\n请清理不必要的文件。" "warning"
else
    log "OK: Disk space: ${FREE_MB} MB free"
fi

# 4. Check queue backlog
ACTION_COUNT=$(find "${PROJECT_ROOT}/queue/actions" -name "*.json" -type f 2>/dev/null | wc -l || echo "0")
ACTION_COUNT=$(echo "$ACTION_COUNT" | tr -d ' ')

if [ "$ACTION_COUNT" -gt 100 ]; then
    log "WARN: Action queue backlog: ${ACTION_COUNT} files"
    send_alert "队列积压" "待处理 action 文件: ${ACTION_COUNT} 个\n\n可能存在处理瓶颈。" "warning"
elif [ "$ACTION_COUNT" -gt 50 ]; then
    log "INFO: Action queue growing: ${ACTION_COUNT} files"
fi

# 5. Check for failed actions
FAILED_COUNT=$(find "${PROJECT_ROOT}/queue/failed" -name "*.json" -type f 2>/dev/null | wc -l || echo "0")
FAILED_COUNT=$(echo "$FAILED_COUNT" | tr -d ' ')

if [ "$FAILED_COUNT" -gt 10 ]; then
    log "WARN: High failure count: ${FAILED_COUNT} failed actions"
    send_alert "失败任务较多" "失败任务数: ${FAILED_COUNT}\n\n请检查系统日志。" "warning"
fi

# 6. Check pending topics (ensure Scout is running)
PENDING_COUNT=$(find "${PROJECT_ROOT}/queue/pending" -name "topic_*.json" -type f 2>/dev/null | wc -l || echo "0")
PENDING_COUNT=$(echo "$PENDING_COUNT" | tr -d ' ')

# Get current hour (UTC)
CURRENT_HOUR=$(date -u +%H)

# If it's past 10:00 UTC and no topics, something might be wrong
if [ "$CURRENT_HOUR" -ge 10 ] && [ "$PENDING_COUNT" -eq 0 ]; then
    # Check if today's scout has run
    TODAY=$(date -u +%Y-%m-%d)
    SCOUT_STATUS="${PROJECT_ROOT}/queue/status/scout.json"
    
    if [ -f "$SCOUT_STATUS" ]; then
        LAST_MODIFIED=$(stat -f "%Sm" -t "%Y-%m-%d" "$SCOUT_STATUS" 2>/dev/null || stat -c "%y" "$SCOUT_STATUS" 2>/dev/null | cut -d' ' -f1)
        if [ "$LAST_MODIFIED" != "$TODAY" ]; then
            log "WARN: Scout may not have run today"
            send_alert "选题异常" "今日 Scout 可能未正常运行，当前无待选题目。" "warning"
        fi
    fi
fi

# 7. Check review queue (articles waiting for approval)
REVIEW_COUNT=$(find "${PROJECT_ROOT}/queue/review" -name "*.meta.json" -type f 2>/dev/null | wc -l || echo "0")
REVIEW_COUNT=$(echo "$REVIEW_COUNT" | tr -d ' ')

if [ "$REVIEW_COUNT" -gt 5 ]; then
    log "INFO: ${REVIEW_COUNT} articles pending review"
    # This is informational, not necessarily an error
fi

log "Watchdog check completed"

# Summary (only log if there are issues)
if [ "$ACTION_COUNT" -gt 50 ] || [ "$FAILED_COUNT" -gt 5 ] || [ "$FREE_KB" -lt 2097152 ]; then
    log "Summary: actions=${ACTION_COUNT}, failed=${FAILED_COUNT}, disk=${FREE_MB}MB, review=${REVIEW_COUNT}"
fi
