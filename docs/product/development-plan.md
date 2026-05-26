# 开发计划书 — 稿定（AI 内容生产系统）

> 基于 PRD v1.4  
> 环境状态：Hermes v0.14.0 已安装，Python 3.14.5/Node v26 就绪  
> 仓库状态：Phase 2 实现中（核心管线 + Dashboard 已编码，详见下方备注）

---

## 一、现状评估：可以直接开始吗？

**可以，但有前提条件。**

### 已就绪的环境

| 资源 | 状态 | 说明 |
|------|------|------|
| Hermes Agent v0.14.0 | ✅ 已安装 | `/Users/twzhan/.local/bin/hermes`，含 50+ skills |
| Python 3.14.5 | ✅ 已安装 | 系统级，Dashboard 后端用 |
| Node v26 / npm | ✅ 已安装 | Dashboard 前端（Vue 3 + Vite）用 |
| 项目目录 | ✅ 已创建 | `/Users/twzhan/Documents/dev/ai-content/` |

### 缺失项（开发前需补齐）

| 资源 | 状态 | 影响 |
|------|------|------|
| Playwright | ❌ 未安装 | 头条号分发 + HTML 配图截图依赖 |
| git 仓库 | ❌ 未初始化 | 版本管理需求 |
| 项目目录结构 | ❌ 未创建 | skills/ dashboard/ scripts/ 等不存在 |
| Hermes MCP 集成 | ❌ 未配置 | 未连接 AiToEarn / china-hot-mcp 等 |

### 核心未知项（Phase 0 PoC 需回答）

从 PRD 风险矩阵提取，这些问题的答案会直接影响架构设计：

1. Hermes cron 能用吗（固定时间点触发能否满足需求）？
2. Hermes Skill 如何与 Python 代码集成（skill.py 的入口签名是什么）？
3. `/llm-wiki` 支持中文搜索吗？
4. `deliver_to` 支持飞书吗？
5. AiToEarn MCP 有没有数据回收接口？
6. baoyu skills 能否直接加载？

**这些问题必须在 Phase 0 验证完，否则后面可能返工。**

---

## 二、总体路线图

```
Phase 0 ─→ Phase 1 ─→ Phase 2 ─→ Phase 3 ─→ Phase 4
  2-3天       2周        1.5周      1.5周+      待定
                      ↑
              核心可运行里程碑
              （单篇管线跑通）
```

| Phase | 产出 | 依赖 |
|-------|------|------|
| 0 | 技术选型确认 + 项目骨架 | 无 |
| 1 | 选题→写作→分发全链路跑通（单 Worker） | Phase 0 |
| 2 | Web Dashboard 可视化 + 审批操作 | Phase 1（有内容可审） |
| 3 | 头条号 + 反馈飞轮 + 并行 Writer | Phase 1+2 |
| 4 | 视频内容管线 | Phase 3 |

---

## 三、Phase 0：基础设施验证（2-3天）

### 任务 0.1 — Hermes 能力边界验证

逐项确认 PRD 中标记的未知项，每一项的结果可能迫使架构调整：

| 验证项 | 方法 | 通过标准 | 不通过的备案 |
|--------|------|---------|-------------|
| cron 调度 | 配一个 cron job，看能否按固定时间触发 Python 脚本 | 定时触发成功 | 改用 system crontab 直接调度 Python 脚本 |
| Skill 开发模式 | 写一个 Hello World Skill，看入口签名 | Skill.py 能被 Hermes 加载并执行 | Agent 改为独立 Python 脚本，Hermes 仅做 cron 触发器 |
| `/llm-wiki` 中文搜索 | 写入中文内容，用关键词+近义词搜索 | 能搜到 | Phase 2 自建 FTS5 索引替代 |
| `deliver_to` 飞书 | 配置飞书 webhook 测试 | 消息推送成功 | Dashboard 后端集成飞书 SDK（方案 B） |
| baoyu skills | 加载 baoyu 已有 skills | 工具可用 | 自建配图和微信发布的 Python 脚本 |

**输出：** `docs/decisions/phase0-hermes-capabilities.md` — 记录每项的验证结果和决策。

### 任务 0.2 — 项目目录初始化

创建 PRD 2.7 节定义的全部目录结构：

