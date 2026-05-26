# AI 内容生产工作流与管理系统 — 产品需求文档

> 版本：v1.4  
> 日期：2026-05-25  
> 状态：开发者独立技术审核版（全栈工程师视角，聚焦工程依赖与实现盲区）  
> 基于 Hermes Agent + FastAPI + Vue 3 + SQLite 技术栈

---

## 目录

1. [项目概述](#一项目概述)
2. [系统架构](#二系统架构)
3. [核心模块](#三核心模块)
4. [内容标准](#四内容标准)
5. [工作流与调度](#五工作流与调度)
6. [Web Dashboard](#六web-dashboard)
7. [平台分发矩阵](#七平台分发矩阵)
8. [知识库设计](#八知识库设计)
9. [配置系统](#九配置系统)
10. [信息源获取方案](#十信息源获取方案)
11. [风险与应对](#十一风险与应对)
12. [实施路线图](#十二实施路线图)

---

## 一、项目概述

### 1.1 背景与目标

利用 AI Agent 能力，按照项目级投产标准，建立一套内容生成发布的通用工作流和管理系统。目标是通过 AI 能力产出高质量内容并能够流量变现。

**核心原则：**
- 通用可配置：系统领域无关，通过配置适配不同内容方向
- 人在回路：选题和发布前必须人工确认
- 质量优先：每篇文章通过质量门后才进入分发环节
- 知识沉淀：每篇内容、每个数据都反哺知识库

### 1.2 核心价值

| 角色 | 价值 |
|------|------|
| **内容创作者** | 选题→写作→配图→排版→发布全流程自动化，节省80%执行时间 |
| **运营者** | 数据反馈飞轮驱动选题策略持续优化 |
| **管理者** | Dashboard 实时看板，管线状态一目了然 |

### 1.3 默认领域配置

- **领域：** 科技/AI
- **语气：** 口语化
- **立场：** 强烈观点
- **篇幅：** 深度长文（2000-3000字）
- **发布平台：** 小红书、微信公众号、头条号、百家号、知乎（暂缓）

### 1.4 成功指标与成本估算

**北极星指标：**
- 单篇文章平均阅读量月环比增长
  - 数据来源：Feedback Agent（Phase 3 就绪前不可用，初期需手动在各平台后台查看后录入 Dashboard）
- 单篇内容综合成本（Token + API 调用 + 图片生成）递减趋势

**过程指标：**
| 指标 | 说明 | 健康值参考 |
|------|------|-----------|
| 选题通过率 | 人工确认选题数 / Scout 推送候选数 | > 40%（Scout 质量够好则高） |
| 审批通过率 | 通过篇数 / 总审批篇数 | > 70%（过高说明质量门太松） |
| 平均重写轮数 | 每篇文批评修订平均轮数 | 1-2 轮（理想） |
| 管线成功率 | 按时完成的时段 / 总时段 | > 95% |
| 分发成功率 | 成功推送平台数 / 目标平台数 | > 90% |

**成本估算（以 Claude Sonnet 4 为例）：**
| 环节 | 估算 Tokens（输入+输出） | 单次成本 |
|------|------------------------|---------|
| Scout 选题评估 | ~5K | $0.015 |
| Writer 初稿（公众号标准） | ~8K（含素材）→ ~3K 输出 | $0.035 |
| AI腔审校 | ~3.5K | $0.010 |
| 批评修订（平均 1.5 轮） | ~5K × 1.5 | $0.022 |
| 标题优化 + 排版 | ~2K | $0.006 |
| 小红书/抖音版本（并行） | ~5K × 2 版本 | $0.030 |
| 图片生成 | 按 baoyu 实际调用次数 | $0.01-0.05/张 |
| **单篇综合（含重写）** | **~35K** | **~$0.12-0.20** |
| **日成本（2篇×3版）** | **~70K** | **~$0.25-0.40** |
| **月成本** | **~2.1M** | **~$7-12** |

> **⚠️ 成本估算假设：** 上述估算假设配图采用 HTML 模板渲染（免费）。如使用 baoyu-article-illustrator 生成配图（~$0.01-0.05/张），单篇综合成本可能升至 **$0.20-0.50**（6 张配图约 $0.06-0.30）。批评修订若跑满 3 轮，日成本可能翻倍至 **$0.50-0.80/天**。月成本波动区间 **$7-25**，取决于配图策略和重写轮数。详见 3.2 节配图降级策略。

**成本控制上限机制：**
- 在配置系统中设置"月成本上限"（默认 $15/月）
- SQLite 中记录每日 Token 消耗和估算费用
- 当累计消耗接近上限（>80%）→ Dashboard 橙色警告 + 飞书提醒
- 达到上限 → 自动暂停管线 + 飞书通知"本月成本已用尽"
- 用户可在 Dashboard 手动"恢复管线"（重置上限检查）
- 可在配置中修改上限值

---

## 二、系统架构

### 2.1 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                      Hermes Agent（编排层）                        │
│   Cron调度 · Skill引擎 · MCP客户端 · /llm-wiki · 飞书通知         │
└──────────┬──────────┬──────────┬──────────┬────────────────────┘
           │          │          │          │
     ┌─────┘     ┌────┘    ┌────┘    ┌────┘
     ▼           ▼         ▼         ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────┐
│ Scout   │ │ Writer  │ │Publisher│ │ Knowledge    │
│ Agent   │ │ Agent   │ │ Agent   │ │ Agent        │
├─────────┤ ├─────────┤ ├─────────┤ ├──────────────┤
│·热榜API │ │·LLM初稿 │ │·WeChat  │ │·选题库(MD)   │
│·Twitter │ │·AI腔   │ │  API    │ │·爆款库(MD)   │
│·RSS    │ │  审校   │ │·AiToEarn│ │·历史库(MD)   │
│·Fire-  │ │·批评修订 │ │  MCP    │ │·策略库(MD)   │
│ crawl  │ │·baoyu   │ │·Play-   │ │·素材库(MD)   │
│·选题   │ │  配图   │ │ wrght   │ │ (Obsidian)   │
│  评分  │ │·标题优化 │ │·queue/  │ │              │
│·人工   │ │·排版    │ │ failed  │ │              │
│  确认  │ │·质量门  │ │  告警   │ │              │
│        │ │  (70+)  │ │         │ │              │
└─────────┘ └─────────┘ └─────────┘ └──────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│                Web Dashboard（FastAPI + Vue 3）                    │
│   Pipeline · 审批队列 · 选题推荐 · 数据分析 · 知识库检索         │
│   常驻服务 · 自动刷新 · 审批操作 · 配置管理                      │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| **编排引擎** | Hermes Agent | 调度、Skill、MCP客户端、Cron。支持 `hermes gateway` 命令。详细地址/安装方式待 Phase 0 PoC 确认 |
| **Agent 通信** | JSON 文件系统 | queue/ 目录作为消息队列 |
| **后端 API** | FastAPI (Python 3.12) | Dashboard 后端 + 知识库服务 |
| **前端** | Vue 3 + Vite | Dashboard 交互界面 |
| **图表** | Chart.js | 数据可视化 |
| **数据库** | SQLite | Dashboard 元数据、分析数据 |
| **知识库** | Markdown + wikilink | 人工可读、Agent 可操作 |
| **信息源 MCP** | china-hot-mcp | 国内热榜聚合 |
| **Twitter 采集** | x-tweet-fetcher | Twitter/X 内容获取 |
| **Web 搜索** | Firecrawl（Hermes 内置） | 网页搜索与内容提取 |
| **AI 模型** | Hermes 配置的 LLM 提供商 | 写作、审校、评分 |
| **图片生成** | baoyu-article-illustrator / LLM 内置 | 文章配图 |

### 2.3 数据流

```
Scout → queue/pending/ → 飞书选题确认
          ↓ 确认
Writer → queue/review/ → 飞书审批卡片
          ↓ 通过 → Publisher → 各平台草稿箱
          ↓ 驳回 → Writer 重写 → queue/review/（最多3轮）

Knowledge Agent 持续读写 kb/ 目录
Feedback Agent 每日回收数据 → 更新 kb/viral/ + kb/strategy/
Dashboard 持续监控 queue/ + kb/ + data/
```

### 2.4 部署模型

```
┌─────────────────────────────────────────────────────────────────┐
│                        单机服务器                                  │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Hermes     │  │  FastAPI     │  │  Playwright  │           │
│  │  Gateway    │  │  Dashboard   │  │  (头条号)    │           │
│  │  (常驻进程) │  │  (常驻进程)  │  │  (按需调用)  │           │
│  └──────┬──────┘  └──────┬───────┘  └──────────────┘           │
│         │                │                                       │
│         └──────┬─────────┘                                       │
│                ▼                                                  │
│     ┌──────────────────┐                                        │
│     │  共享文件系统      │   ← queue/ + kb/ + data/ + config/    │
│     │  (项目目录)       │                                        │
│     └──────────────────┘                                        │
│                                                                   │
│  Hermes cron → Python 脚本 → 读写 queue/                          │
│  FastAPI → SQLite + 读取 queue/ → Vue 3 前端                     │
│  两者通过文件系统共享状态，不依赖外部消息队列                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   系统监控与自愈                                    │
│                                                                   │
│  watchdog.sh（系统 crontab 每分钟）                                │
│   ├─ 检查 Hermes gateway 是否存活 → 否则重启 + 飞书告警          │
│   ├─ 检查 FastAPI 是否存活 → 否则重启 + 飞书告警                 │
│   └─ 检查磁盘空间 /tmp/hermes/queue/ 积压 → 告警                 │
└─────────────────────────────────────────────────────────────────┘
```

**约束条件：**
- 所有组件部署在同一台服务器，通过共享文件系统（项目根目录）通信
- Hermes cron 触发的 Python 脚本操作 `queue/` 目录
- FastAPI Dashboard 读取同一 `queue/` 和 SQLite
- 不依赖 Docker（Hermes 进程 + FastAPI 进程直接运行）
- 非单机场景：需在项目根目录挂载共享卷（NFS / EFS），但首次发布不要求

### 2.5 Agent 状态报告机制

Agent 间通过 JSON 文件系统通信，但 Dashboard 需要实时了解每个 Agent 的进度。实现方式：

**状态文件协议：**
```
queue/status/
├── scout.json              ← 当前状态 {"agent":"scout","stage":"collecting","started_at":"09:00:05"}
├── writer-router.json      ← Router 聚合状态（含并行 Worker 概览）
├── writer-worker-wechat.json   ← Writer Worker 1: 公众号标准
├── writer-worker-xhs.json      ← Writer Worker 2: 小红书标准
├── writer-worker-douyin.json   ← Writer Worker 3: 抖音标准（Phase 4）
├── publisher.json
└── feedback.json
```

**Writer Worker 状态文件字段：**
```json
{
  "agent": "writer",
  "worker": "wechat",            // wechat | xhs | douyin
  "stage": 4,                    // 当前阶段编号 (1-7)
  "stage_name": "批评修订",
  "progress_pct": 65,
  "detail": "第2轮修订中...",     // 可读性描述
  "started_at": "2026-05-25T09:35:00",
  "estimated_end": "2026-05-25T09:55:00",
  "error": null
}
```

**Router 聚合状态文件：**
```json
{
  "agent": "writer",
  "router": true,
  "workers": {
    "wechat": {"status": "running", "stage": 4, "progress_pct": 65},
    "xhs": {"status": "running", "stage": 3, "progress_pct": 40},
    "douyin": {"status": "idle", "stage": null, "progress_pct": 0}
  },
  "status": "running",
  "started_at": "2026-05-25T09:30:00",
  "estimated_end": "2026-05-25T10:00:00"
}
```

> 文档中 2.5 节第 204 行"每个 Writer 进程独立标记"的具体化——每个 Worker 独立写自己的 status 文件，Router 汇总写入聚合状态。Dashboard 读取 writer-router.json 即可展示 Pipeline 全貌。

**超时标记机制：**
- 每个 Agent 阶段有预设最大耗时（如 Writer 单阶段 ≤ 15 分钟）
- Dashboard 轮询时检测：`now - started_at > max_duration` → 状态自动标记为 `timeout`
- 初期硬编码阈值，运行两周后根据 SQLite 历史数据计算动态阈值（P95 × 1.5）

**滚动逻辑：**
- Agent 启动时写 `in_progress` 状态
- Agent 完成时更新为 `completed` 或 `failed`
- Dashboard 轮询间隔：5-10 秒（`setInterval` 轮询后端 `/api/pipeline/status`）
- 异常中止场景：超时标记机制兜底，Dashboard 上显示黄色警告

### 2.6 Dashboard ↔ Agent 集成点

Dashboard 和 Hermes Agent 是独立进程，通过文件系统桥接：

| 操作 | 机制 | 说明 |
|------|------|------|
| **查看管线状态** | Dashboard 读 queue/status/ | 轮询 JSON 状态文件 |
| **确认选题** | Dashboard 写 queue/actions/confirm_{id}.json | 转 Hermes cron 扫描执行 |
| **审批通过** | Dashboard 写 queue/actions/approve_{id}.json | 转 Hermes cron 扫描触发 Publisher |
| **驳回重写** | Dashboard 写 queue/actions/reject_{id}.json | 含驳回原因，Hermes 回调 Writer |
| **配置变更** | Dashboard 写 config/*.json | 部分配置需更新 Hermes config.yaml |
| **重写操作** | Dashboard 写 queue/actions/rewrite_{id}.json | 人工触发重写（不受3轮限制） |

**文件触发协议：**
```
queue/actions/
├── confirm_20260525_01.json    ← "写入即触发"
├── approve_20260525_01.json
├── reject_20260525_01.json     ← 含 "reason": "论点不够新颖"
└── rewrite_20260525_01.json
```

**Action 文件 JSON Schema：**
```json
{
  "action": "approve",          // 动作类型: confirm | approve | reject | rewrite | test_scout
  "target_id": "20260525-morning-wechat",  // 目标内容/选题 ID
  "timestamp": "2026-05-25T10:45:00Z",    // 操作时间
  "reason": null,               // 驳回时填充驳回原因
  "platform_versions": ["wechat", "xiaohongshu"],  // 通过的版本列表
  "trigger_agent": "publisher"  // 此动作触发哪个 Agent 执行
}

// Hermes cron 扫描逻辑：
// 1. 扫 queue/actions/ 下的所有 .json 文件
// 2. 按 modification_time 排序，逐个处理
// 3. 解析 action 字段确定动作类型
// 4. 根据 trigger_agent 执行对应的 Hermes Skill
// 5. 处理完成后文件移至 queue/actions/processed/ 目录
```

**状态文件的区分：** action 文件（queue/actions/）表示"触发操作"，需与状态文件（queue/status/）区分。选题确认状态存储在 `queue/topics/{session_id}.confirmed`，action 文件仅用于触发 Hermes cron 执行动作。两个目录用途不同，不应混用。

**⚠️ 扫描机制与 Hermes cron 不兼容说明：**
Hermes cron 的调度模型是"固定时间点触发"（如 `0 9 * * *`），不是"每 N 秒轮询目录"。因此 `queue/actions/` 的扫描**不能依赖 Hermes cron**。改为独立进程实现：

**扫描方案：** Dashboard 后端启动一个后台线程（或 system cron 每 30 秒调用扫描脚本）：
```python
# 伪代码：Dashboard 后台线程
while True:
    for f in glob("queue/actions/*.json"):
        action = json.load(open(f))
        if action["action"] == "approve":
            subprocess.run(["hermes", "run", action["trigger_agent"], ...])
        os.rename(f, f"queue/actions/processed/{os.path.basename(f)}")
    time.sleep(30)
```

> Hermes cron 本身用于触发 Scout（09:00/14:00）和 Writer（09:30/14:30）的时段任务。`queue/actions/` 的轮询由独立的后台进程负责，两者职责分离。

**⚠️ 文件写入原子性约定：**
所有进程（Dashboard 写 action / Agent 写 status）须遵循 `.tmp + rename` 协议：
1. 先写入 `{target_path}.tmp`
2. 完成后 `os.rename("{target_path}.tmp", "{target_path}")`
3. POSIX 系统上同一文件系统的 `rename()` 是原子操作
4. 读取方永远只会看到完整的文件，绝不会读到半截写入的内容
5. 建议 write + fsync 显式刷新到磁盘再 rename

**配置变更同步策略：**
- 出稿时间、信息源开关、写作风格等业务配置 → 存 `config/` 目录 + SQLite
- 直接影响 Hermes cron 调度的配置 → 需更新 Hermes config.yaml 后重启 gateway
- 重启提示："修改将在下一时段生效，当前时段不受影响"

### 2.7 项目目录结构

```
project-root/
├── skills/                     ← Hermes Skills（各 Agent 的实现代码）
│   ├── scout.py
│   ├── writer.py
│   ├── publisher.py
│   ├── feedback.py
│   └── knowledge.py
├── dashboard/                  ← Web Dashboard
│   ├── backend/                ← FastAPI (Python)
│   │   ├── main.py
│   │   ├── models/             ← SQLite ORM 模型
│   │   ├── routes/             ← API 路由
│   │   └── services/           ← 业务逻辑
│   └── frontend/               ← Vue 3 + Vite
│       ├── src/
│       │   ├── components/
│       │   ├── views/
│       │   └── stores/         ← Pinia 状态管理
│       └── ...
├── scripts/                    ← 运维脚本
│   ├── watchdog.sh
│   ├── cleanup_images.py
│   ├── scan_actions.py         ← queue/actions/ 轮询扫描脚本
│   └── init_directories.sh     ← 项目初始化脚本（创建运行态目录）
├── config/                     ← 运行态配置（由 Dashboard 写入）
│   ├── schedule.json
│   ├── writing_styles.json
│   ├── model_fallback.json
│   └── playwright_state.json
├── data/                       ← 运行态数据
│   ├── analytics.db            ← SQLite
│   └── logs/                   ← Dashboard 日志
├── queue/                      ← 运行态消息队列
│   ├── actions/                ← 操作触发文件
│   │   └── processed/          ← 已处理的 action 文件
│   ├── status/                 ← Agent 状态文件
│   ├── review/                 ← 待审批内容
│   ├── pending/                ← 待确认选题
│   ├── failed/                 ← 分发失败记录
│   ├── images/                 ← 运行时配图文件
│   ├── topics/                 ← 选题确认状态
│   └── tmp/                    ← Writer 并行 Worker 临时目录
└── kb/                         ← 知识库（Markdown + wikilink）
    ├── topics/
    ├── viral/
    ├── history/
    ├── strategy/
    ├── materials/
    └── INDEX.md
```

> 所有运行态目录（queue/ config/ data/）由 `init_directories.sh` 在项目初始化时创建。
> skills/ 目录下的 Python 文件是 Hermes Skill 的实现。Hermes 是否自动发现该目录下的 Skill 需在 Phase 0 PoC 验证；如不支持，需要在 Hermes 的 config.yaml 中手动注册。

---

## 三、核心模块

### 3.1 Scout Agent（侦察兵·选题）

**职责：** 扫描多渠道信息源，筛选出值得写的选题，推送给人工确认。

**信息源矩阵：**

| 渠道 | 方案 | 稳定性 | 说明 |
|------|------|--------|------|
| 微博热搜 | china-hot-mcp → `weibo_trending()` | ⭐⭐⭐⭐⭐ | 直连平台 API |
| 知乎热榜 | china-hot-mcp → `zhihu_trending()` | ⭐⭐⭐⭐⭐ | 直连平台 API |
| B站热门 | china-hot-mcp → `bilibili_trending()` | ⭐⭐⭐⭐⭐ | 直连平台 API |
| 百度热搜 | china-hot-mcp → `baidu_trending()` | ⭐⭐⭐⭐⭐ | 直连平台 API |
| 抖音热点 | china-hot-mcp → `douyin_trending()` | ⭐⭐⭐⭐⭐ | 直连平台 API |
| 头条热榜 | china-hot-mcp → `toutiao_trending()` | ⭐⭐⭐⭐⭐ | 直连平台 API |
| 36氪热榜 | china-hot-mcp → `kr36_trending()` | ⭐⭐⭐⭐⭐ | 直连平台 API |
| Twitter/X KOL | x-tweet-fetcher（Nitter + Playwright 双后端） | ⭐⭐⭐⭐ | 需代理+自建Nitter |
| RSS 订阅 | feedparser 标准 RSS | ⭐⭐⭐⭐⭐ | 最稳定协议 |
| GitHub Trending | GitHub REST API | ⭐⭐⭐⭐⭐ | 官方 API |
| Web 搜索 | Firecrawl `web_search`（Hermes 内置） | ⭐⭐⭐⭐⭐ | 兜底搜索 |
| 人工素材 | kb/materials/ 目录 | — | Obsidian 收藏 |

**评分模型参数规格：**

| 参数 | 值范围 | 类型 | 含义 | 由谁生成 |
|------|--------|------|------|---------|
| `source_weight` | 0.0-1.0 | 浮点数 | 信息源的权威性/可信度 | 预配置（见初始权重表） |
| `viral_score` | 0-100 | 整数 | 该话题在同类话题中的热度分 | LLM 评分 prompt 生成 |
| `freshness_score` | 0-100 | 整数 | 话题的新鲜程度（近1h=高分，近48h=低分） | 算法计算（定时差） |
| `saturation_score` | 0-100 | 整数 | 行业内已有多少文章覆盖此话题（越高=越饱和） | LLM 评分 prompt 生成 |
| `novelty_score` | 0-100 | 整数 | 该选题是否有新颖视角 | LLM 评分 prompt 生成 |
| `self_repeat_score` | 0-100 | 整数 | 自身历史是否写过类似话题（越高=越重复） | 算法（搜索 kb/history/） |
| `feasibility_score` | 0-100 | 整数 | 该话题是否容易查到资料、产生观点 | LLM 评分 prompt 生成 |

**`source_weight` 初始权重表（可按信息源开关配置调整）：**

| 信息源 | source_weight | 说明 |
|--------|--------------|------|
| Twitter/X KOL | 0.95 | 高价值观点源 |
| RSS 订阅 | 0.85 | 筛选过的信源 |
| GitHub Trending | 0.80 | 技术热点 |
| Web 搜索（Firecrawl） | 0.75 | 兜底搜索 |
| 知乎热榜 | 0.70 | 讨论度质量高 |
| 36氪热榜 | 0.70 | 商业科技 |
| 人工素材（kb/materials/） | 0.90 | 你手动收藏的内容 |
| 微博热搜 | 0.50 | 泛热点，质量不均 |
| 抖音热点 | 0.45 | 内容偏向泛娱乐 |
| 百度热搜 | 0.40 | 大众人群，与科技/AI方向匹配度低 |
| B站热门 | 0.55 | 年轻群体热点 |
| 头条热榜 | 0.50 | 大众热点 |

```
评分公式：
第一层：关注度（判断是否值得关注）
attention_score = min(100,
    (source_weight^1.3) × 0.35
    + viral_score × 0.30
    + freshness_score × 0.35
)
< 40 直接丢弃

第二层：信息增量（判断是否值得写）
increment_score = saturation_score × 0.40
    + novelty_score × 0.35
    + self_repeat_score × 0.25

最终得分 = attention_score × 0.55 + increment_score × 0.25 + feasibility_score × 0.20
< 55 淘汰 | > 70 候选 | > 85 强推
```

> 每个 LLM 评分参数（viral/saturation/novelty/feasibility）由 Scout Agent 通过 LLM 调用生成。需要设计具体的评分 prompt 模板（Phase 1 实现）。权重初始值硬编码，运行后可配置。

**冷启动参数策略（系统运行前 2 周）：**
- 爆款库（kb/viral/）和历史库（kb/history/）初始为空，影响评分模型中的参数
- `viral_score`：冷启动期使用 `source_weight` 替代（信任信息来源权重而非历史数据）
- `self_repeat_score`：冷启动期暂不启用（无历史记录时放行所有新话题）
- `saturation_score`：冷启动期默认为 0（尚未建立行业热度基线）
- 运行 2 周后有数据积累 → 自动切换为标准评分公式（viral_score 使用爆款库数据，self_repeat_score 启用，saturation_score 使用历史基线）
- Dashboard 在数据 Tab 标注"评分模型已切换为标准模式"的状态提示

**输出：** 候选列表（5-10条）→ 飞书消息卡片 → 人工确认1条

**超时策略：** 30分钟未确认 → 自动选最高分选题

**内容同质化防御：**
- **"近期话题屏蔽"硬约束**：过去 X 天内（默认 3 天）已写过的话题方向自动过滤，不进入候选列表
- **方向多样性约束**：候选列表中强制包含至少 3 个不同细分方向的选题（如 AI 工具 / 行业分析 / 产品评测 各至少 1 条）
- `self_repeat_score` 在评分模型中权重固定 25%，已保障不被同一方向多次选中
- Dashboard 数据 Tab 中展示"近期文章主题分布"词云，帮助你视觉上察觉倾向性

### 3.2 Writer Agent（写手·内容生产）

**职责：** 将选题转化为成品内容，包含7阶段自动化质量管线。

**并行架构：**

```
选题确认
    ↓
  Router（拆任务，分配标准）
    ├── Worker 1: 小红书标准  ─┐
    ├── Worker 2: 公众号标准  ─┼── 并行执行，各自跑7阶段
    └── Worker 3: 抖音标准    ─┘   （Phase 3 启用）
    ↓
  Aggregator（合并结果，写 meta.json）
    ↓
  queue/review/ 等待审批
```

**并行实现方案（方案 B — 已选定）：**
- 不依赖 Hermes 框架的原生并行能力
- Writer Hermes Skill 启动一个外部 Python 脚本
- 脚本内用 `asyncio.gather()` 或 `concurrent.futures.ThreadPoolExecutor` 并行派发 3 个子 Writer
- 每个 Worker 写独立子目录 `queue/tmp/{timestamp}-{type}/` 避免文件冲突
- Aggregator 轮询所有 Worker 完成后合并结果写 aggregated.json
- Phase 1 优先实现单 Worker（公众号标准）跑通全流程，Phase 3 再启用并行

**HTML 配图截图技术方案（选定）：**
- HTML 模板渲染信息图后，需要用截图方式转为图片文件方可投递到各平台草稿箱
- 复用 Playwright Chromium 实例（已作为头条号分发依赖安装）
- 流程：生成 HTML 模板 → Playwright `page.setContent()` → `page.screenshot()` → 保存 PNG
- 零额外安装依赖，仅增加 ~200-300MB Chromium 实例磁盘占用

**串行 vs 并行对比：**
- 串行场景：3 个版本 × ~25 分钟/版 = 75 分钟，时间线塞不下
- 并行场景：最长版本耗时 ≈ 总耗时（~25-30 分钟），时间线可行
- Token 消耗同时翻 3 倍，已纳入成本估算（见 1.4）

**7阶段管线：**

| 阶段 | 动作 | 产出 | 质量门 |
|------|------|------|--------|
| ① 抓原文 | 从选题 URL 抓取原始内容 | 原文素材 | 抓取失败→fallback到摘要 |
| ② LLM初稿 | 根据素材+写作prompt生成初稿 | 初稿.md | — |
| ③ AI腔审校 | 正则（100+规则）+ LLM双检测去AI味 | 审校后文稿 | 审校分数<70→回退 |
| ④ 批评修订 | 评委LLM打分，<70分打回重写 | 修订稿 | 最多3轮，超限降级 |
| ⑤ 排版 | 中英文空格、段落分割、hashtag | 格式化文稿 | — |
| ⑥ 标题优化 | 生成3个候选标题，分别打分选最优 | 最终标题 | — |
| ⑦ 配图 | HTML模板渲染（优先）→ baoyu-article-illustrator（增强） | 配图文件 | — |

**配图策略（三级降级）：**
```
优先：HTML 模板渲染信息图
  ├─ 零成本、即时生成、风格一致
  ├─ 适用于：小红书轮播图、公众号封面/文中图
  └─ 无需外部 API，Hermes baoyu-infographic 可用

一级降级：baoyu-article-illustrator
  ├─ 调用 image_generate 工具
  ├─ 单张 ~10-30 秒，6张 ~1-3 分钟
  └─ 超时或失败 → 继续降级

二级降级：不带图进入审批
  ├─ 你可在手动审批时决定是否补图
  └─ 不阻塞管线
```

> 配图是内容感知的关键环节，但也是最大不确定因素（API 超时、成本波动）。
> 优先使用 HTML 模板渲染（文章1已验证的方式），baoyu-article-illustrator 作为增强选项。

**输出：**
- `queue/review/{timestamp}-{type}.md` — 文章正文（各标准独立文件）
- `queue/review/{timestamp}-{type}.meta.json` — 元数据（分数、轨迹、配图路径）
- `queue/review/{timestamp}-aggregated.json` — 3个版本的聚合索引（Dashboard 读取用）

**meta.json 结构：**
```json
{
  "topic": "选题标题",
  "source_url": "原文链接",
  "platform_standard": "wechat",
  "proofread_score": 93,
  "critique_scores": [65, 92],
  "revised_rounds": 1,
  "title_score": 60,
  "title_candidates": [
    {"title": "候选标题1", "score": 60},
    {"title": "候选标题2", "score": 55},
    {"title": "候选标题3", "score": 48}
  ],
  "word_count": 2456,
  "ai_slop_issues": 3,
  "images": ["path/to/img1.png"],
  "writing_style": "wechat_default",
  "image_generation_method": "html_template",
  "status": "completed"
}
```

**平台标准输出（"3个版本"的含义明确）：**

Writer 一次输入选题，产出3个**内容独立**的标准版本。三者共享同一选题方向（主题 + 核心论点），但**风格结构、信息密度、语言组织完全不同**——不是排版模板差异，而是按各平台内容范式独立写作。

| 标准 | 字数 | 内容特点 | 附加产出 |
|------|------|---------|---------|
| 小红书标准 | 300-800字 | 第一人称经验分享，轻松口语化+emoji | 6-9张轮播图HTML |
| 公众号标准 | 2000-3000字 | 结构化论证，有观点有态度 | 品牌HTML排版 |
| 抖音标准（Phase 4） | 15-60秒脚本 | 前三秒抓眼球→核心观点→行动引导 | 脚本文字 |

> 由于三个版本是独立写作而非模板适配，LLM prompt 差异大，这是 Writer 并行架构的根本原因（串行情况下 3 个版本依次生成，时间不够）。

**AI腔审校"100+规则"来源说明：**
- Phase 1 实现约 30 条通用高频 AI 腔规则（如"值得注意的是""在这个信息爆炸的时代""正如我们之前所提到的"等句式）
- 剩余规则在 Phase 1 运行过程中根据实际输出积累，不要求一次性完成
- 各领域可自定义规则列表（当前默认科技/AI，后续切换领域时可扩展）
- **审校分数构成：** 正则检测分数 × 40% + LLM 检测分数 × 60%，综合 < 70 分回退
- 写作风格预设中的"专业度"参数影响 LLM 检测的严格程度：专业度越高，对"AI腔"判定越宽松（因为技术文章本身倾向规范的表达）

### 3.3 Publisher Agent（发行·分发）

**职责：** 将审批通过的内容分发到各平台草稿箱。

**分发矩阵：**

| 平台 | 分发方式 | 说明 |
|------|---------|------|
| **微信公众号** | WeChat API（baoyu-post-to-wechat） | 推送到草稿箱，不直接发布 |
| **小红书** | AiToEarn MCP | 推送到账号草稿箱 |
| **抖音** | AiToEarn MCP | 推送到账号草稿箱 |
| **视频号** | AiToEarn MCP | 推送到账号草稿箱 |
| **头条号** | Playwright 浏览器自动化 | 模拟登录后台推草稿箱 |
| **百家号** | 复用公众号标准内容同步 | 手动或后续自动化 |
| **知乎** | 暂缓 | — |

**头条号 Playwright session 管理：**
Playwright 分发头条号涉及浏览器自动化登录，存在以下约束：
- **初始登录需人工辅助**：首次配置需要扫码/输验证码登录
- **Cookie 持久化**：Playwright 的 `storageState` 可保存登录状态到 `config/playwright_state.json`，后续启动自动加载
- **到期重新登录**：Cookie 有过期时间（头条号通常几天到数周）。过期后 Dashboard 飞书通知"头条号需要重新登录"
- **降级策略**：不可用时降级为手动分发（你在头条号后台手动发布）

**安全原则：**
- 所有内容进目标平台草稿箱，绝不自动直接发布
- 分发失败记录到 `queue/failed/` + 飞书告警
- 单个平台失败不影响其他平台分发

### 3.4 Feedback Agent（数据分析师·反馈飞轮）

**职责：** 回收发布数据，反哺选题和写作策略。

**运行频率：** 每日1次

**⚠️ 数据可用性风险：** AiToEarn 的 MCP 工具主要包括 `createVideoDraft`、`createImageTextDraft`、`getDraftTaskStatus` —— 侧重**草稿生成链路**，不一定提供**发布后的数据分析接口**。Phase 3 实施前需验证：
1. 调研 AiToEarn MCP 有哪些 `get`/`analytics` 开头的工具
2. 如没有数据接口，Fallback 方案：Playwright 登录各平台后台抓取数据（文章1的 Feedback 即走浏览器自动化）
3. 初期简化：AiToEarn 网页端手动导出数据补充

**执行步骤：**

| 步骤 | 动作 | 产出 | 依赖 |
|------|------|------|------|
| ① 数据采集 | 通过 AiToEarn API / Playwright 自动化获取昨日发布文章的阅读/互动数据 | 写入 SQLite `analytics` 表 | AiToEarn MCP 或 Playwright 基础设施 |
| ② 爆款识别 | 识别阅读量前20%的文章，提取标题模式、关键词 | kb/viral/ 更新 | 需要基础数据累计（运行1周后生效） |
| ③ 策略写入 | 分析趋势，输出策略建议到策略库 | kb/strategy/ 更新 | 需要数据积累 |
| ④ 评分加权 | 命中爆款词库的选题在Scout中加分 | Scout 配置更新 | 需要数据积累 |

**hit_library 结构：**
```json
{
  "keywords": ["AI", "大模型", "agent", "DeepSeek"],
  "title_patterns": ["对比型", "数字型", "提问型"],
  "topic_directions": {
    "AI_tools": {"avg_reads": 1200, "count": 15},
    "industry_analysis": {"avg_reads": 800, "count": 8}
  }
}
```

### 3.5 Knowledge Agent（知识沉淀）

**职责：** 自动维护5库知识系统，沉淀经验。

**五库设计（详见第八节）。**

**操作范围（按 Phase 逐步深化）：**
| Phase | 操作 | 说明 |
|-------|------|------|
| Phase 1 | 内容归档 | 审批通过后，将文章从 queue/review/ 移动到 kb/history/{date}/（与 Publisher 联动），同时写入 kb/topics/ |
| Phase 3 | 关键词提取 + 摘要 | 提取文章关键词写入 INDEX.md，供 Dashboard 搜索使用 |
| Phase 3+ | 趋势分析 | 根据历史数据生成话题趋势，更新 kb/strategy/ |

> Phase 1 的 Knowledge Agent 本质是一个"归档移动"操作，不涉及 AI 分析。Phase 3 才加入 AI 分析能力。

### 3.6 Orchestrator（总编·调度）

**职责：** Hermes Cron 调度，编排各 Agent 执行时序。

**调度配置（默认）：**

```yaml
# ~/.hermes/config.yaml
cron:
  jobs:
    - name: "morning_scout"
      schedule: "0 9 * * *"
      prompt: "执行 Scout 选题，推送候选到飞书"

    - name: "morning_writer"
      schedule: "30 9 * * *"
      prompt: "选题已确认，启动 Writer 生产上午篇"

    - name: "afternoon_scout"
      schedule: "0 14 * * *"
      prompt: "执行 Scout 选题，推送候选到飞书"

    - name: "afternoon_writer"
      schedule: "30 14 * * *"
      prompt: "选题已确认，启动 Writer 生产下午篇"

    - name: "daily_feedback"
      schedule: "0 22 * * *"
      prompt: "执行 Feedback Agent，回收今日数据"
```

出稿时间可配置，自动推算各任务偏移时间。

---

## 四、内容标准

### 4.1 小红书标准

| 维度 | 规格 |
|------|------|
| **正文长度** | 300-800 字 |
| **语气** | 轻松口语化 + emoji |
| **立场** | 第一人称经验分享 |
| **结构** | 开头痛点/好奇 → 主体干货 → 结尾互动引导 |
| **配图** | 6-9 张轮播图（封面大字标题） |
| **标签** | 3-5 个相关 hashtag |

### 4.2 公众号标准

| 维度 | 规格 |
|------|------|
| **正文长度** | 2000-3000 字 |
| **语气** | 口语化，有观点有态度 |
| **立场** | 强烈观点输出 |
| **结构** | 开头3秒抓人 → 层层递进论证 → 总结观点 |
| **排版** | 品牌 HTML（中英文空格、短段落、引用块） |
| **配图** | 封面图1张 + 文中配图3-5张 |
| **适配平台** | 公众号、头条号、百家号、知乎 |

### 4.3 抖音标准（第二阶段）

| 维度 | 规格 |
|------|------|
| **时长** | 15-60 秒 |
| **语气** | 口语化，语速快 |
| **结构** | 前三秒抓眼球 → 核心观点 → 行动引导 |
| **产出的** | 脚本文字 + TTS 配音 + 画面描述 |

---

## 五、工作流与调度

### 5.1 日循环时间线

```
上午篇：
  09:00  Scout 选题 → 飞书推送候选（3-5条）
  09:30  人工确认选题（超时30分→自动选最高分）
  09:30-10:30  Writer 写作（7阶段管线，3个标准版本）
  10:45  飞书审批卡片推送
  10:45-11:00  人工审批（超时2小时→跳过）
  11:00  出稿完成

下午篇：
  14:00  Scout 选题 → 飞书推送候选
  14:30  人工确认选题
  14:30-16:00  Writer 写作
  16:15  飞书审批卡片推送
  16:15-16:30  人工审批
  16:30  出稿完成

晚间：
   22:00  Feedback Agent 数据回收
```

**日历配置：**
- 默认一周 7 天运行（机器不需要休息）
- 支持通过配置勾选"运行日"：周一至周日可逐日选择
- 跳过的工作日其时段一并跳过，不积压补发
- 支持的运行日配置存储在 `config/schedule.json`
- 含节假日手动暂停开关

**通知时段（免打扰）：**
- 可在配置中设置免打扰起止时间（如 22:00-08:00）
- 免打扰时段内通知策略：静默（不推送到飞书） / 次日汇总
- 在 Dashboard 集成飞书（方案 B）下实现：发消息前检查当前时间，如处于免打扰则排队到非静默时段发送

### 5.2 审批流程

```
Writer 完成
    ↓
queue/review/ 写入文章 + meta.json
    ↓
飞书消息卡片推送（内容摘要 · 质量分 · 版本数）
  （仅作通知 + 快速操作，完整审批在 Dashboard）
    ↓
  ┌── ✅ 通过 → Dashboard 写入 queue/actions/approve_{id}.json → Publisher
  ├── ❌ 驳回 → 附带原因 → Writer 重写 → 重新审批（最多3轮）
  ├── ⏸️ 暂缓 → 将审批截止时间 +2 小时
  └── ⏰ 超时（2小时）→ 自动跳过该时段
```

**飞书 vs Dashboard 审批边界划分：**

| 操作 | 飞书卡片 | Dashboard |
|------|---------|-----------|
| 查看通知 | ✅（仅摘要，无操作） | ✅ |
| 查看摘要/质量分 | ✅ | ✅ |
| 查看3版本完整内容对比 | ❌（卡片空间不足） | ✅（横向Tab预览） |
| 通过/驳回（单个版本） | ❌（localhost 限制，回调不可达） | ✅（含版本级操作） |
| 驳回填写原因 | ❌ | ✅（输入框） |
| 暂缓审批 | ❌ | ✅ |
| 查看排版预览 | ❌ | ✅（iframe安全渲染） |
| 批量历史审批 | ❌ | ✅ |

> 飞书卡片目前仅作通知用途，"🖥️ 打开面板"跳转到 Dashboard 执行操作。
> 后续如需在飞书卡片上直接操作，需 Dashboard 暴露公网端口 + 配置飞书事件订阅回调。

### 5.3 飞书审批卡片设计

**重要前提：** 需要先确认 Hermes Agent 是否原生支持飞书消息卡片及交互事件回调。
- 如 Hermes 不支持飞书 → 需自建 `feishu-notify` Hermes Skill 或由 Dashboard 后端集成飞书 SDK
- 如不支持回调 → 飞书卡片仅作通知，所有审批操作在 Dashboard 完成

**卡片布局（快速操作版）：**
```
┌─────────────────────────────────────┐
│ 📝 新文章待审批                      │
│─────────────────────────────────────│
│ 标题：[标题优化分数] 文章标题         │
│ 质量分：审校分 / 批评修订轨迹        │
│ 版本：公众号 · 小红书 · 头条号（3版） │
│─────────────────────────────────────│
│ 摘要：前100字预览...                 │
│ 全文请在 Dashboard 查看              │
│─────────────────────────────────────│
│ 驳回原因（选填）：                   │
│ ┌─────────────────────────────────┐ │
│ │                                 │ │
│ └─────────────────────────────────┘ │
│                                      │
│ [✅ 通过] [❌ 驳回] [🖥️ 打开面板]   │
└─────────────────────────────────────┘
```

**交互回调协议（如飞书支持）：**
- 用户点击"通过" → 飞书发送回调到 webhook 服务
- webhook 处理 → 写 `queue/actions/approve_{id}.json`
- 用户填写驳回原因 → 原因包含在回调 payload 中
- 不依赖飞书的情况下：通知卡片仅做 "🖥️ 打开面板" 跳转，所有操作在 Dashboard 执行

### 5.4 异常处理

| 场景 | 策略 |
|------|------|
| 选题超时未确认（>30分） | 自动选评分最高选题 |
| 审批超时无响应（>2小时） | 跳过该时段 |
| Writer 阶段失败 | 自动重试2次，仍失败→飞书告警+跳过 |
| Writer 进程异常中止 | 超时标记机制（最大阶段耗时检测）→ 状态标为异常 + 飞书告警 |
| 单平台分发失败 | queue/failed/ 记录+飞书告警，不影响其他平台 |
| LLM 调用失败 | 切换 fallback 模型（可配置 fallback 链）|
| 配图生成失败 | 三级降级：HTML模板→baoyu→不带图 |
| Agent 状态文件不更新 | Dashboard 超时检测（状态停滞>15分钟→黄色警告） |
| Hermes gateway 守护进程宕机 | 系统级 watchdog（crontab 每分钟检查）→ 自动重启 + 飞书告警 |
| AiToEarn MCP 连接断开 | 降级：跳过 AiToEarn 分发通道，其余通道照常运行 |

### 5.5 飞书集成决策（待验证）

Hermes Agent 是否原生支持飞书通知和交互卡片回调**尚未验证**，这是一个重大依赖假设。

**方案 A：自建 feishu-notify Hermes Skill（推荐）**
- 利用飞书 API 发送消息卡片
- 在 Dashboard 后端集成飞书 SDK，处理卡片交互回调
- 完整控制卡片布局和交互逻辑
- 开发量：约 2-3 天

**方案 B：Dashboard 全权负责飞书集成**
- Dashboard 后端直接发飞书消息 + 接收回调
- Hermes 只负责生产内容，不涉及飞书交互
- 开发量：约 1-2 天
- 劣势：Hermes 的交付链中缺少了"通知"环节，需要 Hermes Agent 结束时触发 Dashboard API

> **决策：** 如果 Hermes 不支持飞书，走方案 B——Dashboard 做飞书集成，流程更可控。
> **验证方法（Phase 0 PoC）：** 1) 安装 Hermes 后检查其 `deliver_to` 配置项支持哪些通知渠道；2) 如需要，编写最小 Skill 调用飞书 Webhook API 验证消息发送能力。

**⚠️ 飞书回调与 Dashboard localhost 矛盾（决策）：**
**已决策：Dashboard 不暴露公网端口。飞书卡片仅做通知，所有审批操作在 Dashboard 上完成。**
- 5.2 节的飞书操作表同步修正：飞书卡片上的"通过/驳回"标记为"仅通知，不可操作"
- 理由：Dashboard 监听 127.0.0.1（6.1 节），飞书服务器无法推送回调到 localhost
- 如需公网访问：前端加 Nginx 反向代理 + HTTPS 证书，但 Phase 1-3 不要求

**飞书回调安全（仅当方案 A 或 Dashboard 公网部署时启用）：**
- 飞书卡片交互事件以 HTTP POST 回调到 Dashboard endpoint（如 `POST /api/feishu/callback`）
- 飞书回调携带 `X-Lark-Signature` 和 `X-Lark-Request-Timestamp` 请求头
- 必须使用飞书 App Secret 计算签名并校验，拒绝签名不匹配的请求
- 防止伪造"通过"/"驳回"操作的恶意请求

---

## 六、Web Dashboard

### 6.1 概述

常驻 Web 服务，使用 FastAPI + Vue 3 + SQLite，端口 `localhost:8710`（FastAPI 后端，前端 Vite 开发服务器默认 5173）。

**安全：** Dashboard 仅监听 `127.0.0.1`（localhost），不暴露公网接口。所有操作仅本机可执行，无需 JWT 等额外认证。如需远程访问，通过 SSH 隧道转发。

**SQLite 核心表结构（`data/analytics.db`）：**

```sql
-- WAL 模式开启：PRAGMA journal_mode=WAL;
-- FastAPI 使用单 worker（workers=1），避免多进程 SQLite 写入冲突

pipeline_sessions:        -- 管线时段记录
  id, date, period(am|pm), topic, source_url, status(draft|running|completed|failed|skipped)
  
platform_versions:        -- 各平台版本
  id, session_id, platform(wechat|xhs|douyin|toutiao), status(pending|approved|rejected|rewriting), 
  content_path, meta_path, score, rewrite_round
  
approval_records:         -- 审批操作日志
  id, version_id, action(pass|reject|defer), reason, created_at, operator
  
token_usage:              -- Token 消耗记录
  id, session_id, agent, model, input_tokens, output_tokens, estimated_cost, created_at

config_entries:           -- 配置变更记录（支持双版本预览）
  key, value, effective_from, status(current|pending|expired), updated_at
```

> 上述为核心表，实施时可增减字段。不要求完整建表脚本在 PRD 中，但开发者应以此为基础设计 schema。

### 6.2 五Tab设计

| Tab | 用途 | 核心数据 |
|-----|------|---------|
| **📊 Pipeline** | 各时段管线状态 | 当前处于哪个Agent环节、耗时、成功/失败、预估成本 |
| **📋 审批队列** | 待审批内容 | 标题、质量分、平台标注、通过/驳回/重写状态 |
| **🔥 今日选题** | Scout 候选展示 | 评分、来源、新鲜度、是否已确认 |
| **📈 数据** | 发布表现与趋势 | 阅读量趋势、按平台对比、爆款词库关键词 |
| **🗄️ 知识库** | Wiki 知识检索 | 5库全文搜索、浏览 |

**Pipeline Tab 细节：**
- 每个时段显示独立的时间线，标注当前 Agent 环节
- Agent 名称旁显示当前使用模型（如 fallback 启动则变橙色）
- 每个时段旁标注"预估成本"柱（已消耗 token 数量 + 估算金额）
- Agent 异常中止时显示黄色警告 + 耗时超时提示
- 空状态：展示"系统空闲，等待下一时段" + 下一时段倒计时

**审批队列 Tab 细节：**
- 列表展示待审批内容，每行显示标题、质量分、版本数
- 点击展开 → 横向 Tab 切换 3 个版本预览（小红书轮播图缩略、公众号HTML渲染、抖音脚本）
- **版本对比预览技术实现：**
  - 公众号 HTML → iframe 安全渲染（sandbox 属性避免 XSS）
  - 小红书轮播图 → 缩略图列表 + 展开全屏预览
  - 抖音脚本 → Markdown 语法高亮展示
- 每个版本独立通过/驳回（全部通过才能分发）
- 空状态：展示"暂无待审内容" + 当前时段管线进度链接

**数据 Tab 细节：**
- Phase 2 上线时数据为空，展示："暂无数据，开始发布内容后 24 小时自动更新"
- 展示：阅读量趋势折线图、按平台对比柱状图、爆款词云
- 成本消耗趋势图（按日累计 Token/费用）
- Feedback Agent 启用后（Phase 3）数据自动填充

**今日选题 Tab 细节：**
- Scout 推送的候选列表，每项显示评分、来源、新鲜度标签
- 已确认的选题标记为绿色 ✅，已用于写作的标记为完成状态
- 空状态：展示"等待下一轮选题推送"（无当天选题时）

**知识库 Tab 细节：**
- 5 库切换 + 全文搜索
- 搜索结果高亮 + 打开 Obsidian 链接（`obsidian://open?vault=...`）

### 6.3 审批操作界面

- 以列表展示待审批内容，每行显示：标题、质量分、版本数、状态（待审/已通过/已驳回/已跳过）
- 审批队列 Tab 标签上显示未审数量角标：「审批队列(3)」
- 有新条目到达时顶栏弹出 toast 通知"新文章待审批"，3 秒自动消失
- 点击展开查看文章全文 + 排版预览（横向 Tab 切换 3 个版本）
- **版本对比视图：** 驳回重写后的新版与旧版并排展示，使用 `difflib.HtmlDiff()` 生成的 HTML 渲染，绿色标记新增内容、红色标记删除内容
- 操作按钮：通过（可逐版本操作） / 驳回（附原因） / 暂缓 / 查看详情
- 每个版本可独立操作：全部通过才触发分发
- **版本级操作隔离规则：**
  - 用户对公众号版本 ✅ 通过，小红书版本 ❌ 驳回 → 公众号状态保持"已通过"，小红书进入重写流程
  - 重写只影响被驳回的版本（小红书），不会覆盖已通过的版本（公众号）
  - 已通过的版本状态持久化到 SQLite（`platform_versions.status=approved`），关浏览器后不丢失
  - 所有版本都通过后 → Dashboard 写 `queue/actions/approve_aggregated_{id}.json` → Publisher 一次性分发所有版本到各自平台
  - 如果某个版本始终未通过（被驳回超限），系统在审批队列中标记为"当前不可分发"，其余已通过的版本保留状态
- meta.json 中的 `critique_scores` 评分轨迹以趋势线形式展示（第1轮→第2轮→第3轮）
- 操作记录全会同步到飞书

### 6.4 配置管理界面

- 出稿时间设置（自动推算Agent偏移时间）
- 写作风格预设管理（每种参数组合旁显示"预估单篇成本"）
- 质量门阈值设置
- 信息源开关（每个信息源显示连接状态：绿色已连接/黄色待验证/红色断开）
- 模型优先级设置（首选模型 → 第一 fallback → 第二 fallback，可拖拽排序）
- 配置变更提示：修改出稿时间时显示 "将在下一时段生效，当前时段不受影响"

### 6.5 平台连接状态面板

每个目标平台显示实时连接状态：

| 状态 | 说明 | Dashboard 颜色 |
|------|------|---------------|
| ✅ 已连接 | AiToEarn MCP 健康检查通过 | 绿色 |
| 🟡 待验证 | AiToEarn 已连接，但平台尚未授权 | 黄色 |
| ❌ 断开 | AiToEarn MCP 连接失败 / 平台授权过期 | 红色 |
| ⏸️ 暂缓 | 知乎等未启用平台 | 灰色 |

- 定时 health check（每 30 分钟 ping AiToEarn 连接状态）
- AiToEarn 断开仅影响通过它的分发通道，不影响 Pipeline 其他环节

### 6.6 首次启动引导（Onboarding Wizard）

系统首次启动（SQLite 数据库为空）时，Dashboard 展示全屏引导流程：

```
Step 1/3: 连接 AiToEarn
  ├─ 输入 AiToEarn API Key / MCP 地址
  ├─ 自动检测连接状态 → 显示可用的分发平台列表
  └─ 选择要启用的平台

Step 2/3: 配置 AI 模型
  ├─ 选择 LLM 提供商（Hermes 已配置的列表）
  ├─ 设置 fallback 链顺序
  └─ 测试连接

Step 3/3: 设置写作风格
  ├─ 选择默认领域（预设：科技/AI）
  ├─ 调整语气、立场、篇幅等参数
  └─ 确认每日出稿时段

完成 → 系统状态变为"已就绪"，开始首个日循环
```

- 引导未完成前，Dashboard 展示"系统未就绪"阻塞状态
- 支持中途退出，下次打开继续引导

**Wizard 完成后体验（"就绪后的等待期"）：**
- 系统展示"已就绪"状态 + 到下一时段开始时间的倒计时（如距离 09:00 Scout 还有 4 小时）
- Dashboard 展示"系统结构概览"简化架构图（5 个 Agent + 3 个标准）
- 引导进一步配置：写作风格精调、信息源开关、通知偏好
- 提供"立刻测试选题"按钮：手动触发一次 Scout（写 queue/actions/test_scout.json），让你立刻看到系统在运转，而非等待 4 小时首轮触发

---

## 七、平台分发矩阵

| 平台 | 分发方式 | 实现方案 | 当前状态 |
|------|---------|---------|---------|
| **微信公众号** | API 直连 | WeChat Official Account API（baoyu-post-to-wechat） | ✅ 第一阶段 |
| **小红书** | AiToEarn MCP | 通过 AiToEarn 分发通道 | ✅ 第一阶段 |
| **抖音** | AiToEarn MCP | 通过 AiToEarn 分发通道 | ✅ 第一阶段 |
| **视频号** | AiToEarn MCP | 通过 AiToEarn 分发通道 | ✅ 第一阶段 |
| **头条号** | Playwright 自动化 | 模拟浏览器操作推草稿箱 | ✅ 第一阶段 |
| **百家号** | 同步分发 | 复用公众号标准内容 | ✅ 第一阶段 |
| **知乎** | 暂缓 | — | ⏸️ 暂缓 |
| **快手** | AiToEarn MCP / 抖音复用 | 第二阶段 | ⏸️ 第二阶段 |
| **B站** | 抖音复用 | 第二阶段 | ⏸️ 第二阶段 |

---

## 八、知识库设计

### 8.1 五库结构

```
kb/                         ← Wiki 知识库根目录
├── topics/                 ← 选题库（Scout 自动写入）
│   ├── 2026-05-25-deepseek-r2.md
│   └── ...
├── viral/                  ← 爆款库（Feedback 自动写入）
│   ├── title-patterns.md
│   ├── hit-keywords.md
│   └── 2026-05/
│       └── top-articles.md
├── history/                ← 历史库（Publisher 写入已发布文章）
│   ├── 2026-05/
│   │   ├── 2026-05-25-morning.md
│   │   └── 2026-05-25-afternoon.md
│   └── ...
├── strategy/               ← 策略库（Feedback 分析沉淀）
│   ├── direction-performance.md
│   ├── writing-tips.md
│   └── program.md
├── materials/              ← 素材库（你手动收藏）
│   ├── AI-工具对比.md
│   ├── [[引用：某篇好文章]]
│   └── ...
└── INDEX.md                ← 自动维护的索引文件
```

### 8.2 存储方案

| 数据用途 | 存储形式 | 说明 |
|---------|---------|------|
| **Agent 通信** | JSON 文件系统（queue/） | 零依赖，Agent 直接读写 |
| **知识沉淀** | Markdown + wikilink（kb/） | Obsidian 可直接打开/编辑，Hermes /llm-wiki 可搜索 |
| **分析数据** | SQLite（data/analytics.db） | Dashboard 查询，趋势分析 |

### 8.3 知识库搜索实现方案

知识库搜索需要覆盖两个场景：Agent 写作时引用素材（Scout/Writer）和 Dashboard 知识库 Tab 手动检索。

**搜索分层方案：**

| 场景 | 实施阶段 | 方案 |
|------|---------|------|
| Agent 写作引用素材 | Phase 1 | Hermes `/llm-wiki` 原生搜索（简单关键词匹配） |
| Dashboard 知识库检索 | Phase 2 | 自建 SQLite FTS5 + `jieba` 中文分词全文索引 |
| Agent 升级搜索 | Phase 3 | 如果 Hermes 原生搜索效果不理想，Agent 改为调用 FastAPI 搜索 API |

**自建搜索索引方案（Phase 2 实现）：**
- 在 Dashboard 后端启动时（或定时），扫描 `kb/` 目录建立 SQLite FTS5 索引
- 使用 Python `jieba` 分词库处理中文内容，建立倒排索引
- 支持：关键词搜索、短语搜索、按库过滤（topics/viral/history/strategy/materials）
- 增量更新：检测文件修改时间，只重新索引变更的文件
- Dashboard 搜索 API 返回匹配片段 + 文件路径 + 最后修改时间

**Hermes /llm-wiki 限制：**
- Agent 侧的 /llm-wiki 搜索能力取决于 Hermes 实现，可能不支持中文分词或语义搜索
- 如果 `/llm-wiki` 仅做精确关键词匹配，"AI"将无法匹配到"人工智能"
- 此限制已在风险矩阵中记录，Phase 3 可升级为 Agent → FastAPI API 调用

### 8.4 配图文件的存储与生命周期

图片文件是系统中增长最快的资产，需要明确存储和清理策略。

**存储路径：**
```
queue/images/
├── {timestamp}-{type}-worker1/     ← 运行时临时配图（Worker 1 产出）
│   ├── cover.png
│   ├── img-01.png
│   └── ...
├── {timestamp}-{type}-worker2/     ← Worker 2 产出
└── ...
```

**生命周期：**

| 阶段 | 操作 | 清理条件 |
|------|------|---------|
| 运行中 | Worker 写入 queue/images/{session}/ | Agent 运行时占用 |
| 审批通过 | 图片随文章一起存档到 kb/history/{date}/images/ | 长期保留 |
| 审批驳回 | 保留 7 天，等待手动补发或重写 | 7 天后 cron 清理 |
| 超时跳过 | 保留 7 天，可在 Dashboard 手动触发发表 | 7 天后 cron 清理 |
| 已发布归档 | 图片在 kb/history/ 中长期保留 | 保留决策由用户决定 |

**清理脚本：** `scripts/cleanup_images.py`，每天凌晨由系统 cron 执行：
- 扫描 `queue/images/` 中所有文件
- 删除修改时间超过 3 天且其 session 对应的文章不在"待审"状态的文件
- 输出清理日志

### 8.5 Hermes /llm-wiki 集成（待 PoC 验证）

> ⚠️ **上述操作在 Hermes 文档中有描述，但实际支持程度需在 Phase 0 通过 PoC 验证**（安装 Hermes 后编写一个最小 Skill 调用保存/搜索操作）。如 `/llm-wiki` 不支持中文语义搜索，Agent 侧搜索将在 Phase 3 改为调用 FastAPI 搜索 API（见 8.3 节）。

---

## 九、配置系统

### 9.1 出稿时间配置

```
出稿时段：
  - 时段1: 11:00（自动推算：Scout 09:00 → 确认 09:30 → Writer 09:30 → 审批 10:45）
  - 时段2: 16:30（自动推算：Scout 14:00 → 确认 14:30 → Writer 14:30 → 审批 16:15）

每日篇数：2
```

配置可调，修改出稿时间后自动重新计算所有 Agent 偏移时间。

**配置变更生效机制：**
- **写作风格、质量门阈值、信息源开关** → Writer 从 `config/writing_styles.json` 读取，修改即时生效，无需重启
- **出稿时间** → 影响 Hermes cron schedule。修改时 Dashboard 更新 `config/schedule.json` 并重启 Hermes gateway
- **重启提示：** "修改将在下一时段生效，当前时段不受影响"
- **技术实现：** Hermes 的 cron 配置是 yaml 硬编码。修改时间→后端重新计算偏移量→update Hermes config.yaml → `hermes gateway restart`
- **风险：** `hermes gateway restart` 可能导致正在运行的任务中断。兜底：当前时段完成后立即重启，确保不影响执行中的 Worker
- **重启安全检测：** Dashboard 在重启前读取 `queue/status/*.json` 确认所有 Agent 状态为 `completed` 或 `idle`。如存在 `running` 状态的 Agent，则推迟重启并每小时再次检测
- **重启期间 action 文件保护：** 重启过程（约 5-10 秒）中的 action 文件写入不受影响——文件写入磁盘后，进程重启后后台扫描线程会继续处理。极少数情况下 action 文件的处理会延迟最多 60 秒

**配置双版本预览机制：**
- 配置页面显示当前生效值（今日使用）和待生效值（明日起或下一时段起）
- 例如出稿时间："当前：11:00（今日使用）" / "待生效：14:00（明日起）"
- Pipeline Tab 中的时间线标注"今日按旧时间运行"徽章
- 写作风格修改即时生效，不存在双版本问题（Agent 下次启动时读取最新值）

### 9.2 写作风格预设

```
风格预设：
├── 语气：[口语化 / 正式专业 / 轻松幽默 / 犀利批判]
├── 立场：[强烈观点 / 客观中立 / 第一人称经验]
├── 篇幅：[深度长文(2000-3000字) / 标准(1000-1500) / 短平快(300-800)]
├── 人称：[第一人称(我) / 第二人称(你) / 第三人称(读者)]
├── 句式：[短句为主 / 长短结合 / 排比修辞]
└── 专业度：[小白友好 / 行业入门 / 深度技术]

平台→风格映射：
├── 公众号标准 → 默认风格（口语化·强烈观点·深度长文·第一人称）
├── 小红书标准 → 口语化·第一人称·短平快·轻松
└── 抖音标准 → 口语化·强烈观点·短平快·急切

**风格参数 → LLM Prompt 的映射方式（模板拼接）：**

系统将各维度选项拼接为 Writer Agent 的 System Prompt。例如：
```
你是一位内容创作者。请使用口语化的表达方式，就像在和读者面对面聊天。
以强烈观点为立场，明确表达态度和结论。
篇幅控制在 2000-3000 字左右。
使用第一人称"我"来写作。
句式以短句为主，保持阅读节奏感。
专业度设为小白友好，避免专业术语，需要解释每个概念。
```

每个维度选项对应一段固定的 prompt 片段，拼接后形成完整的 System Prompt。配置界面可展示"当前风格生成的 Prompt 预览"：
```python
# 伪代码，非生产实现
parts = [
    STYLE_TONE[style["语气"]],
    STYLE_STANCE[style["立场"]],
    STYLE_LENGTH[style["篇幅"]],
    STYLE_PERSON[style["人称"]],
    STYLE_SENTENCE[style["句式"]],
    STYLE_EXPERTISE[style["专业度"]],
]
system_prompt = "你是一位内容创作者。" + " ".join(parts)
```
配置界面新维度或修改选项后，prompt 预览区实时刷新。
```

### 9.3 质量门阈值

| 阈值 | 默认值 | 可调范围 |
|------|--------|---------|
| AI腔审校及格线 | 70分 | 60-90 |
| 批评修订及格线 | 70分 | 60-90 |
| 最大重写轮数 | 3轮 | 1-5 |
| 选题评分淘汰线 | 55分 | 40-80 |

### 9.4 信息源配置

```
信息源开关：
├── 微博热搜（china-hot-mcp） | 开/关
├── 知乎热榜（china-hot-mcp） | 开/关
├── B站热门（china-hot-mcp） | 开/关
├── 百度热搜（china-hot-mcp） | 开/关
├── 抖音热点（china-hot-mcp） | 开/关
├── 头条热榜（china-hot-mcp） | 开/关
├── 36氪热榜（china-hot-mcp） | 开/关
├── Twitter/X（x-tweet-fetcher） | 开/关
├── RSS订阅 | 开/关（URL列表可配置）
├── GitHub Trending | 开/关
└── Web搜索（Firecrawl） | 开/关
```

### 9.5 模型 Fallback 链

AI 模型调用失败时需要有序切换。在配置面板中可拖拽排序：

```
模型优先级：
  1. [首选] Claude Sonnet 4 (Anthropic)
  2. [Fallback 1] GPT-4o (OpenAI)
  3. [Fallback 2] DeepSeek V3
  4. [Fallback 3] Ollama 本地模型 (零成本)
```

**Fallback 触发条件：**
- LLM API 返回 5xx 错误
- LLM API 超时（默认 60 秒超时）
- LLM 返回空内容或格式错误

**Fallback 可视化：**
- Pipeline Tab 上当前使用的模型名显示在 Agent 旁边
- 如果 fallback 启动，模型名变为橙色
- Dashboard 记录 fallback 事件日志（原因、时间、fallback 层级）

**配置文件存储：**
```json
// config/model_fallback.json
{
  "chain": [
    {"provider": "anthropic", "model": "claude-sonnet-4", "label": "Claude Sonnet 4"},
    {"provider": "openai", "model": "gpt-4o", "label": "GPT-4o"},
    {"provider": "deepseek", "model": "deepseek-v3", "label": "DeepSeek V3"}
  ],
  "timeout_seconds": 60,
  "retry_on_error": true,
  "max_retries": 2
}
```

---

## 十、信息源获取方案

### 10.1 国内热榜

通过 `china-hot-mcp`（EA-Studio-SHARK 出品，pip 安装）接入。
- Python 原生 MCP Server，Hermes 原生 MCP 客户端可直接对接
- 覆盖平台：微博、知乎、B站、百度、抖音、头条、36氪
- 双数据源：直连平台 API + 备用聚合源
- 5 分钟 TTL 缓存防限流

### 10.2 Twitter/X

通过 `x-tweet-fetcher`（ythx-101 出品）接入。
- 零配置：无需 API Key、登录、Cookie
- 双后端：Nitter 解析 + Playwright 浏览器自动 fallback
- 支持：单推文、时间线、搜索、Lists、X Articles
- 代理支持：你的代理可用，Nitter 需自建实例
- 输出 JSON，Agent 友好

### 10.3 RSS 订阅

feedparser 解析标准 RSS 2.0/Atom，最稳定的协议。

### 10.4 Web 搜索

Hermes 内置 Firecrawl 作为默认 Web 后端，月 500 credits 免费。

### 10.5 微信文章

通过 wewe-rss 将公众号转为 RSS 源。

---

## 十一、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| **平台 API 变更** | 分发失败 | AiToEarn 维护适配+Playwright 兜底+queue/failed/ 告警 |
| **AI 内容平台限流** | 阅读量低 | 人工审批确保质量+AI腔审校降AI味+标题优化 |
| **账号封禁** | 无法发布 | 草稿箱中转不直发+控制自动化频率+多平台分散 |
| **Nitter 不稳定** | 选题遗漏 | x-tweet-fetcher 双后端自动 fallback |
| **AiToEarn 服务变更** | 分发通路中断 | 初期用 SaaS 版快速启动；后续可自部署 Docker 版 |
| **AiToEarn 无数据回收接口** | 反馈飞轮 Phase 3 前不可用 | 替代方案：Playwright 浏览器自动化抓数据 |
| **LLM 质量波动** | 文章质量不稳定 | 70分批评修订门+最多3轮重写 |
| **数据回收不全** | 反馈飞轮失效 | 可手动补录数据到 analytics.tsv |
| **Hermes 不支持飞书通知** | 审批流程需重新设计 | 方案A：自建 feishu-notify Skill；方案B：Dashboard 后端集成飞书 SDK |
| **Hermes 不支持飞书交互回调** | 飞书卡片只读不可操作 | 飞书卡片仅做通知，全部操作在 Dashboard |
| **Hermes cron 依赖进程存活** | cron 宕机导致全线停摆 | 系统级 watchdog（crontab 每分钟检查 + 重启 + 飞书告警） |
| **Agent 异常中止不写状态** | Dashboard 永久显示"进行中" | 超时标记机制兜底（预设阈值 → 标记异常） |
| **图片生成 API 超时/失败** | Writer 管线卡死 | 三级降级策略（HTML模板→baoyu→不带图），不阻塞主线 |
| **AI 模型价格波动** | 运营成本不可控 | 预留模型选择，开放权重数据可用时切换本地 Ollama |
| **不同内容标准时间冲突** | 时间线塞不下串行 Writer | 3 个 Worker 并行运行，Router/Aggregator 模式 |
| **文件写入非原子性** | Dashboard 读到不完整的 action/status 文件 | 所有写入遵循 .tmp + rename 原子协议 |
| **Playwright 登录 Cookie 过期** | 头条号分发失效 | storageState 持久化 + 飞书告警需重新登录 + 降级为手动分发 |
| **内容同质化** | 读者疲劳，阅读量下降 | 近期话题屏蔽硬约束 + 方向多样性约束 + 词云可视化 |
| **SQLite 多 worker 写入冲突** | 数据库写入错序或卡死 | FastAPI 单 worker + WAL 模式，大批量数据走文件 |
| **知识库搜索不支持中文分词** | Agent 搜不到相关素材 | Phase 2 自建 SQLite FTS5 + jieba 索引 |
| **飞书回调签名未校验** | 审批操作可被伪造 | 使用飞书 App Secret 验证回调签名 |
| **LLM API 费用超出预期** | 月账单过高 | 月成本上限机制（默认 $15），达上限自动停管线 |
| **Writer 并行实现不兼容 Hermes** | 无法在 Hermes 框架内实现并行 | 方案 B：外部 Python 脚本 + asyncio.gather 规避框架限制 |
| **配图 HTML 无法直接用于平台** | 平台草稿箱接口接受图片文件而非 HTML | 复用 Playwright Chromium 截图转 PNG |
| **跳过内容永久丢失** | 用户意愿的内容未被发表 | 跳过的文章进入历史记录，可在 Dashboard 手动触发发表 |

---

## 十二、实施路线图

### Phase 0 — 基础设施与 PoC 验证（2-3天）

- [ ] **Hermes Agent PoC：** 安装 Hermes，验证以下能力——
  - [ ] `hermes gateway` 命令可用
  - [ ] 开发一个最小 Skill（Hello World），验证 Skill → Python 代码集成模式
  - [ ] 配置 MCP 客户端，验证连接 china-hot-mcp
  - [ ] 验证 cron 调度（固定时间点触发）
  - [ ] 验证 `/llm-wiki` 的搜索能力（是否支持中文？是关键词还是语义？）
  - [ ] 验证 `deliver_to` 是否支持飞书
  - [ ] 验证 baoyu skills 的安装和加载方式
  - [ ] **以上任一项不通过需要重新评估架构依赖**
- [ ] 调研 AiToEarn MCP 工具集（确认数据回收接口可用性）
- [ ] systemd/crontab watchdog 脚本
- [ ] 项目目录结构初始化（skills/ dashboard/ scripts/ config/ data/ queue/ kb/）
- [ ] 建立文件写入原子性约定（.tmp + rename）
- [ ] 配置 AiToEarn MCP / china-hot-mcp / x-tweet-fetcher / Firecrawl

### Phase 1 — 核心管线（预计2周）

- [ ] Scout Agent — 选题采集 + 评分 + 内容同质化防御 + 状态文件
- [ ] Writer Agent — 7阶段管线基础版（单 Worker：公众号标准）
- [ ] 并行架构设计验证：asyncio.gather 原型 + 独立 Worker 子目录隔离
- [ ] 审批流程 — 飞书消息通知（基于 Phase 0 验证结果选择方案）
- [ ] 驳回重写循环（最多3轮）+ 版本 diff 数据准备（difflib）
- [ ] Publisher Agent（公众号 WeChat API + AiToEarn MCP — 小红书/抖音/视频号）
- [ ] 知识库初始化 — kb/ 目录结构 + 5库骨架 + Knowledge Agent 归档操作（移动 queue/review/ → kb/history/）
- [ ] Agent 状态报告机制（queue/status/）
- [ ] 日历配置：运行日勾选
- [ ] cron 调度 — 上午篇管线跑通
- [ ] queue/actions/ 扫描进程（Dashboard 后台线程或 system cron）
- [ ] 基础异常处理（重试、超时跳过、飞书告警）
- [ ] 跳过内容生命周期：进入历史记录可手动触发

### Phase 2 — Dashboard Web 服务（预计1.5周）

- [ ] FastAPI 后端初始化 + SQLite 表结构（WAL 模式 + 单 worker）
- [ ] Vue 3 前端骨架 + 5Tab 布局
- [ ] Pipeline Tab — 实时管线状态（读 queue/status/ + 阶段节点进度图 + 超时标记）
- [ ] 审批队列 Tab — 3版本横向Tab预览 + 版本diff对比视图 + 评分趋势线
- [ ] 审批通知机制：角标(3) + toast 弹窗
- [ ] 选题推荐 Tab — Scout 候选展示 + 确认操作
- [ ] 数据 Tab — 基础图表 + 成本消耗趋势（从 SQLite token_usage 读取）+ 主题分布词云 + 空状态引导
- [ ] 知识库 Tab — 5库切换 + SQLite FTS5 + jieba 中文全文搜索
- [ ] Dashboard 与 Agent 文件触发集成（queue/actions/ 协议 + 原子写入 + 扫描进程）
- [ ] 配置管理界面（含 Onboarding Wizard + 配置双版本预览 + 写作风格预设 UI + 月成本上限设置 + 通知时段设置）
- [ ] 平台连接状态面板（6.5 节）+ health check（AiToEarn/WeChat API 连接检测）
- [ ] 图片存储目录结构 + 7天清理脚本

### Phase 3 — 增强完善（预计1.5周+）

- [ ] Publisher Agent — 头条号 Playwright 分发 + session 管理（Cookie 持久化 + 过期告警）
- [ ] 配图 HTML → PNG 截图管线（复用 Playwright Chromium）
- [ ] Feedback Agent — 数据回收（根据 Phase 0 调研确认接口写入 SQLite） + 爆款库 / 策略库更新 + 关键词提取
- [ ] 写作风格预设进阶管理 + 风格 prompt 预览 UI
- [ ] 超时兜底 + 异常告警完善
- [ ] 临时选题加入管线（manual/ 入口—Dashboard 上粘贴 URL 或直接写 Markdown 到 queue/pending/）
- [ ] Writer 并行 Worker 架构（Router + 3 Workers + Aggregator）
- [ ] AI 模型 fallback 链管理界面（9.5 节模型优先级拖拽排序）
- [ ] Knowledge Agent 增强：关键词提取 + 摘要生成 + INDEX.md 更新
- [ ] 领域切换的"项目化"管理支持 + 评分模型权重配置
- [ ] 飞书回调签名验证（仅当 Dashboard 公网部署时）

### Phase 4 — 视频阶段

- [ ] 抖音标准内容产出管线
- [ ] AiToEarn 视频分发（抖音+视频号+快手+B站）
- [ ] 图文转视频流程

---

## 十三、基础设施与运维

### 13.1 部署架构（详见 2.4）

- 单机部署：Hermes Gateway + FastAPI Dashboard + Playwright = 3 个进程
- 共享文件系统：项目根目录（queue/ kb/ data/ config/）
- 系统 crontab 仅用于 watchdog 脚本（每分钟）

### 13.2 watchdog 脚本（`scripts/watchdog.sh`）

```bash
#!/bin/bash
# 每分钟由系统 crontab 调用
# 检查 Hermes gateway 进程
if ! pgrep -f "hermes gateway"; then
  hermes gateway start
  curl -X POST -H "Content-Type: application/json" \
    -d '{"msg":"Hermes gateway 已自动重启"}' \
    https://open.feishu.cn/open-apis/bot/v2/hook/xxx
fi

# 检查 FastAPI 进程
if ! pgrep -f "uvicorn main:app"; then
  cd /path/to/project && nohup uvicorn main:app --port 8710 &
fi

# 检查 queue/ 积压
if [ $(ls queue/actions/ 2>/dev/null | wc -l) -gt 50 ]; then
  # queue/actions/ 积压超过 50 个未处理 → 告警
fi
```

### 13.3 日志

- Hermes 日志：`~/.hermes/logs/`
- Dashboard 日志：`logs/dashboard.log`
- Agent 状态文件：`queue/status/*.json`（Dashboard 管线监控来源）
- 分发失败记录：`queue/failed/*.json`

### 13.4 数据备份

- SQLite 数据库：`data/analytics.db`（定 cron 自动备份到空 role备份目录）
- 知识库 kb/：本身就是 Markdown 文件，git 或 Obsidian 同步即可
- queue/ 目录：不需要备份（运行态数据，重启后重新生成）

---

## 附录

### A. 参考项目

| 项目 | 关键借鉴 |
|------|---------|
| 一人AI马特啦·文章1 | 5-Agent 架构、文件系统队列、评分模型、质量门 |
| 一人AI马特啦·文章2 | 三栏 Dashboard、双层评分、知识库、5个 Prompt |
| content-workflow（46⭐） | /pulse→/review→/generate-content→/approve 管线 |
| content-pipeline（OrangeViolin） | 公众号排版+配图+发布、小红书轮播图、baoyu 技能集成 |
| baoyu-skills（JimLiu） | infographic、article-illustrator、post-to-wechat 全套技能 |
| china-hot-mcp | MCP 化国内热榜 API，Python 原生，Hermes 可直接集成 |
| x-tweet-fetcher | 零配置 Twitter 采集，Nitter+Playwright 双后端 |
| AiToEarn（12K⭐） | 多平台 OAuth 分发、MIT 开源、MCP 服务 |
| DailyHotApi | 40+平台热榜聚合 API，稳定运行中 |

### B. 术语表

| 术语 | 说明 |
|------|------|
| Agent | 独立执行特定任务的 AI 单元（Scout/Writer/Publisher/Feedback/Knowledge） |
| Orchestrator | 总编，通过 Hermes Cron 编排 Agent 执行时序 |
| 质量门 | 文章必须达到的分数阈值，未通过则打回重写 |
| 批评修订循环 | Writer 的第4阶段，评委打分+重写，循环至达标或超限 |
| 反馈飞轮 | Feedback Agent 回收数据→分析→反哺选题权重 |
| 小红书标准 | 300-800字图文笔记+6-9张轮播图 |
| 公众号标准 | 2000-3000字深度长文+品牌HTML排版 |
| 抖音标准 | 15-60秒短视频脚本 |
| queue/ | Agent 之间的消息队列，JSON 文件系统 |
| kb/ | 知识库根目录，Markdown + wikilink 格式 |
| MCP | Model Context Protocol，Hermes 与外部服务（AiToEarn）的通信协议 |

### C. 审核发现记录

#### 第一轮审核（30 轮 — PM/UX/DEV 三方交叉审查）

| # | 发现 | 影响 | 状态 |
|---|------|------|------|
| 1 | 缺少成功指标和成本估算 | 无法量化 ROI | ✅ 新增 1.4 节 |
| 2 | Hermes ↔ Dashboard 集成未定义 | 无法互操作 | ✅ 新增 2.6 节 + queue/actions/ 协议 |
| 3 | Writer 串行时间线不够用 | 上午时段 60 分钟塞不下 | ✅ 新增并行架构（3.2 节） |
| 4 | 缺少 Agent 状态报告 | Dashboard 无法监控管线 | ✅ 新增 2.5 节 + queue/status/ 协议 |
| 5 | 飞书集成依赖未验证 | 核心审批流程不可行 | ✅ 新增 5.5 节（备选方案 B） |
| 6 | 部署模型不明确 | 无法规划环境搭建 | ✅ 新增 2.4 部署模型 |
| 7 | 空状态/错误状态未设计 | 用户首次体验差 | ✅ 新增各 Tab 空状态描述 |
| 8 | 缺少 Onboarding 流程 | 新用户启动困惑 | ✅ 新增 6.6 节 |
| 9 | AiToEarn 数据回收能力不确定 | Feedback Agent 无法实现 | ✅ 更新 3.4 节风险提示 |
| 10 | 成本估算缺失 | 无法评估 ROI | ✅ 新增 1.4 节成本估算表 |

#### 第二轮审核（20 轮 — 深水区细节审查）

| # | 发现 | 影响 | 状态 |
|---|------|------|------|
| 1 | 文件写入非原子性 | 进程读到不完整 JSON | ✅ 新增 .tmp + rename 协议（2.6 节） |
| 2 | 周末/节假日无日历策略 | 运行日不可控 | ✅ 新增日历配置（5.1 节） |
| 3 | Writer 进度缺少阶段感 | 用户焦虑系统卡死 | ✅ 新增阶段节点进度图（6.2 节） |
| 4 | Writer 并行实现方案未选择 | 开发方向不明确 | ✅ 选定方案 B — asyncio.gather（3.2 节） |
| 5 | 跳过内容无生命周期 | 内容永久丢失 | ✅ 跳过 → 历史记录，可手动触发（5.4 节） |
| 6 | 驳回重写无版本 diff | 用户无法判断改进 | ✅ 新增 difflib 版本对比（6.3 节） |
| 7 | Playwright session 管理复杂 | 头条号无法无人值守 | ✅ 新增 Cookie 持久化 + 过期告警（3.3 节） |
| 8 | HTML 配图截图方案未定义 | 配图线不通 | ✅ 选定复用 Playwright 截图（3.2 节） |
| 9 | SQLite 多 worker 冲突 | 数据库写入异常 | ✅ 单 worker + WAL 模式（2.2 节） |
| 10 | 内容同质化风险 | 阅读量下降 | ✅ 新增近期话题屏蔽（3.1 节） |
| 11 | 知识库搜索不支持中文分词 | 搜不到素材 | ✅ 新增 SQLite FTS5 + jieba（8.3 节） |
| 12 | 图片文件无存储生命周期 | 文件数无限膨胀 | ✅ 新增 8.4 节存储策略 + 清理脚本 |
| 13 | 缺少成本控制上限 | 费用可能失控 | ✅ 新增月预算机制（1.4 + 9.4 节） |
| 14 | 飞书回调未考虑签名校验 | 审批操作可伪造 | ✅ 新增安全说明（5.5 节） |
| 15 | 通知无免打扰机制 | 夜间被打扰 | ✅ 新增通知时段配置（5.1 节） |

#### 第四轮审核（开发者独立技术审核 — 全栈工程师视角，聚焦工程依赖与实现盲区）

| # | 发现 | 级别 | 影响 | 状态 |
|---|------|------|------|------|
| 1 | Hermes 本体未定义（安装命令、能力边界、Skill 开发方式均无说明） | 🔴 致命 | 如果 Hermes 不支持预期的能力，架构需重新设计 | ✅ 新增 2.2 节注 + Phase 0 PoC CheckList |
| 2 | queue/actions/ 扫描机制与 Hermes cron 不兼容 | 🔴 致命 | Hermes cron 是固定时间点触发，不能"每 30 秒扫描目录" | ✅ 修正为独立后台进程（2.6 节） |
| 3 | 项目目录结构和代码组织未定义 | 🔴 阻塞 | 开发者无法确定 skills/ dashboard/ 的组织方式 | ✅ 新增 2.7 节完整目录结构 |
| 4 | 评分模型参数无值范围/类型/来源定义 | 🟡 高 | Scout 无法实施评分 | ✅ 新增参数规格表 + source_weight 初始权重表（3.1 节） |
| 5 | Token 消耗追踪无工程路径 | 🟡 高 | 月成本上限机制缺失实现基础 | ✅ 说明从 LLM API 响应提取 + Aggregator 聚合（1.4 节注） |
| 6 | data/analytics.tsv 存在并发隐患 | 🟡 高 | Dashboard 读到不完整 TSV 行 | ✅ 改为写入 SQLite（3.4 节） |
| 7 | hermes gateway restart 安全边界不清 | 🟡 高 | 重启时正在执行的 Writer 可能中断 | ✅ 补充状态检测 + action 文件保护说明（9.1 节） |
| 8 | Hermes Skill 开发路径未定义 | 🟡 高 | Phase 1 无法开始开发 Agent | ✅ Phase 0 PoC 加入"最小 Skill"验证项 |
| 9 | Phase 边界不一致（头条号 Phase 3 vs 矩阵表标"第一阶段"） | 🔵 中 | 开发排期混乱 | ✅ 对齐：Publisher 基础在 Phase 1，头条号 Playwright 在 Phase 3 |
| 10 | Knowledge Agent 具体职责不清 | 🔵 中 | 开发者不知道应该实现什么 | ✅ 明确 Phase 1 仅归档，Phase 3+ 分析（3.5 节） |

| # | 发现 | 影响 | 状态 |
|---|------|------|------|
| 1 | 北极星指标数据来源未明确 | 无法判断 Phase 1-2 该指标是否可用 | ✅ 补充数据来源依赖说明（1.4 节） |
| 2 | "3 个标准版本"语义歧义 | 开发者和用户对"版本"的理解可能不同 | ✅ 明确为"独立写作而非模板适配"（3.2 节） |
| 3 | queue/actions/ 文件 JSON schema 缺失 | Hermes cron 无法解析 action 文件内容 | ✅ 补充完整 schema + 扫描逻辑（2.6 节） |
| 4 | 飞书卡片回调与 Dashboard localhost 矛盾 | 飞书按钮交互设计不可实现 | ✅ 决策：飞书仅通知，所有操作在 Dashboard（5.2/5.5 节） |
| 5 | SQLite 表结构未定义 | 后端开发无基准设计 | ✅ 补充 5 张核心表定义（6.1 节） |
| 6 | 写作风格预设→prompt 映射规则未说明 | 配置界面无法实现"生成效果预览" | ✅ 明确为模板拼接 + 伪代码（9.2 节） |
| 7 | AI腔审校"100+规则"来源和工作量未定义 | 开发量被低估 | ✅ 说明 Phase 1 先实现 30 条，其余运行中积累（3.2 节） |
| 8 | Scout 评分模型冷启动参数策略未说明 | 前 2 周选题倾向被扭曲 | ✅ 补充冷启动期参数替代策略（3.1 节） |
| 9 | 版本级审批操作隔离逻辑未定义 | 部分通过时数据状态冲突 | ✅ 补充持久化和隔离规则（6.3 节） |
| 10 | 并行 Worker 状态文件协议未细化 | Dashboard 无法按 Worker 展示进度 | ✅ 补充 worker 文件命名 + Router 聚合格式（2.5 节） |
| 11 | 成本估算表配图费用假设未说明 | 用户按 $0.12 预期实际花了 $0.50 | ✅ 补充假设注释 + baoyu 场景价格区间（1.4 节） |
| 12 | 日成本未包含批评修订跑满 3 轮场景 | 成本范围被低估 | ✅ 补充波动区间 $7-25/月（1.4 节） |

---

> 文档结束。版本 v1.3。如有修订需求，请更新版本号并记录变更日志。
