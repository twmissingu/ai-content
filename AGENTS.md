# AGENTS.md

仓库：`ai-content` — AI 内容生产系统「稿定」的源代码与规格文档库。
状态：**v0.7.0**（架构重构 + 提示词优化 + 前端 UX 升级 + 测试补全 + 安全加固）。
版本：[v0.7.0](CHANGELOG.md) — 2026-05-28

---

## 一、遵守的规则

优先级：**禁令规则 > 其他规则**。哪个任务类型，激活哪个模块，不相关的不看。

### 禁令（违反即问题）

1. **先读再改**。任何编辑操作前必须读取文件当前内容。改文章前先复述原文要点，经确认后再动笔。
2. **不添加未要求的内容**。画蛇添足增加筛选成本。只给用户问的东西。
3. **不为不可能发生的情况做预防性处理**。三次重复好过一个"通用框架"。
4. **不编造不预测**。子任务结果未知就说"不知道，需进一步检查"。
5. **不把理解工作外包**。自己消化信息后再派子任务，给足上下文（做什么、为什么、排除了什么）。
6. **不扩大授权范围**。一次授权只对当次、当个对象有效。
7. **不检查就说"没问题"**。没读源文件就没有发言权。

### 汇报规范

- 没做好就直说哪里没做好、卡在哪里。不用"可能""或许"软化。
- 做好了不额外免责。不加"但可能还有其他问题"这类废话。
- 准确报告，不是防御性报告。

### 沟通格式

- 能一句话不说三句。先说结论，再说理由。
- 不用冒号连接开头。结尾不加"希望以上对你有帮助"这类总结。

### 子任务描述格式

每条必须包含：做什么 + 为什么 + 排除了什么。格式："做X，因为需要Y，不包含Z。"

### 自检机制

重要输出前执行反驳检查：有证据吗？有遗漏的边界吗？挑剔用户会从哪里挑毛病？发现问题直接修正，不暴露给用户来指。

### 信息加载策略

不一次性倒出所有工具说明。先告知工具名称和用途，用户决定用再给详情。

### 工具使用限制

- 调用工具时说明理由。
- 不连续调用超过 3 个工具而不中途汇报进展。
- 工具返回异常时立即停止并报告，不尝试"自动修复"。

### 安全红线（违反即事故）

1. **禁止对外暴露 API Key、密钥、Token 等敏感信息**。输出时自动脱敏处理，如需展示只显示前缀（如 `ak_u***D5G`）。
2. **绝对禁止操作各平台钱包、余额、提现、转账等资金相关功能**。任何涉及金钱的操作必须由用户人工完成。
3. **绝对禁止自动申请贷款、信用支付、绑定支付方式等金融操作**。
4. **高危操作必须两次人工确认**：涉及发布内容、删除数据、修改关键配置等不可逆操作时，执行前先请求确认，用户确认后再次提醒确认风险，再执行。

---

## 二、仓库结构