```bash
project-root/
├── skills/           # Agent 实现代码
│   ├── scout.py
│   ├── writer.py
│   ├── publisher.py
│   ├── feedback.py
│   └── knowledge.py
├── dashboard/
│   ├── backend/      # FastAPI
│   │   ├── main.py
│   │   ├── models/
│   │   ├── routes/
│   │   └── services/
│   └── frontend/     # Vue 3 + Vite
│       └── src/
│           ├── components/
│           ├── views/
│           └── stores/
├── scripts/
│   ├── watchdog.sh
│   ├── cleanup_images.py
│   ├── scan_actions.py
│   └── init_directories.sh
├── config/
├── data/
│   └── logs/
├── queue/
│   ├── actions/
│   │   └── processed/
│   ├── status/
│   ├── review/
│   ├── pending/
│   ├── failed/
│   ├── images/
│   ├── topics/
│   └── tmp/
└── kb/
    ├── topics/
    ├── viral/
    ├── history/
    ├── strategy/
    ├── materials/
    └── INDEX.md
```

**还包括：**
- `scripts/init_directories.sh` — 一键创建所有运行态目录
- `scripts/watchdog.sh` — 进程守护脚本
- 文件写入原子性约定（`.tmp + rename`）纳入开发规范

### 任务 0.3 — 外部依赖配置

| 依赖 | 动作 | 参考文档 |
|------|------|---------|
| AiToEarn MCP | 注册账号 → 创建 API Key → 配置到 Hermes | 仓库内 `docs/manual/AiToEarn配置与自动化操作指引.md` |
| china-hot-mcp | pip 安装 → Hermes MCP 配置 | 同上 |
| Firecrawl | 确认 Hermes 内置配置 | Hermes 文档 |
| Playwright | `npx playwright install chromium` | Playwright 文档 |
| git | `git init` + `.gitignore`（屏蔽 queue/ data/ config/） | — |

### Phase 0 退出标准

- [ ] Hermes 7 项能力验证全部记录，不确定项已明确备案方案
- [ ] 项目目录结构就绪，`init_directories.sh` 可一键重建
- [ ] AiToEarn / china-hot-mcp / Firecrawl 连接配置完成
- [ ] 最小 Skill 开发流程跑通（能写一个 Python 脚本并通过 Hermes 调用）
- [ ] git 仓库初始化

---

## 四、Phase 1：核心管线（2周）

目标是：**选题→写作→分发 全链路跑通**。Phase 1 只做单 Worker（公众号标准），不启动并行 Writer。

### 架构概览（Phase 1 的范围）

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

### 任务 1.1 — Scout Agent（2天）

职责：扫描多渠道，评分，推送候选选题。

**内部子任务：**

| 子任务 | 产出 |
|--------|------|
| 编写信息源采集模块 | 集成 china-hot-mcp，调用各平台 trending 接口 |
| 编写评分模型 | 实现 PRD 3.1 节评分公式（两层评分 + 最终得分） |
| 实现选题推荐输出 | 评分后写入 `queue/pending/` + 飞书推送 |
| 实现选题确认机制 | Dashboard 写 `queue/actions/confirm_{id}.json` → 触发 Writer |
| 状态文件写入 | 写 `queue/status/scout.json` |
| 冷启动参数策略 | 前 2 周使用替代参数（source_weight 替代 viral_score 等） |
| 内容同质化防御 | 近期话题屏蔽 + 方向多样性约束 |

**外部依赖：** china-hot-mcp 就绪（Phase 0.3）

### 任务 1.2 — Writer Agent（4天）

职责：7 阶段管线，单 Worker（公众号标准）。

**7 阶段管线实现顺序（建议）：**

```
阶段 ⑥ 标题优化 ──→ 可最早做，独立于其他阶段
阶段 ② LLM初稿  ──→ 核心，先跑通
阶段 ① 抓原文   ──→ 依赖度低，可并行
阶段 ③ AI腔审校 ──→ 依赖②的输出
阶段 ④ 批评修订 ──→ 依赖③
阶段 ⑤ 排版     ──→ 依赖④
阶段 ⑦ 配图     ──→ 可选，可最后做
```

**推荐实现顺序：先核心再外围**

| 顺序 | 子任务 | 说明 |
|------|--------|------|
| 1 | LLM 初稿生成 | 调用 Hermes 配置的 LLM，输出初稿 Markdown |
| 2 | 标题优化 | 生成 3 个候选标题 + LLM 打分选最优 |
| 3 | 审校去 AI 腔 | 30 条正则规则 + LLM 双检测 |
| 4 | 批评修订循环 | 评委 LLM 打分 → <70 打回重写，最多 3 轮 |
| 5 | 排版格式化 | 中英文空格、段落分割、Hashtag |
| 6 | 原文抓取 | 从选题 URL 抓素材（Firecrawl） |
| 7 | 配图 | HTML 模板渲染（零成本方案优先） |

