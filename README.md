# 稿定 (Gaoding) — AI Content Production System

> **Find hot topics → Write 3 platform versions → Push to draft boxes.**  
> You just pick the topic and approve. Everything else happens automatically.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/)
[![Vue 3](https://img.shields.io/badge/vue-3.5-4FC08D.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)

---

## Why This Project?

Content creators spend 80% of their time on repetitive work: searching for trending topics, drafting articles, formatting for different platforms, and distributing to each platform's backend.

**Gaoding** automates the entire pipeline:

- **Scout** scans 10+ sources (Weibo, Zhihu, Bilibili, GitHub, RSS, Web search...) and scores topics using a two-layer LLM model
- **Writer** runs a 7-stage pipeline producing 3 independent versions simultaneously: WeChat deep-dive, Xiaohongshu infographic post, and Douyin video script
- **Publisher** pushes approved content to draft boxes (never auto-publishes)  
- **Feedback** recovers performance data and feeds insights back into future topic selection

The system is domain-agnostic, human-in-the-loop, and designed for daily operation with minimal manual effort (~10 minutes/day).

---

## Features

- 🔍 **Multi-channel topic discovery** — Weibo, Zhihu, Bilibili, Douyin, Toutiao, 36Kr, GitHub, RSS, Firecrawl web search, manual materials
- 📊 **Two-layer LLM scoring** — attention score + increment score with cold-start fallback
- ✍️ **3 parallel platform versions** — WeChat (2000-3000 words), Xiaohongshu (300-800 chars + emoji), Douyin (15-60s video script)
- ✅ **7-stage quality pipeline** — fetch source → LLM draft → AI-slop proofread → critique & rewrite → format → titles → illustrate
- 🎛️ **Web Dashboard** — real-time pipeline status, approval queue with multi-version preview, topic management, cost tracking
- 🚫 **Never auto-publishes** — content goes to platform draft boxes, you hit "publish"
- 🔄 **Daily feedback loop** — data recovery → viral detection → strategy update → scout weight tuning
- 📦 **Zero external dependencies for communication** — JSON file system as agent message queue

---

## Architecture

```
Hermes Cron ─→ Scout Agent ─→ queue/pending/ ─→ You confirm
                                                     ↓
                     Writer Router ──────────────────┤
                       ├── WeChat Worker (2000-3000 words)
                       ├── Xiaohongshu Worker (300-800 chars)
                       └── Douyin Worker (15-60s script)
                                                     ↓
                     queue/review/ ─→ You approve/reject
                                         ↓
                     Publisher Agent ─→ Platform Draft Boxes
                                         ↓
                     Knowledge Agent ─→ kb/ (archive)
                     Feedback Agent (22:00) ─→ kb/viral/ + kb/strategy/

                     Web Dashboard (FastAPI + Vue 3) monitors everything
```

---

## Quick Start

### Prerequisites

- Python 3.14+
- Node.js 20+ (for Dashboard frontend)
- [Hermes Agent](https://hermes-agent.nousresearch.com/) v0.14+
- Playwright (for Toutiao distribution + screenshots)

### Installation

```bash
# Clone
git clone https://github.com/twmissingu/ai-content.git
cd ai-content

# Python dependencies for agents
pip install httpx uvicorn fastapi pydantic

# Frontend dependencies
cd dashboard/frontend
npm install
cd ../..

# Playwright (optional, for Toutiao + screenshots)
pip install playwright
python3 -m playwright install chromium
```

### Configuration

```bash
# Set LLM API key (required)
export XIAOMI_API_KEY="your-api-key-here"
# Optional overrides
export LLM_BASE_URL="https://api.xiaomimimo.com/v1"   # default
export LLM_MODEL="mimo-v2.5"                           # default
```

### Run

```bash
# Terminal 1: Dashboard backend
python3 dashboard/backend/main.py

# Terminal 2: Dashboard frontend (dev mode)
cd dashboard/frontend
npm run dev

# Or trigger agents manually
python3 skills/scout.py
python3 skills/writer.py
python3 skills/publisher.py <target_id>
```

### Daily Operation

1. Open Dashboard at `http://localhost:5173`
2. Pick a topic from the Topics tab (or wait 30 min for auto-select)
3. Review 3 article versions in the Approval tab
4. Approve or reject with feedback
5. Approved content auto-distributes to platform draft boxes

---

## For AI Agents

This project is designed for seamless AI agent interaction:

```bash
# 1. Clone and install
git clone https://github.com/twmissingu/ai-content.git
cd ai-content
pip install httpx uvicorn fastapi pydantic

# 2. Set environment
export XIAOMI_API_KEY="your-key"
export LLM_BASE_URL="https://api.xiaomimimo.com/v1"

# 3. Run a full pipeline (morning session)
python3 skills/scout.py morning
# ... human confirms topic via Dashboard ...
python3 skills/writer.py
# ... human approves via Dashboard ...
python3 skills/publisher.py <article-id>

# 4. Or use the Dashboard background scanner for automatic dispatch
python3 dashboard/backend/main.py
# Scanner polls queue/actions/ every 10s and dispatches to agent scripts
```

**Key files for agent understanding:**
- `PRD.md` — Complete product spec (single source of truth)
- `AGENTS.md` — Agent behavior rules for AI coding assistants
- `config/settings.py` — All runtime configuration in one place
- `skills/action.py` — JSON action file protocol (atomic `.tmp + rename`)
- `skills/llm.py` — Shared LLM utility with fallback chain

---

## Project Structure

```
├── skills/                    # Agent implementations (Python)
│   ├── scout.py               Topic discovery & scoring
│   ├── writer.py              7-stage article pipeline
│   ├── writer_router.py        Parallel multi-platform dispatch
│   ├── writer_xhs.py          Xiaohongshu worker
│   ├── writer_douyin.py       Douyin script worker
│   ├── publisher.py           Platform draft box dispatch
│   ├── publisher_toutiao.py   Toutiao Playwright automation
│   ├── feedback.py            Data recovery & analysis
│   ├── knowledge.py           Article archiving
│   ├── llm.py                 Shared LLM utility
│   └── action.py              JSON file protocol
├── dashboard/                 # Web Dashboard
│   ├── backend/main.py        FastAPI (port 8710)
│   └── frontend/              Vue 3 + Vite (port 5173)
├── config/                    # Runtime configuration
├── scripts/                   # Operational scripts
├── queue/                     # Agent communication (JSON files)
├── kb/                        # Knowledge base (Markdown)
└── data/                      # Runtime data (logs, cost CSVs)
```

---

## Platform Distribution

| Platform | Method | Status |
|----------|--------|--------|
| WeChat Official Account | baoyu-post-to-wechat API | ✅ Phase 1 |
| Xiaohongshu | AiToEarn MCP | ✅ Phase 1 |
| Douyin | AiToEarn MCP | ✅ Phase 1 |
| Kuaishou | AiToEarn MCP | ✅ Phase 1 |
| WeChat Video Channel | AiToEarn MCP | ✅ Phase 1 |
| Toutiao | Playwright automation | Phase 3 |
| Baijiahao | WeChat content sync | Phase 3 |

---

## Cost Estimates

| Component | Per-article Cost |
|-----------|-----------------|
| Scout scoring | ~$0.015 |
| Writer (draft) | ~$0.035 |
| Proofreading | ~$0.010 |
| Critique (avg 1.5 rounds) | ~$0.022 |
| Titles + formatting | ~$0.006 |
| Xiaohongshu/Douyin versions | ~$0.030 |
| **Single article total** | **~$0.12–0.20** |
| **Daily (2 sessions × 3 versions)** | **~$0.25–0.80** |
| **Monthly** | **~$7–25** |

---

## License

MIT License — see [LICENSE](LICENSE).

---

*稿定 = 稿 (content draft) + 定 (get it done). AI handles the writing; you handle the decisions.*