```
README.md                            项目介绍（英文）
README_zh.md                         项目介绍（中文）
AGENTS.md                            AI Agent 行为规范
CHANGELOG.md                         版本变更记录
LICENSE                              MIT 许可证
docs/
  product/
    PRD.md                           产品规格文档（唯一完整方案）
    development-plan.md              开发计划书
  manual/
    AiToEarn配置与自动化操作指引.md    AiToEarn 接入配置（MCP + API）
    用户使用说明书.md                  用户手册（面向运营人员）
    账号注册指引.md                    社交平台账号注册指南

skills/                            Agent 实现代码（Python）
  ├── __init__.py
  ├── common.py                    共享工具（AgentBase, metrics, load_prompt）
  ├── scout.py                     选题 Agent
  ├── writer.py                    写手 Agent（7 阶段管线）
  ├── writer_router.py              并行 Writer 路由器
  ├── writer_xhs.py                 小红书 Worker
  ├── writer_douyin.py              抖音 Worker
  ├── publisher.py                  分发 Agent
  ├── publisher_toutiao.py          头条号 Playwright 分发
  ├── feedback.py                   数据反馈 Agent
  ├── knowledge.py                  知识沉淀 Agent
  ├── screenshot.py                 HTML→PNG 截图工具
  ├── action.py                     action 文件协议
  ├── llm.py                       LLM 调用工具
  └── metrics.py                   性能指标收集

dashboard/                         Web Dashboard
  ├── backend/
  │   ├── main.py                  FastAPI 入口（中间件 + 路由挂载，版本 0.7.0）
  │   ├── routes/                  路由模块
  │   │   ├── pipeline.py          管线状态、触发
  │   │   ├── approval.py          审批队列和操作
  │   │   ├── topics.py            选题候选
  │   │   ├── data.py              数据分析
  │   │   ├── kb.py                知识库搜索
  │   │   ├── config.py            系统配置（含质量飞轮）
  │   │   ├── health.py            健康检查
  │   │   ├── traces.py            管线执行追踪（/api/pipeline/traces）
  │   │   └── prompts.py           提示词版本管理（/api/prompts）
  │   ├── database/                SQLite 数据层（拆分为 7 个模块）
  │   │   ├── core.py              连接管理、缓存、初始化（get_db, init_db）
  │   │   ├── sessions.py          管线会话 CRUD
  │   │   ├── versions.py          平台版本 + 审批记录 + 质量飞轮
  │   │   ├── tokens.py            Token 用量 + 预算控制
  │   │   ├── config_ops.py        配置键值存取
  │   │   ├── traces.py            执行追踪（批量查询优化）
  │   │   └── prompts.py           提示词版本管理
  │   ├── auth.py                  API Key 认证中间件（hmac.compare_digest）
  │   ├── background.py            后台任务（action 扫描、预算监控）
  │   ├── config_service.py        配置管理服务
  │   ├── ws.py                    WebSocket 实时推送（ConnectionManager）
  │   ├── feishu.py                飞书通知
  │   ├── helpers.py               共享工具函数
  │   ├── models.py                Pydantic 请求模型
  │   └── search.py                FTS5 全文搜索（trigram tokenizer）
  └── frontend/                    Vue 3 + Vite 前端（端口 5173）

config/                            运行态配置
  ├── settings.py                  所有运行时配置（路径、LLM、调度）
  ├── models.json                  模型价格配置
  ├── quality_gates.json           质量门禁阈值（proofread: 60, critique: 70, title: 75）
  ├── proofread_patterns.json      AI-slop 检测模式（23 个 regex）
  ├── prompts/                     Agent 提示词模板（24 个文件）
  │   ├── *.txt                    数据库导入的提示词（7 个，启动时自动导入）
  │   │   ├── scout_scoring.txt    Scout 评分提示词
  │   │   ├── writer_draft.txt     Writer 初稿提示词
  │   │   ├── writer_proofread.txt Writer 审校提示词
  │   │   ├── writer_critique_*.txt  批评修订（scorer + critic）
  │   │   ├── writer_title.txt     标题优化提示词
  │   │   └── feedback_strategy.txt  策略分析提示词
  │   └── *.md                     内容模板（17 个，8 类型 × 2 平台 + persona_bible）
  │       ├── persona_bible.md     统一人设圣经（所有模板引用）
  │       ├── {type}_{platform}.md 8 类型 × 2 平台 = 16 个写作模板
  │       └── types: news, opinion, insight, roundup, sharing,
  │                   tech_science, tool_update, tutorial
  ├── schedule.json                调度配置
  └── writing_styles.json          写作风格预设（8 类型 + 3 默认）

pyproject.toml                     Python 包声明（pip install -e .）
pytest.ini                         测试配置
scripts/                            运维脚本
queue/                              Agent 间通信目录（JSON 文件系统）
kb/                                 知识库（Markdown）
```

**核心文档：`docs/product/PRD.md`** — 所有决策和方案的唯一来源。开始任务前必须读取相关内容。

---

## 三、系统概览（基于 PRD）

产品名「稿定」，日循环工作流：

```
09:00 Scout 选题 → 09:30 人工确认 → 09:30-10:30 Writer 写作（3版并行）
→ 10:45 人工审批 → 11:00 分发各平台草稿箱
（14:00 重复下午场，22:00 Feedback 数据回收）
```

### 关键术语

| 术语 | 含义 |
|------|------|
| Scout | 选题 Agent，扫描热榜 + RSS + Twitter + Web 搜索 |
| Writer | 写手 Agent，7 阶段管线：抓原文→初稿→审校→批评修订→排版→标题→配图 |
| Publisher | 分发 Agent，推送到各平台草稿箱（不直接发布） |
| Feedback | 数据分析 Agent，回收阅读量数据反哺选题 |
| Knowledge | 知识沉淀 Agent，归档文章到 kb/ |
| queue/ | Agent 间通信目录（JSON 文件系统） |
| kb/ | 知识库（Markdown + wikilink） |
| Traces | 管线执行追踪，每阶段记录耗时、Token、状态 |
| WebSocket | 实时状态推送（`/ws/pipeline`），3s 轮询 + hash 变更检测 |
| 质量飞轮 | 审批数据分析 → 推荐质量门禁阈值调整 |

