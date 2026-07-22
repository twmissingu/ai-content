# POLISH_LOG.md — 稿定打磨日志

> 本日志记录 jiuqing-product-polish 迭代过程。起始状态: v0.9.11 + 2 次提交加固

---

## Round 0 — 基线评估（2026-07-22）

### 项目状态

- **版本**: v0.9.11 + 2 commits
- **测试**: 851 passed
- **源码**: Python ~12,300 行 + Vue/TS ~9,200 行
- **模式**: 14 轮 vibe-evolve 迭代已完成，本次为新打磨

### 自上次迭代后变化

- fix: 多维度生产就绪加固（303cc93）
- fix: 代码审查全量修复（7dc9d8a）
- 未提交: settings.py 去除 .hermes 加载、llm.py 增加 reasoning 字段提取

### 待解决问题 (issues_dev.json)

| ID | 级别 | 类别 | 文件 | 问题 |
|----|------|------|------|------|
| DEV-001 | HIGH | security | writer_stages.py:143 | SSRF DNS 解析失败时 fail-open |
| DEV-002 | HIGH | bug | approval.py:93 | action 文件先于 DB 写入，顺序颠倒 |
| DEV-003 | HIGH | bug | background.py:67 | 硬编码 .venv Python 路径 |
| DEV-004 | MEDIUM | code_quality | action.py:35 | ActionFile dict 继承模式脆弱 |
| DEV-005 | MEDIUM | code_quality | common.py:319 | 函数体内自我 import |
| DEV-006 | MEDIUM | security | writer_stages.py:222 | prompt injection safety 关闭 |
| DEV-007 | MEDIUM | error_handling | writer_stages.py:336 | QualityGate 验证失败 silent pass |
| DEV-008 | MEDIUM | code_quality | ApprovalVersionPanel.vue:35 | API_BASE 多处重复定义 |
| DEV-009+ | MEDIUM | 待读 | 待确认 | 剩余 issue |

### 基线维度评分

| 维度 | 基线 | 参考证据 |
|------|------|----------|
| 功能完整性 | 8 | 48 项核心功能完成，但 issues_dev 有 3 high |
| 可靠性 | 8 | 851 tests pass, trail 锁 + timeout 原子性已加 |
| 性能 | 8 | WAL 模式 + 查询缓存 + 复合索引 |
| 安全性 | 9 | 有 SSRF 保护但 fail-open（DEV-001） |
| 代码质量 | 9 | WriterAgent 重构完成，但有自我 import（DEV-005） |
| 测试覆盖 | 9 | 851 后端测试，69 前端测试 |
| 用户体验 | 8 | aria-live + focus trap 已加 |
| UI 精细度 | 7 | 设计系统完成但无新迭代 |
| 可访问性 | 8 | WCAG AA 已达标 |

**综合评分: 8.3 / 10**

### issues_dev 优先级修复顺序

1. DEV-001 (SSRF fail-open, high, security)
2. DEV-002 (写入顺序颠倒, high, bug)
3. DEV-003 (硬编码路径, high, bug)
4. DEV-006 (injection_safety=False, medium, security)
5. DEV-007 (QualityGate silent pass, medium, error handling)
6. DEV-004 (ActionFile 模式, medium, quality)
7. DEV-005 (自我 import, medium, quality)
8. DEV-008 (API_BASE 重复, medium, quality)
9. DEV-009+ (剩余 issues)

---

## Round 1 — UI 精细度修复（2026-07-22）

### 聚焦维度

**UI 精细度** — 从 7/10 提升。

### 改进

1. **修复 Transition 警告** — 将 `ErrorBoundary` 从 `<Transition>` 内部移至外部，使 `App.vue` 中 `<router-view>` 的过渡动画正常工作。消除 Vue 运行时 warning。
2. **TopicsView 单根节点** — 为 TopicsView.vue 模板添加包裹层 `<div>`，使其从多根（`.topics-view` + `ReaderPanel`）变为单根结构，兼容 Vue `<Transition>` 要求。

### 修改文件

- `dashboard/frontend/src/App.vue` — ErrorBoundary 移出 router-view 包裹层
- `dashboard/frontend/src/views/TopicsView.vue` — 添加模板根包裹层

### 验证

- 前端测试 69/69 通过 | 后端测试 851/851 通过
- Playwright 确认 0 warnings, 0 errors (Transition 警告已消除)
- 所有路由页面正常渲染

### 状态

**已完成** ✅

---

## Round 2 — 代码质量修复（DEV-005 自我 import）（2026-07-22）

### 聚焦维度

**代码质量** — 从 9/10 微调。

### 改进

- 移除 `skills/common.py` 中两处函数体内的 `from skills.common import atomic_write_json` 自我导入。该函数已在模块级定义（第 174 行），调用时已在作用域内。

### 修改文件

- `skills/common.py` — 删除第 319、341 行不必要的内联自我导入

### 验证

- 后端测试 851/851 通过

### 状态

**已完成** ✅

---

## Round 3 — 代码质量修复（main.py NODE_ENV + DEV-007 日志增强）（2026-07-22）

### 聚焦维度

**代码质量** — 继续清除 issues_dev.json 中已验证的剩余问题。

### 改进

1. **修复 main.py 两处 NODE_ENV 兜底** — main.py:154 (`parse_cors_origins`) 和 main.py:219 (FastAPI docs gate) 使用 `os.getenv("ENV", os.getenv("NODE_ENV", "development"))`，绕过 `config.settings.ENVIRONMENT`。当前端设定 `NODE_ENV=production` 时，CORS 会误判为生产环境、API 文档被隐藏。改为导入并使用 `ENVIRONMENT` 常量。
2. **DEV-007 QualityGate 日志增强** — writer_stages.py:372 的 `except Exception:` 中增加异常上下文 (`%s`, e)，使验证失败时可溯源，与 stage_proofread 中的已有模式一致。

### 修改文件

- `dashboard/backend/main.py` — 添加 `ENVIRONMENT` 导入，替换两处 NODE_ENV 兜底
- `skills/writer_stages.py` — QualityGate 异常日志添加上下文

### 验证

- 后端测试 851/851 通过

### 状态

**已完成** ✅
