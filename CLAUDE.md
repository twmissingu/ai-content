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
- `config/prompts/*.txt` — Agent prompt templates, loaded via `load_prompt()`
- `config/proofread_patterns.json` — AI-slop detection patterns

## Dashboard Backend Modules

- `dashboard/backend/main.py` — FastAPI entry point (middleware + router mounting)
- `dashboard/backend/routes/` — Route modules (pipeline, approval, topics, data, kb, config, health)
- `dashboard/backend/auth.py` — API Key authentication middleware (`X-API-Key` header)
- `dashboard/backend/background.py` — Background tasks (action scanning, budget monitoring)
- `dashboard/backend/database.py` — SQLite operations (pipeline sessions, approvals, token usage, config)
- `dashboard/backend/search.py` — FTS5 trigram full-text search for knowledge base
- `dashboard/backend/config_service.py` — Schedule, writing style, quality gates, source config
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

## Testing

Tests use pytest with markers:
- `@pytest.mark.integration` — Integration tests
- `@pytest.mark.slow` — Long-running tests

Test files in `tests/` follow `test_*.py` naming. Conftest provides shared fixtures.