### 平台分发矩阵

| 平台 | 方式 | 状态 |
|------|------|------|
| 微信公众号 | WeChat API | Phase 1 |
| 小红书 | AiToEarn MCP | Phase 1 |
| 抖音 | AiToEarn MCP | Phase 1 |
| 视频号 | AiToEarn MCP | Phase 1 |
| 头条号 | Playwright 自动化 | Phase 3 |
| 百家号 | 同步公众号内容 | Phase 1 |

### 外部依赖

- `Hermes Agent` — 编排引擎（cron + Skill + MCP 客户端）
- `AiToEarn` — 多平台分发通道
- `china-hot-mcp` — 国内热榜聚合
- `x-tweet-fetcher` — Twitter 采集
- `Firecrawl` — Web 搜索
- `baoyu-skills` — 配图 + 公众号发布

### 实施阶段

| Phase | 内容 | 预估 |
|-------|------|------|
| 0 | 基础设施 PoC（Hermes 验证 + 配置） | 2-3 天 |
| 1 | 核心管线（Scout + Writer + Publisher 基础） | 2 周 |
| 2 | Web Dashboard（FastAPI + Vue 3） | 1.5 周 |
| 3 | 增强完善（Feedback + 头条号 + 并行 Writer） | 1.5 周+ |
| 4 | 视频阶段（抖音标准 + 视频分发） | — |

---

## 四、配置流程（AI Agent 快速上手）

引导用户完成配置时（包括你自己作为 Agent 首次部署），按以下步骤：

### 4.1 交互式配置（推荐）

推荐给用户执行，引导式问答完成全部配置：

```bash
bash scripts/setup.sh
```

脚本自动完成：检测 Python/Node 版本 → 引导填入 **Base URL**（必填）→ 引导填入 **API Key**（必填）→ 写入 `.env` → 创建目录 → 安装依赖 → 可选启动 Dashboard。

### 4.2 手动配置（自动化场景）

适合你自己作为 Agent 执行或 CI/CD 场景：

```bash
# 1. 安装依赖
pip install httpx uvicorn fastapi pydantic
cd dashboard/frontend && npm install && cd ../..

# 2. 设置 Base URL + API Key（两种方式任选其一）
# 方式 A：环境变量（推荐）
export LLM_BASE_URL="https://你的api地址/v1"
export XIAOMI_API_KEY="你的key"

# 方式 B：写入 .env 文件
echo 'LLM_BASE_URL="https://你的api地址/v1"' >> .env
echo 'XIAOMI_API_KEY="你的key"' >> .env

# 3. 创建运行时目录
bash scripts/init_directories.sh
```

### 4.3 配置验证

```python
# 验证 .env 自动加载
python3 -c "
from config.settings import LLM_BASE_URL, LLM_API_KEY
print(f'Base URL: {LLM_BASE_URL}')
print(f'API Key : {\"OK\" if LLM_API_KEY else \"MISSING\"}')
"
```

### 4.4 安全提醒

`scripts/setup.sh` 会读取并在终端显示 API Key 前 4 位 + 后 4 位（脱敏格式 `ak_u***D5G`）。
.env 文件和空值不会触发加载。任何情况下都不暴露完整 Key。

---

## 五、开发约束

- 所有文件编辑前必须先 `read`，不准凭记忆改。
- `docs/product/PRD.md` 中的设计方案如需修改，先引用原文位置再提改动。
- 外部服务文档优先查 `docs/manual/AiToEarn配置与自动化操作指引.md`（仓库内已有），不够再用 web search。
- 不添加仓库中不存在的文件除非用户明确要求。
- 项目使用 `pyproject.toml` 声明为 Python 包，通过 `pip install -e .` 安装后可直接 import。
- 提示词模板存放在 `config/prompts/` 目录，使用 `skills/common.py` 的 `load_prompt()` 加载。
- 提示词支持数据库版本管理（`/api/prompts` CRUD），`.txt` 文件启动时自动导入。
- AI-slop 检测模式存放在 `config/proofread_patterns.json`，支持通过 Dashboard 管理。
- 质量门禁阈值存放在 `config/quality_gates.json`，Writer 管线各阶段读取对应阈值。
- 数据库层已拆分为 `dashboard/backend/database/` 包（7 个领域模块），通过 `__init__.py` 统一导出。
- WebSocket 实时推送在 `dashboard/backend/ws.py`，前端通过 `ws://host/ws/pipeline` 接收状态变更。
