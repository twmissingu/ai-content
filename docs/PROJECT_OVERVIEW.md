# 稿定 (Gaoding) — AI Content Production System

## Project Overview

**Gaoding** is an AI-powered content production system that automates the entire content creation pipeline from topic discovery to multi-platform distribution. The system is designed for daily operation with minimal manual effort (~10 minutes/day).

### Core Value Proposition

Content creators spend 80% of their time on repetitive work: searching for trending topics, drafting articles, formatting for different platforms, and distributing to each platform's backend. Gaoding automates this entire pipeline.

**Key Workflow**: Find hot topics → Write 3 platform versions → Push to draft boxes. You just pick the topic and approve. Everything else happens automatically.

---

## Technical Architecture

### Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Backend** | Python, FastAPI, SQLite, Pydantic v2 | Python 3.14+ |
| **Frontend** | Vue 3, Vite, Pinia, Chart.js, TypeScript | Vue 3.5+ |
| **LLM** | OpenAI-compatible API | Default: xiaomimimo.com |
| **Queue** | JSON file system (`queue/` directory) | No external message broker |
| **Database** | SQLite with WAL mode | 8 domain modules |
| **Real-time** | WebSocket | 3s polling + hash detection |

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Dashboard (Vue 3)                     │
│              http://localhost:5173 (dev mode)                │
└─────────────────────────┬───────────────────────────────────┘
                          │ REST API + WebSocket
┌─────────────────────────▼───────────────────────────────────┐
│                  FastAPI Backend (Port 8710)                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Routes    │  │  Database   │  │  WebSocket  │         │
│  │  (12 modules)│  │ (8 modules) │  │   /ws/pipeline│       │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Agent System (Python)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │    Scout    │  │   Writer    │  │  Publisher   │         │
│  │  (选题发现)  │  │  (7阶段管线) │  │  (平台分发)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Feedback   │  │  Knowledge  │  │     TTS     │         │
│  │  (数据反馈)  │  │  (知识沉淀)  │  │  (语音合成)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    External Services                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ LLM API     │  │  AiToEarn   │  │  Firecrawl  │         │
│  │ (OpenAI)    │  │  (MCP分发)   │  │  (Web搜索)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Agent System (`skills/`)

The agent system implements the content production pipeline with specialized agents:

#### Scout Agent (`scout.py`)
- **Purpose**: Topic discovery and scoring
- **Sources**: Weibo, Zhihu, Bilibili, Douyin, Toutiao, 36Kr, GitHub, RSS, Web search
- **Scoring**: Two-layer LLM model (attention score + increment score)
- **Cold-start**: Fallback scoring when historical data unavailable

#### Writer Agent (`writer.py`)
- **Purpose**: 7-stage article production pipeline
- **Stages**:
  1. Fetch source material
  2. LLM draft generation
  3. AI-slop proofreading (23 regex patterns)
  4. Critique & rewrite (up to 3 rounds)
  5. Format adaptation
  6. Title optimization
  7. Illustration generation
- **Parallel Processing**: 3 versions simultaneously (WeChat, Xiaohongshu, Douyin)

#### Publisher Agent (`publisher.py`)
- **Purpose**: Multi-platform distribution
- **Method**: Push to draft boxes (never auto-publishes)
- **Platforms**: WeChat, Xiaohongshu, Douyin, Kuaishou, Video Channel, Toutiao

#### Feedback Agent (`feedback.py`)
- **Purpose**: Performance data recovery and analysis
- **Schedule**: Daily at 22:00
- **Output**: Viral detection, strategy updates, scout weight tuning

#### Knowledge Agent (`knowledge.py`)
- **Purpose**: Article archiving
- **Storage**: Markdown with wikilink format
- **Location**: `kb/` directory

### 2. Web Dashboard (`dashboard/`)

#### Backend (FastAPI)
- **Port**: 8710
- **Routes**: 12 modules (pipeline, approval, topics, data, kb, config, health, traces, prompts, reader, reviews, sources)
- **Database**: SQLite with 8 domain modules (core, sessions, versions, tokens, config_ops, traces, prompts, manual_reviews)
- **Authentication**: Optional API Key with timing-safe comparison
- **WebSocket**: Real-time pipeline status push (`/ws/pipeline`)
- **Background Tasks**: Action scanning, budget monitoring, timeout handling
- **API Documentation**: Auto-generated OpenAPI docs available at `/api/docs` (Swagger UI) and `/api/redoc` (ReDoc)

#### Frontend (Vue 3)
- **Port**: 5173 (dev mode)
- **Framework**: Vue 3.5 + Vite 8 + Pinia
- **Features**:
  - Real-time pipeline status (WebSocket)
  - Approval queue with multi-version preview
  - Topic management
  - Cost tracking and analytics
  - Quality flywheel visualization

### 3. Configuration System (`config/`)

