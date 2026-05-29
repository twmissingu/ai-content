# 信源文章优化清单

> 来源：[肝了三天，我把用Hermes搭建的内容自动化生产线升级成了一站式网站](https://mp.weixin.qq.com/s/A6dzmcjD-Jn9cKGCn9nThg)
> 对标项目：ai-content v0.7.0
> 生成时间：2026-05-29

---

## 文章核心观点

作者用 Hermes 搭建了一条内容自动化生产线，并围绕 6 个真实问题做了升级：

1. **信源够不够？** — 从 138→180 源，分 T1/T1.5/T2 三档，X KOL 分 8 档
2. **扫出来的东西怎么看？** — 三栏布局（信源流 / 阅读器+编辑器 / 工具箱）
3. **怎么知道哪些值得写？** — 双层评分：关注度 + 信息增量，饱和度用实体聚类
4. **人应该站在 AI 哪个环节？** — 原文高亮+笔记指导 AI 写作，不只是事后审批
5. **怎么让经验沉淀？** — 四类 KB（选题/爆款/历史/策略），标注自动入 KB
6. **从写完到发出去？** — 异步 Job + SSE 进度 + 一键推送草稿箱

---

## 逐项对比

### 问题 1：信源够不够

| 维度 | 文章做法 | ai-content 现状 | 差距 |
|------|---------|----------------|------|
| 信源数量 | 180 个（RSS 83 + X 48 + GitHub 12 + Reddit 18 + Jina 19） | `scout.py` 12 种信源类型 | 缺少 X KOL 分级、Reddit、Jina |
| 信源分级 | T1(×1.15) / T1.5(×1.08) / T2(×1.0) | `config/sources.json` + T1/T1.5/T2 分级 | 已实现 |
| 新鲜度 | 1h=爆发、48h=热议、>48h=过期 | `calculate_freshness()` 基于 timestamp/hot_value | 已实现 |
| X KOL 分级 | 8 档（CEO 35→国产AI 16） | 无 | 缺失 |

### 问题 2：可视化

| 维度 | 文章做法 | ai-content 现状 | 差距 |
|------|---------|----------------|------|
| 布局 | 三栏并排 | 单栏卡片堆叠 | 无并排对照 |
| 信源流 | 实时刷新、评分+来源+新鲜度、搜索过滤 | 无信源流视图 | **缺失** |
| 阅读+编辑 | 原文和作品并排对照 | ApprovalView 只读预览 | 缺编辑器 |
| 面板控制 | 可折叠、全屏、并排 | 固定布局 | 缺失 |

### 问题 3：选题公式

| 维度 | 文章做法 | ai-content 现状 | 差距 |
|------|---------|----------------|------|
| 关注度公式 | 源质量(^1.3)×0.35 + 传播×0.30 + 新鲜度×0.35 | 同 | 已对齐 |
| 信息增量公式 | 饱和×0.40 + 新颖×0.35 + 自重复×0.25 | 同 | 已对齐 |
| 饱和度 | 实体聚类 + Jaccard>25% | 关键词重叠>30% | 文章更精确 |
| 自重复 | 同实体同方向=10，不同方向=50，全新=100 | `calculate_self_repeat()` 基于 KB 历史 | 已实现 |
| 最终公式 | raw × tier_multiplier | raw × tier_multiplier | 已实现 |
| 阈值 | <55 淘汰、>70 候选、>85 强推 | 同（TopicsView 已显示强推标签） | 已对齐 |

### 问题 4：人在环

| 维度 | 文章做法 | ai-content 现状 | 差距 |
|------|---------|----------------|------|
| 原文阅读 | 阅读器 + 高亮 + 笔记 + 翻译 | 无 | **缺失** |
| 协作模式 | 读→标注→AI 写→对照改 | AI 写→审批→驳回重写 | 文章是"指导式"，项目是"事后式" |
| 审批界面 | 阅读器+编辑器并排 | 只读预览 + approve/reject | 缺编辑 |
| 驳回细化 | 段落级标记 | 全文级自由文本 | 文章更精细 |

### 问题 5：知识库

| 维度 | 文章做法 | ai-content 现状 | 差距 |
|------|---------|----------------|------|
| KB 分类 | 选题/爆款/历史/策略（4 类） | topics/viral/history/strategy/materials（5 类） | 基本一致 |
| 自动沉淀 | 高亮/笔记自动入 KB | 纯文件复制，无 AI 分析 | 缺 AI 提取 |
| KB 浏览 | 可浏览+搜索 | 仅搜索+section 过滤 | 缺目录浏览 |
| 爆款分析 | 自动提取标题模式和关键词 | 无自动分析 | 缺失 |

### 问题 6：发布

| 维度 | 文章做法 | ai-content 现状 | 差距 |
|------|---------|----------------|------|
| 平台数 | 头条为主 | 6 平台 | **项目更全面** |
| 异步 Job | 后台子进程 + SSE 进度 | 同步子进程（60s timeout） | 缺异步化 |
| 双格式 | HTML + Markdown 自选 | 平台适配器自动转 | 项目更自动化 |
| 发布 UI | 一键保存+推送 | PipelineView 手动触发 | 基本具备 |

---

## 优化清单

### P0：低成本高收益（立即可做）

#### 1. 实现真实 freshness_score ✅

- **文件**：`skills/scout.py`
- **现状**：`freshness_score = 60` 硬编码默认值（第 361 行）
- **目标**：基于发布时间距当前时间差计算
- **方案**：
  ```
  1h 内  → 90（爆发期）
  6h 内  → 75
  24h 内 → 60
  48h 内 → 40
  >48h   → 20（已过期）
  ```
- **改动量**：~10 行
- **预计工时**：0.5h
- **状态**：已实现 `calculate_freshness()` — 支持 timestamp 字段和 hot_value 回退

#### 2. self_repeat_score 细分 ✅

- **文件**：`skills/scout.py`
- **现状**：去重过滤后 `self_repeat = 100`（第 417 行），丢失了"同实体不同方向"的区分
- **目标**：检查 kb/history 中是否已有同实体文章
- **方案**：
  ```
  同实体同方向   → 10
  同实体不同方向 → 50
  全新           → 100
  ```
- **改动量**：~15 行
- **预计工时**：1h
- **状态**：已实现 `calculate_self_repeat()` — 复用 topic_analyzer 的关键词提取和历史文章检索

#### 3. STRONG_PUSH 接入 TopicsView ✅

- **文件**：`dashboard/frontend/src/views/TopicsView.vue`
- **现状**：`STRONG_PUSH = 85` 已定义但未在 UI 使用
- **目标**：对 score > 85 的选题标注"强推"标签
- **改动量**：~5 行
- **预计工时**：0.5h
- **状态**：已存在 — TopicsView 的 `getScoreColor`/`getScoreLabel` 已使用 >= 85 显示 'success'/'强推'

#### 4. tier_multiplier 接入选题公式 ✅

- **文件**：`skills/scout.py`
- **现状**：`final_score = attention×0.55 + increment×0.25 + feasibility×0.20`，无信源档位乘数
- **目标**：`final_score = raw_score × tier_multiplier`
- **方案**：基于 SOURCE_WEIGHTS 值划分 T1(≥0.85, ×1.15) / T1.5(≥0.70, ×1.08) / T2(其他, ×1.0)
- **改动量**：~5 行
- **预计工时**：0.5h
- **状态**：已实现 — `score_candidate` 中 `final_score = raw_score * tier_multiplier`

#### 5. 信源权重配置化 ✅

- **文件**：`skills/scout.py` + 新增 `config/sources.json`
- **现状**：`SOURCE_WEIGHTS` 硬编码在 Python 文件中（第 55-68 行）
- **目标**：提取到 JSON 配置文件，支持运行时修改
- **方案**：
  ```json
  {
    "twitter": {"weight": 0.95, "tier": "T1", "label": "X/Twitter"},
    "rss": {"weight": 0.85, "tier": "T1.5", "label": "RSS 订阅"},
    ...
  }
  ```
- **改动量**：~20 行
- **预计工时**：1h
- **状态**：已实现 — `config/sources.json` + `_load_sources_config()` 加载器

---

### P1：中等成本显著体验提升

#### 6. ApprovalView 增加内联编辑

- **文件**：`dashboard/frontend/src/views/ApprovalView.vue` + 后端 API
- **现状**：审批页面只有只读预览 + approve/reject 按钮
- **目标**：在审批界面增加 Markdown 编辑器，允许直接修改文章
- **方案**：集成 Tiptap 或使用 textarea + marked 实时预览，保存时调用后端更新接口
- **改动量**：前端 ~200 行 + 后端 ~50 行
- **预计工时**：4-6h

#### 7. KbView 增加目录浏览

- **文件**：`dashboard/frontend/src/views/KbView.vue` + `dashboard/backend/routes/kb.py`
- **现状**：KbView 仅支持搜索 + section 过滤，无目录浏览
- **目标**：增加左侧文件树或面包屑导航，支持按目录层级浏览
- **方案**：后端新增 `/api/kb/tree` 返回目录结构，前端增加树形导航组件
- **改动量**：前端 ~150 行 + 后端 ~80 行
- **预计工时**：3-4h

#### 8. 新增 `/sources` 信源流页面

- **文件**：新建前端页面 + 后端 API
- **现状**：无信源流视图，TopicsView 只显示 Scout 输出的候选选题
- **目标**：展示 Scout 抓取的原始信源条目（不只是候选选题），带评分、来源、新鲜度标签
- **方案**：Scout 输出时保存原始抓取结果到 `queue/sources/`，前端新增 `/sources` 页面渲染
- **改动量**：前端 ~300 行 + 后端 ~100 行 + scout.py ~30 行
- **预计工时**：6-8h

#### 9. knowledge.py AI 分析归档

- **文件**：`skills/knowledge.py`
- **现状**：归档时只做文件复制（review→history），无 AI 分析
- **目标**：归档时用 LLM 提取关键词、话题标签、写作模式，写入 KB 元数据
- **方案**：在文件复制后增加 LLM 分析步骤，生成 `.meta.json` 伴随文件
- **改动量**：~80 行
- **预计工时**：3-4h

---

### P2：长期架构级优化

#### 10. 三栏布局改造

- **范围**：前端整体布局重构
- **现状**：单栏卡片堆叠，6 个独立页面
- **目标**：可选的三栏布局（信源流 / 主内容区 / 工具箱），面板可折叠、全屏
- **方案**：引入 resizable panel 组件，重构 App.vue 布局
- **预计工时**：2-3 天

#### 11. 原文阅读 + 标注系统

- **范围**：新增阅读器组件 + 后端存储
- **现状**：无原文阅读视图，无标注能力
- **目标**：选中信源后展示原文，支持高亮、笔记、翻译，标注自动附加到 writer prompt
- **预计工时**：1 周

#### 12. 发布异步化 + SSE 进度

- **范围**：publisher 重构 + WS 推送
- **现状**：同步子进程（60s timeout），无进度流
- **目标**：发布改为后台 Job，通过 WebSocket 推送每个平台的发布进度和结果
- **预计工时**：2-3 天

#### 13. 饱和度升级为实体聚类

- **范围**：`skills/topic_analyzer.py` 重构
- **现状**：基于关键词重叠（>30%）的简单相似度计算
- **目标**：提取实体词（OpenAI、GPT-5、Agent 等），用 Jaccard 相似度 >25% 做事件聚类
- **预计工时**：1-2 天

---

## 验证方式

```bash
# P0 验证
pytest tests/test_topic_analyzer.py tests/test_scout*.py -v   # freshness/self_repeat/tier 测试
cd dashboard/frontend && npm run test:e2e                      # TopicsView 强推标签

# P1 验证
pytest tests/test_api_*.py -v                                  # 新 API 测试
cd dashboard/frontend && npm run test:e2e                      # ApprovalView 编辑、KbView 浏览

# P2 验证
pytest --cov=skills --cov-report=term                          # 全量覆盖率
cd dashboard/frontend && npm run build                         # 前端构建
```