**关键决策点：**
- Writer 的 LLM 调用：通过 Hermes 的 LLM 能力调用，还是直接调用 LLM API？
  - 建议：直接调用（通过 litellm / openai SDK），避免对 Hermes 内部 API 的耦合
- 批评修订的"评委 LLM"：与写手 LLM 同一实例还是独立实例？
  - 建议：同一实例，不同 prompt

**产出物：**
- `queue/review/{timestamp}-wechat.md` — 文章正文
- `queue/review/{timestamp}-wechat.meta.json` — 元数据（分数、轨迹、配图路径）
- `queue/status/writer.json` — 进度报告

### 任务 1.3 — Publisher Agent（2天）

职责：将审批通过的内容分发到各平台草稿箱。

**Phase 1 覆盖的平台：**

| 平台 | 方式 | 优先级 |
|------|------|--------|
| 微信公众号 | baoyu-post-to-wechat / WeChat API | P0 |
| 小红书 | AiToEarn MCP `createImageTextDraft` | P1 |
| 抖音 | AiToEarn MCP `createVideoDraft` | P1 |
| 视频号 | AiToEarn MCP | P1 |

**实现步骤：**
1. 实现微信公众号分发（先确认 baoyu 可行性，否则直接调 WeChat API）
2. 实现 AiToEarn 多平台分发
3. 失败处理：记录到 `queue/failed/` + 飞书告警
4. 分发成功后触发 Knowledge Agent 归档

### 任务 1.4 — 人工审批流程（2天）

| 子任务 | 说明 |
|--------|------|
| 飞书消息通知 | 文章就绪后推送通知卡片（仅通知，不可操作） |
| 驳回重写循环 | Dashboard 写 action 文件 → Writer 重写 → 重新审批 |
| 重写轮数控制 | 最多 3 轮，超限标记为"不可分发" |
| 审批超时跳过 | 2 小时未审批 → 自动跳过该时段 |

**飞书通知实现方案（二选一）：**
- **方案 A（推荐）：** Hermes Skill 内调用飞书 Webhook API
- **方案 B（备选）：** Dashboard 后端集成飞书 SDK

决策依据：Phase 0 中 Hermes `deliver_to` 支持飞书的结果。

### 任务 1.5 — queue/actions/ 扫描进程（1天）

独立后台进程，每 30 秒轮询 `queue/actions/` 目录：

```python
# scan_actions.py — 核心逻辑
while True:
    for f in glob("queue/actions/*.json"):
        action = json.load(open(f))
        if action["action"] == "approve":
            # 调用 Publisher
            subprocess.run(["python3", "skills/publisher.py", action["target_id"]])
        elif action["action"] == "reject":
            # 调用 Writer 重写
            subprocess.run(["python3", "skills/writer.py", "--rewrite", action["target_id"]])
        # ... 处理完成后移入 processed/
        os.rename(f, f"queue/actions/processed/{basename}")
    time.sleep(30)
```

### 任务 1.6 — 日历配置 + Cron 调度（1天）

- 实现 `config/schedule.json` 配置读取
- 配置 Hermes cron 4 个 job（早晚 Scout + 早晚 Writer）
- 支持运行日勾选（周一至周日可逐日选择）

### 任务 1.7 — 基础异常处理（1天）

| 场景 | 实现 |
|------|------|
| Writer 失败 | 自动重试 2 次 → 仍失败 → 飞书告警 + 跳过 |
| 分发失败 | 记入 `queue/failed/` + 飞书告警，不影响其他平台 |
| 配图降级 | HTML 模板 → baoyu → 不带图（不阻塞管线） |
| 超时标记 | Dashboard 读取 status 时检测超时 |

### Phase 1 退出标准

- [ ] 完整日循环跑通：Scout 选题 → 人工确认 → Writer(公众号) → 审批 → Publisher 分发到公众号/小红书
- [ ] 驳回重写循环正常（改→审→改→审）
- [ ] 失败场景有告警且不影响其他环节
- [ ] queue/ 目录完整运行（status/ actions/ pending/ review/ failed/ 均有数据）

---

## 五、Phase 2：Web Dashboard（1.5周）

### 架构

```
浏览器（Vue 3） ←→ FastAPI ←→ SQLite + queue/ + kb/
                  ↕
            后台扫描线程（30 秒轮询 queue/actions/）
```

### 任务 2.1 — FastAPI 后端（3天）

