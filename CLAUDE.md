# CLAUDE.md

Claude Code 项目指南。行为规范、仓库结构、系统概览、配置流程见 @AGENTS.md。

## Tech Stack

- **Backend**: Python 3.14+, FastAPI, SQLite, Pydantic v2
- **Frontend**: Vue 3.5, Vite 8, Pinia, Chart.js, TypeScript
- **LLM**: OpenAI-compatible API (default: xiaomimimo.com)
- **Queue**: JSON file system (`queue/` directory) — no external message broker

## Essential Commands

```bash
# Setup (interactive, recommended)
bash scripts/setup.sh

# Install project as Python package (required for imports)
pip install -e .

# Run dashboard
python3 dashboard/backend/main.py          # Backend (port 8710)
cd dashboard/frontend && npm run dev       # Frontend (port 5173)

# Run agents manually
python3 skills/scout.py                    # Topic discovery
python3 skills/scout.py morning            # Morning session mode
python3 skills/writer.py                   # 7-stage article pipeline
python3 skills/publisher.py <article-id>   # Push to platform draft boxes

# Tests
pytest                                     # Run all tests
pytest tests/test_scout.py                 # Run single test file
pytest -m integration                      # Run integration tests only
pytest --cov=skills --cov-report=term      # Coverage report

# Docker
docker compose up -d                       # Start services
docker compose logs -f dashboard           # View logs
```

## Core Files

- `config/settings.py` — All runtime config (paths, LLM settings, schedules, platform config). Never read env vars directly; import from here.
- `skills/llm.py` — Shared LLM utility with fallback chain and retry logic
- `skills/action.py` — JSON action file protocol (atomic `.tmp` + rename pattern)
- `skills/common.py` — Shared utilities (AgentBase, metrics, status writing, load_prompt) across all agents
- `config/prompts/*.txt` — Agent 提示词模板（7 个，启动时自动导入数据库）
- `config/prompts/*.md` — 写作提示词模板（8 类型 × 2 平台 + persona_bible），详见 [docs/content_type_system.md](docs/content_type_system.md)
- `config/prompts/persona_bible.md` — 统一人设圣经，所有模板引用此文件
- `config/writing_styles.json` — 风格配置（8 类型 + 3 默认）
- `config/quality_gates.json` — 质量门禁阈值（proofread: 60, critique: 70, title: 75, max_rewrite: 3）
- `config/proofread_patterns.json` — AI-slop detection patterns (23 regex)
- `config/models.json` — 模型价格配置（用于 Token 成本计算）

## Dashboard Backend Modules

- `dashboard/backend/main.py` — FastAPI entry point (middleware + router mounting, v0.7.0)
- `dashboard/backend/routes/` — Route modules:
  - `pipeline.py` — Pipeline status, trigger, timeline
  - `approval.py` — Approval queue, approve/reject actions, version management
  - `topics.py` — Topic candidates, confirm
  - `data.py` — Cost tracking, analytics
  - `kb.py` — Knowledge base search, sections, reindex
  - `config.py` — System config (schedule, styles, gates, sources, budget, flywheel)
  - `health.py` — Health check, token logging
  - `traces.py` — Pipeline execution traces (`/api/pipeline/traces`)
  - `prompts.py` — Prompt version management (`/api/prompts`)
- `dashboard/backend/database/` — SQLite operations (split into 7 domain modules):
  - `core.py` — Connection management, cache, schema init (`get_db`, `init_db`)
  - `sessions.py` — Pipeline session CRUD
  - `versions.py` — Platform versions, approval records, quality flywheel
  - `tokens.py` — Token usage tracking, budget control
  - `config_ops.py` — Config key-value store
  - `traces.py` — Execution traces with batch query optimization
  - `prompts.py` — Prompt version management (CRUD + import)
- `dashboard/backend/auth.py` — API Key auth middleware (timing-safe `hmac.compare_digest`)
- `dashboard/backend/background.py` — Background tasks (action scanning, budget monitoring)
- `dashboard/backend/ws.py` — WebSocket real-time push (`/ws/pipeline`, 3s polling)
- `dashboard/backend/config_service.py` — Schedule, writing style, quality gates, source config
- `dashboard/backend/search.py` — FTS5 trigram full-text search for knowledge base
- `dashboard/backend/feishu.py` — Feishu webhook notifications
- `dashboard/backend/helpers.py` — Shared helper functions (read_json, write_action)
- `dashboard/backend/models.py` — Pydantic request/response models

## Configuration

All config flows through `config/settings.py`. It auto-loads `.env` from project root (env vars take precedence).

Required environment variables:
- `LLM_BASE_URL` — LLM API endpoint (OpenAI-compatible)
- `XIAOMI_API_KEY` — LLM API key

Optional:
- `LLM_MODEL` — Model name (default: `mimo-v2.5`)
- `FEISHU_WEBHOOK_URL` — Alert notifications
- `MONTHLY_BUDGET_USD` — Cost cap (default: 15)
- `API_KEY` — API authentication key (leave empty to disable auth)
- `CORS_ORIGINS` — Allowed CORS origins (default: localhost:5173, localhost:8710)

## Testing

Tests use pytest with markers:
- `@pytest.mark.integration` — Integration tests
- `@pytest.mark.slow` — Long-running tests

Test files in `tests/` follow `test_*.py` naming. Conftest provides shared fixtures.
