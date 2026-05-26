# 稿定 — AI 内容生产系统

> **发现热点 → 生成 3 版本 → 推送草稿箱**  
> 你只负责选题和审批，其余全部自动完成。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/)
[![Vue 3](https://img.shields.io/badge/vue-3.5-4FC08D.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)

---

## 为什么需要稿定？

内容创作者 80% 的时间花在重复劳动上：找热点、写文章、适配不同平台、登录各平台后台发布。

**稿定**自动化了整个管线：

- **选题 Agent** 扫描 10+ 来源（微博、知乎、B站、GitHub、RSS、Web 搜索…）并用双层 LLM 评分
- **写手 Agent** 经 7 阶段管线，并行产出 3 个独立版本：公众号深度文、小红书图文贴、抖音视频脚本
- **分发 Agent** 将审批通过的内容推送到各平台**草稿箱**（绝不自动发布）
- **反馈 Agent** 回收效果数据反哺选题

系统不限定领域、人工在环、日循环运营，每天只需约 10 分钟人工介入。

---

## 功能特性

- 🔍 **多通道选题** — 微博、知乎、B站、抖音、头条、36氪、GitHub、RSS、Firecrawl 搜索、手动素材
- 📊 **双层 LLM 评分** — 关注分 + 增量分，支持冷启动兜底
- ✍️ **3 版并行输出** — 公众号版（2000-3000 字）、小红书版（300-800 字 + emoji）、抖音版（15-60s 脚本）
- ✅ **7 阶段质量管線** — 抓原文 → LLM 初稿 → AI味检测 → 批评修订 → 排版 → 标题 → 配图
- 🎛️ **Web Dashboard** — 实时管线状态、审批队列（多版本预览）、选题管理、成本跟踪
- 🚫 **绝不自动发布** — 内容只到草稿箱，由你手动发布
- 🔄 **日反馈循环** — 数据回收 → 爆款分析 → 策略更新 → 选题权重调整
- 📦 **零外部依赖通信** — JSON 文件系统作为 Agent 消息队列

---

## 架构

```
Hermes Cron ─→ Scout Agent ─→ queue/pending/ ─→ 人工确认选题
                                                     ↓
                     Writer Router ──────────────────┤
                       ├── WeChat Worker (2000-3000 字)
                       ├── Xiaohongshu Worker (300-800 字)
                       └── Douyin Worker (15-60s 视频脚本)
                                                     ↓
                     queue/review/ ─→ 人工审批
                                         ↓
                     Publisher Agent ─→ 各平台草稿箱
                                         ↓
                     Knowledge Agent ─→ kb/ (归档)
                     Feedback Agent (22:00) ─→ kb/viral/ + kb/strategy/

                     Web Dashboard (FastAPI + Vue 3) 监控全局
```

---

## 快速开始

### 前置依赖

- Python 3.14+
- Node.js 20+（Dashboard 前端）
- [Hermes Agent](https://hermes-agent.nousresearch.com/) v0.14+（可选，用于定时调度）
- Playwright（可选，用于头条号分发 + 截图）

### 安装与配置

**推荐 — 交互式配置向导：**

```bash
bash scripts/setup.sh
```

脚本自动完成：检测 Python/Node 版本 → 引导填入 API Key → 写入 `.env` → 创建目录 → 安装依赖 → 可选启动 Dashboard。

**手动配置：**

```bash
# 1. 安装 Python 依赖
pip install httpx uvicorn fastapi pydantic

# 2. 安装前端依赖
cd dashboard/frontend && npm install && cd ../..

# 3. 设置 API Key
export XIAOMI_API_KEY="your-api-key-here"

# 4. 创建运行目录
bash scripts/init_directories.sh

# Playwright（可选）
pip install playwright && python3 -m playwright install chromium
```

> 配置也可通过 `.env` 文件自动加载（参考 `config/.env.example`）。
> 环境变量优先级高于 `.env` 文件。

### 运行

```bash
# 终端 1：启动 Dashboard 后端
python3 dashboard/backend/main.py

# 终端 2：启动 Dashboard 前端（开发模式）
cd dashboard/frontend
npm run dev

# 或者手动触发 Agent
python3 skills/scout.py
python3 skills/writer.py
python3 skills/publisher.py <target_id>
```

### 日常运营流程

1. 打开 Dashboard `http://localhost:5173`
2. 在"选题"标签页选取热点话题（或等待 30 分钟自动选取）
3. 在"审批"标签页审阅 3 个版本
4. 批准或驳回（附反馈理由）
5. 审过即自动分发到各平台草稿箱

---

## 项目结构

```
├── skills/                    # Agent 实现代码（Python）
│   ├── scout.py               选题 Agent
│   ├── writer.py              7 阶段写手管线
│   ├── writer_router.py       并行 Writer 路由器
│   ├── writer_xhs.py          小红书 Worker
│   ├── writer_douyin.py       抖音 Worker
│   ├── publisher.py           分发 Agent
│   ├── publisher_toutiao.py   头条号 Playwright 分发
│   ├── feedback.py            数据反馈 Agent
│   ├── knowledge.py           知识沉淀 Agent
│   ├── llm.py                 LLM 调用工具
│   └── action.py              JSON 文件协议
├── dashboard/                 # Web Dashboard
│   ├── backend/main.py        FastAPI 后端（端口 8710）
│   └── frontend/              Vue 3 + Vite 前端（端口 5173）
├── config/                    # 运行态配置
├── scripts/                   # 运维脚本
├── queue/                     # Agent 间通信（JSON 文件）
├── kb/                        # 知识库（Markdown）
└── data/                      # 运行时数据（日志、成本 CSV）
```

---

## 分发平台

| 平台 | 方式 | 状态 |
|------|------|------|
| 微信公众号 | baoyu-post-to-wechat API | ✅ Phase 1 |
| 小红书 | AiToEarn MCP | ✅ Phase 1 |
| 抖音 | AiToEarn MCP | ✅ Phase 1 |
| 快手 | AiToEarn MCP | ✅ Phase 1 |
| 视频号 | AiToEarn MCP | ✅ Phase 1 |
| 头条号 | Playwright 自动化 | Phase 3 |
| 百家号 | 同步公众号内容 | Phase 3 |

---

## 成本估算

| 组件 | 单篇成本 |
|------|---------|
| 选题评分 | ~$0.015 |
| 写手（初稿） | ~$0.035 |
| AI味检测 | ~$0.010 |
| 批评修订（平均 1.5 轮） | ~$0.022 |
| 标题 + 排版 | ~$0.006 |
| 小红书/抖音版 | ~$0.030 |
| **单篇合计** | **~$0.12–0.20** |
| **每日（2 场 × 3 版本）** | **~$0.25–0.80** |
| **每月** | **~$7–25** |

---

## License

MIT License — 详见 [LICENSE](LICENSE)。

---

*稿定 = 稿 + 定。AI 写稿，你来定夺。*