| 子任务 | 产出 |
|--------|------|
| SQLite 表结构 | pipeline_sessions / platform_versions / approval_records / token_usage / config_entries |
| Pipeline 状态 API | 读取 `queue/status/*.json` + SQLite |
| 审批操作 API | 写 `queue/actions/approve_{id}.json` / `reject_{id}.json` |
| 选题操作 API | 写 `queue/actions/confirm_{id}.json` |
| 知识库搜索 API | SQLite FTS5 + jieba 分词 |
| 配置管理 API | CRUD config/ 目录 |

### 任务 2.2 — Vue 3 前端（4天）

5 个 Tab 的实现优先级：

```
P0: Pipeline Tab + 审批队列 Tab  → 可操作系统
P1: 今日选题 Tab                  → 选题确认
P2: 配置管理 + Onboarding Wizard  → 系统设置
P3: 数据 Tab + 知识库 Tab         → 查看数据
```

| Tab | 核心功能 |
|-----|---------|
| 📊 Pipeline | 时间线视图 + Agent 阶段进度 + 超时标记 + 预估成本柱 |
| 📋 审批队列 | 列表 + 展开预览（Markdown/HTML 渲染）+ 通过/驳回/暂缓按钮 + 角标计数 |
| 🔥 今日选题 | 候选列表 + 评分/来源/新鲜度标签 + 确认按钮 |
| 📈 数据 | 阅读量趋势折线图 + 平台对比柱状图 + 成本消耗趋势（Chart.js） |
| 🗄️ 知识库 | 5 库切换 + 全文搜索 + 结果高亮 |

### 任务 2.3 — 配置管理界面（2天）

| 配置项 | UI 组件 |
|--------|---------|
| 出稿时间 | 时间选择器 + 自动推算偏移时间 |
| 写作风格 | 下拉选择器（语气/立场/篇幅） + Prompt 预览 |
| 质量门阈值 | 滑块（60-90） |
| 信息源开关 | 开关列表 + 连接状态指示 |
| 模型 Fallback 链 | 拖拽排序 |
| 月成本上限 | 输入框（默认 $15） |

### 任务 2.4 — 平台连接状态面板（0.5天）

- 每个平台显示连接状态（绿色/黄色/红色/灰色）
- 定时 health check（每 30 分钟）

### 任务 2.5 — 图片生命周期管理（0.5天）

- `scripts/cleanup_images.py` — 每天凌晨清理超 7 天图片
- 目录结构：`queue/images/{session-id}/`

### Phase 2 退出标准

- [ ] 5 个 Tab 全部可访问且有数据展示
- [ ] 审批操作写 queue/actions/ → Agent 响应
- [ ] 配置修改即时生效或下一时段生效
- [ ] Onboarding Wizard 引导首次启动
- [ ] 平台连接状态实时显示

---

## 六、Phase 3：增强完善（1.5周+）

### 任务 3.1 — 头条号分发（2天）

| 子任务 | 说明 |
|--------|------|
| Playwright 登录 | 首次人工辅助登录 → storageState 持久化到 `config/playwright_state.json` |
| 内容推送 | 模拟操作推送到头条号草稿箱 |
| Cookie 过期处理 | 检测过期 → 飞书告警 "头条号需要重新登录" |

**依赖：** Playwright 已安装（Phase 0.3）

### 任务 3.2 — HTML 配图截图管线（1天）

- 生成 HTML 模板
- Playwright `page.setContent()` → `page.screenshot()` → 保存 PNG
- 集成到 Writer 的配图阶段

### 任务 3.3 — Feedback Agent（2天）

| 子任务 | 说明 |
|--------|------|
| 数据回收 | 从各平台获取昨日阅读/互动数据 → 写入 SQLite |
| 爆款识别 | 阅读量前 20% → 提取标题模式/关键词 → 更新 kb/viral/ |
| 策略写入 | 趋势分析 → kb/strategy/ |
| 评分加权 | 爆款关键词在 Scout 评分中加分 |

**前提：** 确认 AiToEarn 是否提供数据回收接口（Phase 0 调研结果）。
**备选：** Playwright 自动化登录平台后台抓取数据。

### 任务 3.4 — 并行 Writer 架构（2天）

| 子任务 | 说明 |
|--------|------|
| Router | 接收选题 → 拆成 3 个任务 → 分派到独立子目录 |
| 3 个 Worker | asyncio.gather 并行执行 7 阶段管线 |
| Aggregator | 轮询完成 → 合并结果 → 写入 aggregated.json |
| 临时目录隔离 | `queue/tmp/{timestamp}-{type}/` |

### 任务 3.5 — 其他增强（2天）

