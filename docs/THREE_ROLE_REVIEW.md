# 三角色深度审核报告

## 项目概览

**稿定** — AI 内容生产系统，Scout → Writer → Publisher 多 Agent 管线，配合 Vue 3 Dashboard 进行人工审批。

竞品调研范围: Dify (143k⭐), CrewAI (52k⭐), n8n (190k⭐), Langfuse (28k⭐), Flowise (53k⭐), FastGPT (28k⭐)

---

## 一、产品经理视角

### 1.1 稿定的核心差异化优势

经过对 6 个竞品的深度分析，稿定在以下维度建立了竞品不具备的护城河:

| 差异化能力 | 竞品现状 | 稿定优势 |
|-----------|---------|---------|
| 编辑质量门禁 | Dify/CrewAI 无内容质量评估 | 3 级质量门禁(审校/批评/标题)可配置阈值 |
| 人工审批工作流 | n8n/Dify 无结构化审批 | 带驳回原因的审批队列 + 快捷键操作 |
| 中国平台分发 | 所有竞品均无 | 微信/头条/小红书/抖音/快手 5 平台原生支持 |
| AI-slop 检测 | 无竞品有此功能 | 23 个 regex 模式 + LLM 双重审校 |
| 反馈闭环 | Langfuse 仅观测 | Feedback Agent 自动检测爆款并更新策略 KB |

### 1.2 竞品最佳实践吸收清单

从竞品中提炼的 10 个高价值模式，按实施优先级排列:

**P0 — 立即实施**

1. **执行追踪树** (来源: n8n + Langfuse)
   - n8n 的执行历史: 每个管线运行记录每阶段输入/输出/耗时/状态
   - Langfuse 的 trace 树: 嵌套 span 可视化，从 Scout 到 Publisher 全链路
   - **稿定实施**: 新增 `pipeline_traces` 表 + `trace_stage()` 上下文管理器 ← 已完成

2. **结构化 Agent 输出** (来源: CrewAI)
   - CrewAI 的 `output_pydantic`: 每个 Task 输出强制 Pydantic 校验
   - **稿定实施**: 新增 `skills/agent_schemas.py` 定义 ScoutOutput/ArticleDraft/PublisherResult ← 已完成

3. **数据库模块化** (来源: n8n 节点注册表)
   - n8n 每个节点是独立模块，自注册到系统
   - **稿定实施**: `database.py` 608行 → `database/` 包，按域拆分为 core/sessions/versions/tokens/config_ops/traces ← 已完成

**P1 — 下一迭代**

4. **Prompt 版本管理** (来源: Langfuse)
   - Langfuse 的 prompt 存储支持版本化、A/B 测试、回滚
   - **稿定建议**: 在 `config_entries` 表中追踪 prompt 变更历史，Dashboard 支持 prompt 编辑和版本对比

5. **错误分支 + 自动重试** (来源: n8n)
   - n8n 的三种错误处理: Stop/Continue On Fail/Error Output Branch
   - **稿定建议**: Writer 管线的批评修订阶段如果连续 2 轮分数不升反降，自动切换 prompt 策略

6. **管线部分重跑** (来源: n8n)
   - n8n 支持从任意失败节点重新执行
   - **稿定建议**: 审批页添加"从 Stage 4 重跑"按钮，不需要从头开始

**P2 — 未来规划**

7. **知识库 chunk 级编辑** (来源: FastGPT)
8. **凭证管理加密存储** (来源: n8n)
9. **管线模板市场** (来源: Flowise)
10. **Golden Set 评测** (来源: Langfuse)

### 1.3 产品建议

| 优先级 | 建议 | 理由 |
|--------|------|------|
| P0 | 执行追踪页 | 运维必备，当前管线运行后无法回溯每阶段细节 |
| P1 | Prompt 版本管理 | 提示词迭代是内容质量的核心杠杆 |
| P1 | 管线部分重跑 | 减少用户等待时间，提升审批效率 |
| P2 | 知识库 QA 自动生成 | 利用已有文章自动生成参考语料 |

---

## 二、全栈开发工程师视角

### 2.1 架构评估