#### Core Configuration
- `settings.py` — All runtime config (paths, LLM settings, schedules, platform config)
- `models.json` — Model pricing for token cost calculation
- `quality_gates.json` — Quality thresholds (proofread: 60, critique: 70, title: 75)
- `proofread_patterns.json` — AI-slop detection patterns (23 regex)
- `writing_styles.json` — Style presets (8 types + 3 defaults)

#### Prompt Templates (`config/prompts/`)
- 26 templates total (7 .txt + 19 .md)
- Database-backed versioning
- Auto-import from files on startup
- Types: scout_scoring, writer_draft, writer_proofread, writer_critique, writer_title, feedback_strategy

### 4. Data Layer (`queue/`, `kb/`, `data/`)

#### Queue System (`queue/`)
- JSON file system for agent communication
- Atomic write pattern (`.tmp` + rename)
- Directories: `pending/`, `review/`, `actions/`

#### Knowledge Base (`kb/`)
- Markdown format with wikilink
- FTS5 full-text search (trigram tokenizer)
- Sections: articles, viral, strategy

#### Runtime Data (`data/`)
- Logs and cost CSVs
- Execution traces
- Performance metrics

---

## Content Production Pipeline

### Daily Workflow

```
09:00  Scout Agent scans sources → topic candidates
09:30  Human confirms topic via Dashboard
09:30  Writer Router dispatches to 3 parallel workers:
       ├── WeChat Worker (2000-3000 words deep-dive)
       ├── Xiaohongshu Worker (300-800 chars + emoji)
       └── Douyin Worker (15-60s video script)
10:30  Articles ready for review
10:45  Human approves/rejects via Dashboard
11:00  Publisher Agent pushes to platform draft boxes
14:00  Afternoon session (repeat)
22:00  Feedback Agent recovers performance data
```

### Quality Pipeline (7 Stages)

1. **Source Fetch** — Retrieve original article content
2. **LLM Draft** — Generate initial draft using prompt templates
3. **AI-Slop Proofread** — Detect and fix AI-generated patterns (23 regex)
4. **Critique & Rewrite** — Up to 3 rounds of review and improvement
5. **Format Adaptation** — Platform-specific formatting
6. **Title Optimization** — Generate multiple title options
7. **Illustration** — AI-generated images (Agnes AI)

### Platform Distribution

| Platform | Method | Content Type | Status |
|----------|--------|--------------|--------|
| WeChat Official Account | baoyu-post-to-wechat API | Deep-dive article | Phase 1 |
| Xiaohongshu | AiToEarn MCP | Infographic post | Phase 1 |
| Douyin | AiToEarn MCP | Video script | Phase 1 |
| Kuaishou | AiToEarn MCP | Video content | Phase 1 |
| WeChat Video Channel | AiToEarn MCP | Video content | Phase 1 |
| Toutiao | Playwright automation | Article | Phase 3 |
| Baijiahao | WeChat content sync | Article | Phase 3 |

---

## Configuration Guide

### Environment Variables

**Required**:
- `LLM_BASE_URL` — LLM API endpoint (OpenAI-compatible)
- `XIAOMI_API_KEY` — LLM API key

**Optional**:
- `LLM_MODEL` — Model name (default: `mimo-v2.5`)
- `FEISHU_WEBHOOK_URL` — Alert notifications
- `MONTHLY_BUDGET_USD` — Cost cap (default: 15)
- `API_KEY` — API authentication key (leave empty to disable auth)
- `CORS_ORIGINS` — Allowed CORS origins (default: localhost:5173, localhost:8710)

### Quick Start

```bash
# Interactive setup (recommended)
bash scripts/setup.sh

# Manual setup
pip install -e .
cd dashboard/frontend && npm install && cd ../..
export LLM_BASE_URL="https://your-api-endpoint/v1"
export XIAOMI_API_KEY="your-api-key"
bash scripts/init_directories.sh

# Run dashboard
python3 dashboard/backend/main.py          # Backend (port 8710)
cd dashboard/frontend && npm run dev       # Frontend (port 5173)
```

### Daily Operation

1. Open Dashboard at `http://localhost:5173`
2. Pick a topic from the Topics tab
3. Review 3 article versions in the Approval tab
4. Approve or reject with feedback
5. Approved content auto-distributes to platform draft boxes

---

## Cost Structure

### Per-Article Cost Breakdown

| Component | Cost |
|-----------|------|
| Scout scoring | ~$0.015 |
| Writer (draft) | ~$0.035 |
| Proofreading | ~$0.010 |
| Critique (avg 1.5 rounds) | ~$0.022 |
| Titles + formatting | ~$0.006 |
| Xiaohongshu/Douyin versions | ~$0.030 |
| **Single article total** | **~$0.12–0.20** |

### Daily/Monthly Estimates

| Metric | Cost |
|--------|------|
| Daily (2 sessions × 3 versions) | ~$0.25–0.80 |
| Monthly | ~$7–25 |

---

