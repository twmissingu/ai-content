#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# 稿定 Setup — 配置引导向导
# 用途：首次部署时引导用户/Agent 完成环境配置
# 用法：bash scripts/setup.sh
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[setup]${NC} $1"; }
ok()    { echo -e "${GREEN}[setup]${NC} $1"; }
warn()  { echo -e "${YELLOW}[setup]${NC} $1"; }
fail()  { echo -e "${RED}[setup]${NC} $1"; exit 1; }

# ── 0. Banner ────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}    稿定 — AI Content Production System Setup      ${BLUE}║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Python 版本检查 ─────────────────────────────────────────────
info "检查 Python 版本..."
PYTHON=$(command -v python3 || command -v python || echo "")
if [ -z "$PYTHON" ]; then
    fail "未找到 Python。请安装 Python 3.14+: https://www.python.org/downloads/"
fi

PY_VER=$("$PYTHON" --version 2>&1 | grep -oP '\d+\.\d+')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 12 ]; }; then
    warn "Python $PY_VER — 推荐 3.14+，最低需 3.12"
else
    ok "Python $PY_VER ($PYTHON)"
fi

# ── 2. Node.js 版本检查 ─────────────────────────────────────────────
info "检查 Node.js 版本..."
NODE=$(command -v node || echo "")
if [ -z "$NODE" ]; then
    warn "未找到 Node.js。如需使用 Dashboard 前端请安装: https://nodejs.org/"
else
    NODE_VER=$("$NODE" --version 2>&1 | sed 's/v//')
    NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
    if [ "$NODE_MAJOR" -lt 18 ]; then
        warn "Node.js v$NODE_VER — 推荐 20+"
    else
        ok "Node.js v$NODE_VER"
    fi
fi

