# ARCHITECTURE.md — 稿定系统架构

> 最后更新: 2026-06-05 | 基于 v0.8.1 代码现状

## 系统总览

```
┌─────────────────────────────────────────────────────────────────┐
│                      稿定 (Gaoding)                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  Scout   │───→│  Writer  │───→│ Publisher│───→│ Feedback │  │
│  │  选题    │    │  写作    │    │  分发    │    │  反馈    │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │               │               │               │         │
│       └───────────────┴───────────────┴───────────────┘         │
│                           │                                     │
│                    ┌──────┴──────┐                               │
│                    │  queue/     │  JSON 文件系统                 │
│                    │  (Agent 通信)│                               │
│                    └──────┬──────┘                               │
│                           │                                     │
│  ┌────────────────────────┼────────────────────────────────┐    │
│  │                Dashboard (FastAPI + Vue 3)               │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │    │
│  │  │ REST API│  │WebSocket│  │ SQLite  │  │Background│   │    │
│  │  │12 routes│  │实时推送  │  │8 模块   │  │ 任务    │   │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## 技术栈

| 层 | 技术 |
|----|------|
| 后端语言 | Python 3.14+ |
| Web 框架 | FastAPI 0.115 |
| 数据库 | SQLite (WAL mode) |
| 数据验证 | Pydantic v2 |
| 前端框架 | Vue 3.5 + TypeScript |
| 构建工具 | Vite 8 |
| 状态管理 | Pinia |
| 图表 | Chart.js |
| LLM | OpenAI-compatible API (默认: xiaomimimo.com) |
| Agent 通信 | JSON 文件系统（queue/ 目录） |
| 外部服务 | Hermes Agent, AiToEarn, china-hot-mcp, Firecrawl |

## Agent 架构

### Agent 通信协议

Agent 之间通过 `queue/` 目录下的 JSON 文件通信，不使用外部消息队列。

```
queue/
├── pending/        Scout 写入待确认选题
├── review/         Writer 写入待审批文章
├── actions/        Dashboard 写入人工指令
│   ├── processed/  已处理的 action
│   └── failed/     处理失败的 action
├── status/         各 Agent 运行状态
├── images/         生成的配图
├── videos/         生成的视频
├── sources/        采集的原始数据
├── tokens/         Token 使用记录
├── trails/         执行轨迹
└── tmp/            临时文件
```

**写入协议**（原子操作）：
1. 写入 `.tmp` 临时文件
2. `fsync` 确保持久化
3. `rename` 替换目标文件（原子操作）

### Agent 职责

| Agent | 入口 | 职责 |
|-------|------|------|
| Scout | `skills/scout.py` | 扫描 10+ 信源，LLM 评分，输出待确认选题 |
| Writer | `skills/writer.py` | 7 阶段管线：抓原文→初稿→审校→批评修订→排版→标题→配图 |
| Publisher | `skills/publisher.py` | 分发到各平台草稿箱（不自动发布） |
| Feedback | `skills/feedback.py` | 回收阅读量数据，检测爆文，更新策略 |
| Knowledge | `skills/knowledge.py` | 归档文章到 kb/ 知识库 |

### Writer 管线详情

```
Stage 1: 抓取原文（HTTP 请求 + 内容提取）
Stage 2: LLM 初稿生成（基于模板 + 人设圣经）
Stage 3: AI-slop 审校（23 个 regex 模式检测）
Stage 4: 批评修订（scorer + critic 并行，最多 3 轮）
Stage 5: 排版格式化
Stage 6: 标题优化（多候选 + 评分）
Stage 7: 配图生成（Agnes AI，可选视频生成）
```

质量门禁阈值（`config/quality_gates.json`）：
- 审校分 ≥ 60
- 批评分 ≥ 70
- 标题分 ≥ 75
- 最大修订轮数: 3

## Dashboard 架构

### 后端模块

```
dashboard/backend/
├── main.py              FastAPI 入口（中间件 + 路由挂载）
├── routes/              12 个路由模块
│   ├── pipeline.py      管线状态、触发、时间线
│   ├── approval.py      审批队列、审批/驳回、版本管理
│   ├── topics.py        选题候选、确认
│   ├── data.py          成本追踪、数据分析
│   ├── kb.py            知识库搜索、分段、重建索引
│   ├── config.py        系统配置（调度/风格/门禁/信源/预算/飞轮）
│   ├── health.py        健康检查
│   ├── traces.py        执行追踪
│   ├── prompts.py       提示词版本管理
│   ├── reader.py        原文抓取代理（SSRF 防护）
│   ├── reviews.py       人工抽检
│   └── sources.py       信源流管理
├── database/            SQLite 数据层（8 个领域模块）
│   ├── core.py          连接管理、缓存、schema 初始化
│   ├── sessions.py      管线会话 CRUD
│   ├── versions.py      平台版本 + 审批记录 + 质量飞轮
│   ├── tokens.py        Token 用量 + 预算控制
│   ├── config_ops.py    配置键值存取
│   ├── traces.py        执行追踪（批量查询优化）
│   ├── prompts.py       提示词版本管理
│   └── manual_reviews.py 人工抽检记录
├── auth.py              API Key 认证（hmac.compare_digest）
├── background.py        后台任务（action 扫描 + 预算监控 + 超时处理）
├── ws.py                WebSocket 实时推送（3s 轮询 + hash 检测）
├── config_service.py    配置管理服务
├── search.py            FTS5 全文搜索（trigram tokenizer）
├── feishu.py            飞书通知
├── helpers.py           共享工具函数
└── models.py            Pydantic 请求/响应模型
```

### 数据库 Schema

5 张核心表：
- `pipeline_sessions` — 管线会话
- `platform_versions` — 平台版本（3 版本/文章）
- `approval_records` — 审批记录
- `token_usage` — Token 用量追踪
- `config_entries` — 配置键值存储

附加：
- FTS5 虚拟表 — 知识库全文搜索
- `prompt_versions` — 提示词版本管理
- `manual_reviews` — 人工抽检记录

### 前端结构

```
dashboard/frontend/src/
├── App.vue              主布局（导航 + 连接状态 + 通知）
├── views/
│   ├── PipelineView     管线状态 + 时间线
│   ├── ApprovalView     审批队列 + 多版本预览
│   ├── TopicsView       选题管理
│   ├── DataView         数据分析图表
│   └── KbView           知识库搜索
├── stores/
│   └── dashboard.ts     Pinia 状态管理
└── components/          共享组件
```

## 数据流

### 日常工作流

```
09:00  Scout 扫描信源 → LLM 评分 → queue/pending/{topic_id}.json
         ↓