## Testing

### Test Framework

- **Framework**: pytest
- **Markers**: `@pytest.mark.integration`, `@pytest.mark.slow`
- **Coverage**: 80% minimum target

### Test Commands

```bash
pytest                                     # Run all tests
pytest tests/test_scout.py                 # Run single test file
pytest -m integration                      # Run integration tests only
pytest --cov=skills --cov-report=term      # Coverage report
```

### Test Structure

```
tests/
├── test_scout.py              Scout agent tests
├── test_writer.py             Writer pipeline tests
├── test_publisher.py          Publisher tests
├── test_api_*.py              API endpoint tests
├── test_integration.py        Integration tests
└── conftest.py                Shared fixtures
```

---

## Development

### Key Files

| File | Purpose |
|------|---------|
| `config/settings.py` | All runtime configuration |
| `skills/llm.py` | Shared LLM utility with fallback chain |
| `skills/action.py` | JSON action file protocol |
| `skills/common.py` | Shared utilities (AgentBase, metrics, load_prompt) |
| `dashboard/backend/main.py` | FastAPI entry point |
| `dashboard/backend/database/core.py` | SQLite connection management |

### Development Workflow

1. **Research & Reuse** — Search for existing implementations first
2. **Plan First** — Create implementation plan
3. **TDD Approach** — Write tests first, then implement
4. **Code Review** — Review before commit
5. **Commit & Push** — Follow conventional commits format

### Code Quality

- **File Size**: 200-400 lines typical, 800 max
- **Function Size**: <50 lines
- **Nesting**: <4 levels
- **Error Handling**: Explicit at every level
- **Input Validation**: Schema-based at system boundaries

---

## Deployment

### Docker

```bash
docker compose up -d                       # Start services
docker compose logs -f dashboard           # View logs
```

### Manual Deployment

```bash
# Backend
python3 dashboard/backend/main.py

# Frontend (build)
cd dashboard/frontend
npm run build
# Serve dist/ directory
```

---

## External Dependencies

| Service | Purpose | Integration |
|---------|---------|-------------|
| Hermes Agent | Orchestration engine (cron + Skill + MCP client) | MCP |
| AiToEarn | Multi-platform distribution channel | MCP |
| china-hot-mcp | Chinese hot topics aggregation | MCP |
| x-tweet-fetcher | Twitter data collection | API |
| Firecrawl | Web search | API |
| baoyu-skills | Image generation + WeChat publishing | MCP |

---

## Project Structure

```
ai-content/
├── skills/                    # Agent implementations (Python)
│   ├── scout.py               Topic discovery & scoring
│   ├── writer.py              7-stage article pipeline
│   ├── publisher.py           Platform draft box dispatch
│   ├── feedback.py            Data recovery & analysis
│   ├── knowledge.py           Article archiving
│   └── ...                    (27 Python files)
├── dashboard/                 # Web Dashboard
│   ├── backend/
│   │   ├── main.py            FastAPI (port 8710)
│   │   ├── routes/            12 route modules
│   │   ├── database/          8 domain modules
│   │   └── ...                (9 Python files)
│   └── frontend/              Vue 3 + Vite (port 5173)
│       ├── src/
│       │   ├── components/    Vue components
│       │   ├── views/         Page views
│       │   ├── stores/        Pinia stores
│       │   └── composables/   Vue composables
│       └── ...                (23 Vue files, 16 TS files)
├── config/                    # Runtime configuration
│   ├── prompts/               26 prompt templates
│   └── ...                    (settings, models, styles, patterns)
├── docs/                      # Documentation
├── scripts/                   # Operational scripts
├── queue/                     # Agent communication (JSON files)
├── kb/                        # Knowledge base (Markdown)
├── data/                      # Runtime data (logs, cost CSVs)
├── tests/                     # Test suite (47 test files)
├── pyproject.toml             Python package declaration
└── docker-compose.yml         Docker configuration
```

---

## Version History

**Current Version**: v0.9.9 (2026-06-06)

### Recent Changes

- 安全性审查 — 异常详情泄露修复 + 系统性安全扫描
- 监控指标端点 — /api/metrics + /api/metrics/summary
- 屏幕阅读器测试清单 — 10 个场景标准化测试流程
- WriterAgent 优化 — 提取 writer_helpers 模块，561→449 行 (-20%)
- E2E 测试补充 — writer_helpers 单元测试 15 个用例
- 用户体验改进 — aria-live 播报 + aria-label 补全 + focus trap 验证
- 部署运维改进 — GitHub Actions CI + Docker 健康检查验证
- 测试覆盖改进 — 3 个核心视图组件测试 + 21 个新测试用例
- 代码质量改进 — DEPRECATED 模块清理 + WriterAgent 拆分

---

## License

MIT License — see [LICENSE](LICENSE)

---

*稿定 = 稿 (content draft) + 定 (get it done). AI handles the writing; you handle the decisions.*