| 子任务 | 说明 |
|--------|------|
| 临时选题入口 | Dashboard 上粘贴 URL 或写 Markdown 到 queue/pending/ |
| Fallback 链 UI | 模型优先级拖拽排序 |
| Knowledge Agent 增强 | 关键词提取 + 摘要生成 + INDEX.md 更新 |
| 领域切换支持 | 评分模型权重配置 |
| 异常告警完善 | 补充边缘场景 |

### Phase 3 退出标准

- [ ] 头条号分发跑通（登录→推草稿箱→过期告警）
- [ ] 配图截图管线集成到 Writer
- [ ] Feedback 数据回收 + 爆款库初始数据
- [ ] 3 Worker 并行 Writer 运行正常
- [ ] 全平台分发矩阵覆盖（公众号 + 小红书 + 抖音 + 视频号 + 头条号 + 百家号）

---

## 七、Phase 4：视频阶段（待定）

| 任务 | 说明 |
|------|------|
| 抖音标准内容管线 | 15-60 秒脚本生成 + TTS + 画面描述 |
| 视频分发 | AiToEarn 视频分发（抖音/视频号/快手/B站） |
| 图文转视频 | 将公众号/小红书内容转为视频 |

---

## 八、风险与关键决策跟踪

### 未知项（Phase 0 必须回答）

| # | 问题 | 回答后影响 |
|---|------|-----------|
| U1 | Hermes cron 能否触发 Python 脚本？ | 否 → 改用 system crontab |
| U2 | Hermes Skill 的 Python 入口签名是什么？ | 影响所有 Agent 代码结构 |
| U3 | `/llm-wiki` 支持中文搜索吗？ | 否 → Phase 2 必须自建 FTS5 |
| U4 | `deliver_to` 支持飞书吗？ | 否 → Dashboard 集成飞书 SDK |
| U5 | AiToEarn MCP 有数据回收接口吗？ | 否 → Feedback 走 Playwright 抓数据 |
| U6 | baoyu skills 能否直接加载？ | 否 → 自建配图 + 微信发布模块 |

### 需人工配合的环节

| 环节 | 说明 | 频率 |
|------|------|------|
| 选择选题 | 在 Dashboard 上勾选当日选题 | 每天 2 次 |
| 审批文章 | 审阅 3 个版本，决定通过/驳回 | 每天 2 次 |
| 头条号登录 | 首次配置需要扫码/输验证码 | 首次 + Cookie 过期时 |
| AiToEarn 账号注册 | 注册 + 连接社交平台 | 仅首次 |

### 成本监控

- 月预算上限默认 $15，Dashboard 可调整
- Token 消耗在 SQLite 中逐次记录
- 达 80% 警告，达上限自动暂停

---

## 九、Phase 0 速查：Hermes 验证清单

以下是你需要逐项在终端检查的内容：

```bash
# 1. cron 是否可用
hermes run --help                    # 看是否有 cron 相关子命令
cat ~/.hermes/config.yaml | grep cron  # 检查现有 cron 配置

# 2. 创建最小 Skill 测试
mkdir -p ~/.hermes/skills/test-hello
# 写一个最简单的 skill.yaml + hello.py
# 执行 hermes run test-hello 看能否输出

# 3. MCP 配置
cat ~/.hermes/config.yaml | grep mcp_servers  # 是否已有 MCP 配置
hermes mcp --help

# 4. llm-wiki
hermes llm-wiki --help               # 查看命令是否存在

# 5. baoyu skills
ls ~/.hermes/skills/ | grep baoyu    # 是否已安装

# 6. AiToEarn 数据接口
# 在 AiToEarn MCP 文档中搜索 analytics / data / stats 关键词
```

将这些结果记录到 `docs/decisions/phase0-hermes-capabilities.md`，后续所有架构决策基于此文件。

---

## 十、建议的工作方式

### Phase 0 → Phase 1 的切换条件

Phase 0 完成后，不建议等全部验证完再开始编码。可以**并行推进**：

```
Phase 0.1 (Hermes验证)         ──→ Phase 1 开始
Phase 0.2 (项目目录初始化)      ──→ 并行
Phase 0.3 (外部依赖配置)        ──→ 并行
```

Hermes 验证通过 3 项核心能力（cron / Skill / MCP）后即可启动 Phase 1 编码，其余验证项可继续并行进行。

### 每个 Phase 内的节奏

```
Day 1-2:  核心数据结构 + 核心逻辑
Day 3-4:  集成 + 异常处理
Day 5+:   测试 + 修复 + 文档
```

### 退出标准的含义

每个 Phase 的退出标准是"可以开始下一 Phase"的最低条件，不是"100% 无 bug"。未覆盖的边缘场景在后续 Phase 中修复。