| 模块 | 行数 | 评分 | 说明 |
|------|------|------|------|
| main.py | 178 | ✅ | 精简入口，路由挂载 + 中间件 |
| routes/*.py | 665 | ✅ | 7 个路由模块，平均 95 行 |
| database/ | ~350 | ✅ | 已拆分为 7 个域模块（core, sessions, versions, tokens, config_ops, traces, prompts） |
| search.py | 385 | ✅ | FTS5 trigram 中文搜索 |
| writer.py | 659 | ⚠️ | 7 阶段管线，可拆分但非阻塞 |
| common.py | 586 | ✅ | AgentBase 统一架构 |
| agent_schemas.py | ~80 | ✅ | 结构化输出模型 |

### 2.2 从竞品学到的架构改进

**已实施:**

1. **执行追踪** (n8n 模式)
   - 新增 `pipeline_traces` 表记录每阶段 I/O
   - `trace_stage()` 上下文管理器自动计时和错误捕获
   - 支持按 session/agent 查询追踪记录

2. **结构化输出** (CrewAI 模式)
   - `TopicCandidate`, `ScoutOutput`, `ArticleDraft`, `PublisherResult` Pydantic 模型
   - 强制类型校验，防止 Agent 输出格式漂移

3. **数据库模块化** (n8n 节点模式)
   - `database/__init__.py` 保持向后兼容的 re-export
   - 按域拆分: core(连接), sessions(管线), versions(版本+审批), tokens(用量+预算), config_ops(配置), traces(追踪), prompts(提示词版本)

4. **WebSocket 推送** (Dify 模式)
   - `ws.py` — `ConnectionManager` 每 3s 轮询状态文件，hash 变更检测后广播
   - 前端通过 `ws://host/ws/pipeline` 接收实时状态更新
   - `asyncio.to_thread()` 包装同步 `_build_status()` 避免阻塞事件循环

5. **Prompt 版本管理** (Langfuse 模式)
   - `/api/prompts` CRUD API，数据库 `prompt_versions` 表
   - 启动时自动从 `config/prompts/*.txt` 导入
   - 支持版本切换、激活、删除

**待实施:**

6. **Agent YAML 配置** (CrewAI 模式)
   - CrewAI 的 agent 定义在 YAML 中，运行时加载
   - 建议: 将 Scout/Writer/Publisher 的角色定义、提示词、模型参数外置为 YAML

### 2.3 安全审计

| 检查项 | 状态 | 说明 |
|--------|------|------|
| SQL 注入 | ✅ | 参数化查询，无字符串拼接 |
| XSS | ✅ | Vue 自动转义 + DOMPurify 清理 markdown 渲染 + CSP headers |
| 时序攻击 | ✅ | `hmac.compare_digest` 常量时间比较 |
| 输入验证 | ✅ | Pydantic v2 强校验 |
| 密钥管理 | ✅ | 环境变量，无硬编码 |
| 子进程管理 | ✅ | set 追踪 + shutdown 清理 |
| 原子写入 | ✅ | tempfile + fsync + rename |
| Rate Limiting | ✅ | 内存限流 + LRU 淘汰 + 触发端点独立限流 |

### 2.4 测试覆盖

| 指标 | 数值 | 说明 |
|------|------|------|
| 总测试数 | 390+ | 后端 API + 数据库 + 搜索 + 飞书 + 后台 + 前端 |
| 后端覆盖率 | 80%+ | 含 auth, helpers, traces, prompts 等新增模块 |
| 路由覆盖率 | 99% | approval/config/health 100%，pipeline 95% |
| writer.py 覆盖率 | 86% | 从 69% 提升 |
| 前端测试 | 36 | useToast/StatusBadge/dashboard store |

---

## 三、UI/UX 设计师视角

### 3.1 用户旅程分析

#### 核心旅程: 审批一篇文章 (4 步)

```
Pipeline 页 → 看到待审批数 → Approval 页 → Enter 通过 / R 驳回
```

**对标 n8n 的执行历史 UX:**
- n8n 每次执行有完整的节点级时间线，点击任意节点查看 I/O
- 稿定目前只有最终状态，缺少中间过程可视化
- **建议**: Pipeline 页增加"执行详情"展开面板，显示每阶段耗时和评分曲线

#### 次要旅程: 查看管线运行历史

**现状问题**: Pipeline 页只显示当前状态，历史运行需要去 Data 页看统计
**对标 n8n**: n8n 的 Executions tab 有完整的运行历史，支持按状态/日期筛选，点击进入详情
**建议**: Pipeline 页增加"历史" tab，展示最近 14 天的管线执行记录，每条可展开查看阶段详情

### 3.2 竞品 UX 最佳实践

| UX 模式 | 来源 | 稿定应用 |
|---------|------|---------|
| 执行时间线 | n8n | Pipeline 页增加阶段时间线组件 |
| Trace 树展开 | Langfuse | 审批页显示文章从选题到成稿的完整 trace |
| 节点状态内联 | Dify | 看板卡片显示当前阶段进度条 |
| Debug 模式 | Dify | 选题页增加"预览管线"功能，用测试数据跑一遍 |
| Prompt Playground | Langfuse | 配置页增加 prompt 编辑器，支持实时预览 |

### 3.3 视觉设计评估

| 元素 | 评分 | 改进方向 |
|------|------|---------|
| 色彩系统 | ✅ | CSS 变量 + 深色模式，对比度达标 |
| 字体层级 | ✅ | PingFang SC + 等宽代码字体 |
| 间距系统 | ✅ | 4px-40px 标准化 |
| 动画系统 | ✅ | 过渡自然，骨架屏加载 |
| 空状态 | ⚠️ | 可增加插图引导(参考 Linear 的空状态设计) |
| 数据可视化 | ⚠️ | Chart.js 可用，但缺少管线执行的时间轴图 |

### 3.4 可访问性

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 键盘导航 | ✅ | 审批页 Enter/R/E 快捷键，ConfirmDialog 焦点陷阱 |
| 颜色对比度 | ✅ | 深色/浅色模式均达标，CSS 变量统一 |
| 语义化 HTML | ✅ | Kanban 卡片 role="link"，错误 role="alert"，aria-hidden 装饰元素 |
| 屏幕阅读器 | ✅ | StatusBadge aria-label，SkeletonLoader aria-hidden，按钮 aria-label |
| 焦点管理 | ✅ | 全局 :focus-visible 样式，ConfirmDialog 焦点陷阱 + 恢复焦点 |
| 触控目标 | ✅ | 按钮最小高度 32px，移动端分页 32px |
| 响应式 | ✅ | 移动端底部导航，375px 网格适配 |
| XSS 防护 | ✅ | DOMPurify 清理 markdown 渲染输出 |

---

## 四、独特优化建议 (竞品未覆盖)

### 4.1 内容质量飞轮

**问题**: 当前质量门禁是静态阈值，不会根据历史数据自动调整
**方案**: 利用 Feedback Agent 的爆款检测数据，自动调整质量门禁阈值
- 如果近 7 天爆款文章的平均审校分是 75，则将 `proofread_threshold` 从 60 上调到 70
- 如果某类选题的爆款率显著高于平均，则提高该类选题的评分权重
- 这是所有竞品都没有的自适应质量控制能力

### 4.2 平台适配引擎

**问题**: 当前 Publisher 对每个平台使用相同的正文，只有格式差异
**方案**: 为每个平台构建适配规则引擎
- 小红书: 自动添加 emoji 分段、标签、首图引导语
- 抖音: 自动提取金句作为视频文案、生成口播脚本
- 头条: 自动添加 SEO 关键词、相关文章推荐
- 微信: 自动生成摘要、添加公众号引导关注
- 这比竞品的通用发布能力更贴合中国内容平台的运营需求

### 4.3 选题竞争度分析

**问题**: Scout 只看热度，不看竞争度
**方案**: 对每个选题关键词搜索已有内容数量，计算饱和度
- 高热度 + 低饱和度 = 优先选题
- 高热度 + 高饱和度 = 需要差异化角度
- 这个二维评估比单纯的热度评分更精准

### 4.4 管线成本预算分配

**问题**: 当前只有月度总预算，无法按管线阶段分配
**方案**: 参考 Langfuse 的 trace 级成本追踪，支持按 agent/阶段设置预算上限
- Scout 预算: $2/月 (选题发现不需要太多 token)
- Writer 预算: $10/月 (核心生产环节)
- Publisher 预算: $3/月 (主要是格式化)
- 超预算时自动降级模型或暂停对应阶段

---

## 五、实施清单

### 已完成
- [x] 数据库模块化拆分 (database.py → database/ 包，7 个域模块)
- [x] 执行追踪系统 (pipeline_traces 表 + trace_stage 上下文管理器 + 批量查询优化)
- [x] 结构化 Agent 输出模型 (agent_schemas.py: ScoutOutput/ArticleDraft/PublisherResult)
- [x] WebSocket 实时推送 (ws.py: ConnectionManager, 3s 轮询 + hash 变更检测)
- [x] Prompt 版本管理 (/api/prompts CRUD, 数据库版本化, 启动自动导入)
- [x] 质量门禁配置化 (config/quality_gates.json, Writer 管线各阶段读取阈值)
- [x] 路由测试覆盖 99% (approval/config/health 100%, pipeline 95%)
- [x] writer.py 覆盖率 69% → 86%
- [x] 前端测试框架 (Vitest + 36 测试)
- [x] 390+ 测试通过，后端覆盖率 80%+
- [x] 可访问性增强 (焦点陷阱, :focus-visible, aria-label, DOMPurify, 触控目标)

### 待实施 (按优先级)
| 优先级 | 任务 | 来源 | 工作量 |
|--------|------|------|--------|
| P0 | Pipeline 追踪页 UI | n8n 执行历史 | 2 天 |
| P1 | 管线部分重跑 | n8n 节点重跑 | 1 天 |
| P2 | 平台适配引擎 | 独创 | 3 天 |
| P2 | 内容质量飞轮 UI | 独创 | 2 天 |
| P3 | 选题竞争度分析 | 独创 | 1 天 |
| P3 | Agent YAML 配置 | CrewAI 模式 | 1 天 |