# ── 3. 加载 .env（如果存在）────────────────────────────────────────
load_env() {
    local env_file="$ROOT/.env"
    [ -f "$env_file" ] || return 1
    while IFS='=' read -r key val; do
        key="${key// /}"
        [ -z "$key" ] && continue
        [[ "$key" == \#* ]] && continue
        val="${val%\"}"
        val="${val#\"}"
        [ -n "$key" ] && [ -n "$val" ] && export "$key=$val"
    done < "$env_file"
    return 0
}
load_env || true

# ── 4. Base URL 检查 ──────────────────────────────────────────────
echo ""
info "第一步：LLM API 地址"
echo "  输入你的 LLM API Base URL（兼容 OpenAI 格式）"
echo "  例如: https://api.deepseek.com"
echo "       https://dashscope.aliyuncs.com/compatible-mode/v1"
echo "       https://token-plan-cn.xiaomimimo.com/v1"
echo ""

if [ -n "${LLM_BASE_URL:-}" ]; then
    ok "已检测到 LLM_BASE_URL: ${LLM_BASE_URL}"
    echo "  直接回车保留，或输入新地址覆盖："
else
    echo -n "  Base URL > "
fi
read -r USER_BASE_URL
if [ -n "$USER_BASE_URL" ]; then
    LLM_BASE_URL="$USER_BASE_URL"
    ok "Base URL 已设置"
elif [ -z "${LLM_BASE_URL:-}" ]; then
    warn "Base URL 未设置（Agent 功能将不可用）"
fi

# ── 5. API Key 检查 ───────────────────────────────────────────────
echo ""
info "第二步：LLM API Key"
echo ""

if [ -n "${XIAOMI_API_KEY:-}" ]; then
    PREFIX="${XIAOMI_API_KEY:0:4}"
    SUFFIX="${XIAOMI_API_KEY: -4}"
    ok "已检测到 XIAOMI_API_KEY: ${PREFIX}****${SUFFIX}"
    echo "  直接回车保留，或输入新 Key 覆盖："
else
    echo -n "  API Key > "
fi
read -r -s USER_KEY
echo ""
if [ -n "$USER_KEY" ]; then
    XIAOMI_API_KEY="$USER_KEY"
    ok "API Key 已设置"
elif [ -z "${XIAOMI_API_KEY:-}" ]; then
    warn "API Key 未设置（Agent 功能将不可用）"
fi

# ── 6. 写入 .env ──────────────────────────────────────────────────
ENV_FILE="$ROOT/.env"
ENV_UPDATED=false

write_env() {
    local key="$1"
    local val="$2"
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        # macOS sed requires different syntax
        sed -i '' "s|^${key}=.*|${key}=\"${val}\"|" "$ENV_FILE"
    else
        echo "${key}=\"${val}\"" >> "$ENV_FILE"
    fi
    ENV_UPDATED=true
}

if [ -n "${LLM_BASE_URL:-}" ] || [ -n "${XIAOMI_API_KEY:-}" ]; then
    # 如果 .env 不存在则创建，保留已有内容
    [ -f "$ENV_FILE" ] || touch "$ENV_FILE"

    if [ -n "${LLM_BASE_URL:-}" ]; then
        write_env "LLM_BASE_URL" "$LLM_BASE_URL"
    fi
    if [ -n "${XIAOMI_API_KEY:-}" ]; then
        write_env "XIAOMI_API_KEY" "$XIAOMI_API_KEY"
    fi

    if $ENV_UPDATED; then
        ok ".env 已更新"
    fi
fi

# ── 7. 创建运行时目录 ──────────────────────────────────────────────
info "创建运行时目录..."
bash "$ROOT/scripts/init_directories.sh"
ok "目录已就绪"

# ── 8. 安装 Python 依赖 ───────────────────────────────────────────
info "检查 Python 依赖..."
DEPS_MISSING=false
for mod in httpx uvicorn fastapi pydantic; do
    if ! "$PYTHON" -c "import $mod" 2>/dev/null; then
        DEPS_MISSING=true
        break
    fi
done

if $DEPS_MISSING; then
    echo ""
    warn "部分 Python 依赖缺失，是否安装？[Y/n]"
    read -r INSTALL_DEPS
    if [ -z "$INSTALL_DEPS" ] || [[ "$INSTALL_DEPS" =~ ^[Yy] ]]; then
        "$PYTHON" -m pip install httpx uvicorn fastapi pydantic
        ok "Python 依赖安装完成"
    else
        warn "跳过 Python 依赖安装。运行 Agent 前请手动执行："
        echo "  pip install httpx uvicorn fastapi pydantic"
    fi
else
    ok "Python 依赖已就绪"
fi

# ── 9. 安装前端依赖 ───────────────────────────────────────────────
if [ -n "${NODE:-}" ] && [ -d "$ROOT/dashboard/frontend" ]; then
    if [ ! -d "$ROOT/dashboard/frontend/node_modules" ]; then
        info "安装前端依赖..."
        cd "$ROOT/dashboard/frontend"
        npm install
        cd "$ROOT"
        ok "前端依赖安装完成"
    else
        ok "前端依赖已就绪"
    fi
fi

# ── 10. 配置概要 ──────────────────────────────────────────────────
echo ""
echo -e "${BLUE}══════════════════ 配置概要 ═══════════════════${NC}"
echo "  项目根目录 : $ROOT"
echo "  Python      : $PY_VER ($PYTHON)"
echo "  Node.js     : ${NODE_VER:-未安装}"

if [ -n "${LLM_BASE_URL:-}" ]; then
    echo "  LLM 地址    : $LLM_BASE_URL"
else
    echo -e "  ${YELLOW}LLM 地址    : 未配置${NC}"
fi

if [ -n "${XIAOMI_API_KEY:-}" ]; then
    PREFIX="${XIAOMI_API_KEY:0:4}"
    SUFFIX="${XIAOMI_API_KEY: -4}"
    echo "  API Key     : ${PREFIX}****${SUFFIX}"
else
    echo -e "  ${YELLOW}API Key     : 未配置${NC}"
fi

echo "  队列目录    : $ROOT/queue/"
echo "  Dashboard   : http://localhost:5173"
echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo ""

# ── 11. 启动 Dashboard ───────────────────────────────────────────
if [ -n "${LLM_BASE_URL:-}" ] && [ -n "${XIAOMI_API_KEY:-}" ]; then
    echo "是否启动 Dashboard？[y/N]"
    read -r START_DASH
    if [[ "$START_DASH" =~ ^[Yy] ]]; then
        info "启动 FastAPI 后端 (port 8710)..."
        "$PYTHON" -m uvicorn dashboard.backend.main:app --host 0.0.0.0 --port 8710 --reload &
        BACKEND_PID=$!
        sleep 2

        if [ -n "${NODE:-}" ] && [ -d "$ROOT/dashboard/frontend/node_modules" ]; then
            info "启动 Vue 前端 (port 5173)..."
            cd "$ROOT/dashboard/frontend"
            npm run dev &
            FRONTEND_PID=$!
            cd "$ROOT"
        fi

        echo ""
        ok "Dashboard 已启动："
        echo "  后端: http://localhost:8710"
        echo "  前端: http://localhost:5173"
        echo "  停止: kill $BACKEND_PID ${FRONTEND_PID:-}"
        echo ""
        echo "按 Ctrl+C 停止所有服务"
        wait
    fi
else
    info "Base URL 或 API Key 未配置，跳过 Dashboard 启动。"
    echo "  配置后手动启动: python3 dashboard/backend/main.py"
fi

ok "Setup 完成！"
echo "  下一步: 运行 python3 skills/scout.py 开始选题"
echo "  或访问 http://localhost:5173 打开 Dashboard（需先启动）"