09:30  人工在 Dashboard 确认选题 → queue/actions/ 写入 action
         ↓
09:30  Writer Router 读取 action → 并行启动 3 个 Worker
         ├── WeChat Worker (2000-3000 字长文)
         ├── Xiaohongshu Worker (300-800 字图文)
         └── Douyin Worker (15-60s 视频脚本)
         ↓
       每个 Worker 执行 7 阶段管线 → queue/review/{article_id}.json
         ↓
10:45  人工在 Dashboard 审批（预览 3 个版本）→ queue/actions/ 写入 action
         ↓
11:00  Publisher 读取 action → 分发到各平台草稿箱
         ↓
       Knowledge Agent → kb/ 归档
         ↓
22:00  Feedback Agent → 回收数据 → 更新选题策略
```

### 超时自动处理

- 选题 30 分钟未确认 → 自动选择最高分选题
- 审批 2 小时未响应 → 自动跳过
- 超时事件发送飞书通知

## 外部依赖

| 服务 | 用途 | 接入方式 |
|------|------|----------|
| Hermes Agent | 编排引擎（cron + Skill + MCP） | 外部进程 |
| AiToEarn | 多平台分发通道 | MCP 协议 |
| china-hot-mcp | 国内热榜聚合 | MCP 协议 |
| x-tweet-fetcher | Twitter 采集 | MCP 协议 |
| Firecrawl | Web 搜索 | API |
| baoyu-skills | 配图 + 公众号发布 | CLI |
| Agnes AI | 图片/视频生成 | CLI (子进程) |
| Kimi WebBridge | 浏览器自动化分发 | HTTP API |

## 配置体系

所有配置通过 `config/settings.py` 统一管理，自动加载 `.env`。

```
config/
├── settings.py              运行时配置（路径、LLM、调度、平台）
├── prompts/                 提示词模板（26 个）
│   ├── *.txt                数据库导入的提示词（7 个）
│   └── *.md                 写作模板（19 个：8 类型 × 2 平台 + 3 通用）
├── quality_gates.json       质量门禁阈值
├── proofread_patterns.json  AI-slop 检测模式（23 个 regex）
├── writing_styles.json      写作风格预设
├── image_styles.json        配图风格配置
├── models.json              模型价格配置
├── model_fallback.json      模型 fallback 链
├── sources.json             信源配置
└── schedule.json            调度配置
```

## 安全设计

| 机制 | 实现 |
|------|------|
| API 认证 | `X-API-Key` header, `hmac.compare_digest` timing-safe |
| SSRF 防护 | `_SSRFSafeTransport` 验证重定向目标 |
| 输入校验 | Pydantic 模型 + 自定义校验 |
| XSS 防护 | DOMPurify 净化 Markdown 渲染 |
| 密钥脱敏 | 日志中只显示前 4 位 + 后 4 位 |
| 速率限制 | 120 请求/分钟/IP |
| CORS | 默认仅允许 localhost |
| 子进程注入 | 参数白名单校验 + 临时文件传递 |

## 部署架构

### 本地开发

```
Terminal 1: python3 dashboard/backend/main.py    # 后端 :8710
Terminal 2: cd dashboard/frontend && npm run dev  # 前端 :5173
Terminal 3: python3 skills/scout.py               # 手动触发 Agent
```

### Docker

```bash
docker compose up -d    # 包含 dashboard + watchdog
```

### 生产环境要求

- `ENV=production` 强制要求 `API_KEY`
- 绑定 `127.0.0.1`（通过反向代理暴露）
- SQLite WAL 模式支持并发读
