# 开发计划书 — 稿定（AI 内容生产系统）

> 基于 PRD v1.4
> **当前状态：v0.8.0（Phase 1-3 已完成，Phase 4 进行中，详见 [CHANGELOG.md](../../CHANGELOG.md)）**
> 环境状态：Hermes v0.14.0 已安装，Python 3.14.5/Node v26 就绪

---

## 一、总体路线图（已完成）

```
Phase 0 ─→ Phase 1 ─→ Phase 2 ─→ Phase 3 ─→ Phase 4
  2-3天       2周        1.5周      1.5周+      待定
```

| Phase | 内容 | 状态 |
|-------|------|------|
| 0 | 基础设施 PoC（Hermes 验证 + 目录结构 + 外部依赖） | ✅ 已完成 |
| 1 | 核心管线（Scout + Writer + Publisher 基础） | ✅ 已完成 |
| 2 | Web Dashboard（FastAPI + Vue 3，7 视图） | ✅ 已完成 |
| 3 | 增强完善（Feedback + 头条号 + 并行 Writer + 信源优化） | ✅ 已完成 |
| 4 | 视频阶段（抖音标准 + 视频分发） | 🔄 进行中 |

---

## 二、Phase 1：核心管线

### 架构概览

```
Hermes cron 触发
    ↓
Scout Agent（Python） → 选题写入 queue/pending/
    ↓ (人工确认)
Writer Agent（Python）→ 7 阶段管线 → queue/review/
    ↓ (人工审批)
Publisher Agent（Python）→ 分发到公众号 + AiToEarn 平台
    ↓
Knowledge Agent（Python）→ 归档到 kb/history/
```

### 关键决策

- Writer 直接调用 LLM API（通过 `skills/llm.py`），不依赖 Hermes 内部 API
- 批评修订的"评委 LLM"与写手 LLM 同一实例，不同 prompt
- 飞书通知由 Dashboard 后端 `feishu.py` 集成飞书 Webhook，不依赖 Hermes deliver_to

### 产出物

- `queue/review/{timestamp}-wechat.md` — 文章正文
- `queue/review/{timestamp}-wechat.meta.json` — 元数据（分数、轨迹、配图路径）
- `queue/status/writer.json` — 进度报告

---

## 三、Phase 2：Web Dashboard

### 架构

```
浏览器（Vue 3） ←→ FastAPI ←→ SQLite + queue/ + kb/
                  ↕
            后台扫描线程（10 秒轮询 queue/actions/）
```

### 后端模块

| 模块 | 功能 |
|------|------|
| database/ | SQLite 数据层（7 个领域模块：core/sessions/versions/tokens/config_ops/traces/prompts） |
| routes/ | 11 个路由模块（pipeline/approval/topics/data/kb/config/health/traces/prompts/reader/sources） |
| auth.py | API Key 认证（hmac.compare_digest 时序安全） |
| background.py | 后台任务（action 扫描、预算监控） |
| ws.py | WebSocket 实时推送（/ws/pipeline） |
| search.py | FTS5 trigram 中文搜索 |
| feishu.py | 飞书通知 |
| config_service.py | 配置管理服务 |
| models.py | Pydantic 请求/响应模型 |
| helpers.py | 共享工具函数 |

### 前端视图

| 视图 | 核心功能 |
|------|---------|
| PipelineView | 时间线视图 + Agent 阶段进度 + 超时标记 + 成本柱 |
| ApprovalView | 列表 + 展开预览 + 通过/驳回/重写按钮 + 内联编辑 |
| TopicsView | 候选列表 + 评分/来源/新鲜度标签 + 确认按钮 + 原文阅读 |
| DataView | Chart.js 趋势图 + 平台对比 + 成本消耗 |
| KbView | 5 库切换 + 全文搜索 + 侧边栏目录树 |
| ConfigView | 调度/风格/门禁/信源/模型/预算全配置 |
| SourcesView | 信源流筛选表格 + 聚合统计 |

---

## 四、Phase 3：增强完善

| 任务 | 说明 |
|------|------|
| 头条号分发 | Playwright 登录 + 推草稿箱 + Cookie 过期告警 |
| HTML 配图截图 | Playwright 渲染 HTML → 截图 PNG |
| Feedback Agent | 数据回收 → 爆款识别 → 策略更新 → 评分加权 |
| 并行 Writer | Router 分派 → 3 Worker asyncio.gather → Aggregator 合并 |
| 信源文章优化 | P0-P3 共 13 项（freshness/self_repeat/tier/config/实体聚类/内联编辑/LLM分析/目录浏览/信源流/发布状态/三栏布局/原文阅读器） |
| 知识库增强 | LLM 关键词提取 + 摘要生成 + INDEX.md 更新 |
| 临时选题入口 | Dashboard 粘贴 URL 或写 Markdown 到 queue/pending/ |

---

## 五、Phase 4：视频阶段（进行中）

| 任务 | 说明 | 状态 |
|------|------|------|
| Agnes 视频生成 | LLM prompt → Agnes 异步视频生成（`skills/writer_video.py`） | ✅ 已完成 |
| Writer 管线集成 | Stage 7b 可选视频生成，`writing_styles.json` 控制开关 | ✅ 已完成 |
| 抖音标准内容管线 | 15-60 秒脚本生成 + TTS + 画面描述 | ⏳ 待定 |
| 视频分发 | AiToEarn 视频分发（抖音/视频号/快手/B站） | ⏳ 待定 |
| 图文转视频 | 将公众号/小红书内容转为视频 | ⏳ 待定 |

---

## 六、需人工配合的环节

| 环节 | 说明 | 频率 |
|------|------|------|
| 选择选题 | 在 Dashboard 上勾选当日选题 | 每天 2 次 |
| 审批文章 | 审阅 3 个版本，决定通过/驳回 | 每天 2 次 |
| 头条号登录 | 首次配置需要扫码/输验证码 | 首次 + Cookie 过期时 |
| AiToEarn 账号注册 | 注册 + 连接社交平台 | 仅首次 |

---

## 七、成本监控

- 月预算上限默认 $15，Dashboard 可调整
- Token 消耗在 SQLite 中逐次记录
- 达 80% 警告，达上限自动暂停

---

## 八、已知待办（优先级排序）

| 优先级 | 任务 | 说明 | 预估 |
|--------|------|------|------|
| P0 | 超时自动处理 | 选题 30 分未确认自动选最高分、审批 2 小时未响应跳过 | 1 天 |
| P1 | X KOL 分级 | 8 档 X KOL 分级权重，扩展信源采集 | 2 天 |
| P2 | 前端 E2E 测试 | Playwright 覆盖 SourcesView / ReaderPanel / 三栏布局 | 1 天 |
| P3 | 平台适配引擎 | 各平台独立格式适配规则 | 3 天 |
| P3 | 选题竞争度分析 | 热度 + 饱和度二维评估 | 1 天 |
| P4 | 视频管线 | 抖音标准内容 + 视频分发 | 待定 |
