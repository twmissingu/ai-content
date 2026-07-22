# Changelog

## [0.9.12] - 2026-07-22

### Fixed

- **SSRF fail-closed**: DNS 解析失败时拒绝请求而非允许通过 (DEV-001)
- **审批写入顺序修复**: action 文件在 DB 更新后写入，消除不一致窗口 (DEV-002)
- **硬编码 Python 路径移除**: 改用 sys.executable 替代 .venv 硬编码 (DEV-003)
- **自我 import 移除**: skills/common.py 中函数体内 self-import 删除 (DEV-005)
- **QualityGate 日志增强**: 异常时记录具体错误上下文 (DEV-007)
- **NODE_ENV 兜底修复**: main.py CORS/docs 两处使用 config.settings.ENVIRONMENT 替代 NODE_ENV 兜底 (DEV-010)
- **API_BASE 去重**: 统一为 utils/api.ts 共享常量 (DEV-008)
- **.env 加载去重**: 提取 _load_env_file 辅助函数 (DEV-009)
- **Transition 警告消除**: ErrorBoundary 移出 Transition 包裹层 (R1)
- **TopicsView 单根节点**: 兼容 Vue Transition 要求 (R1)

### Security

- **Prompt injection safety 恢复**: writer_stages 中去除明确的 injection_safety=False (DEV-006)

### Changed

- **pyproject.toml 版本同步**: 从 0.8.0 更新至 0.9.12

## [0.9.8] - 2026-06-06

### Monitoring (2)

- **系统监控端点**: 添加 `/api/metrics` 端点，返回 uptime、队列大小、预算、磁盘等系统指标
- **人类可读摘要**: 添加 `/api/metrics/summary` 端点，提供快速诊断信息

### Accessibility (1)

- **屏幕阅读器测试清单**: 创建 `docs/SCREEN_READER_TESTING.md`，包含 10 个标准化测试场景

### Test Coverage (1)

- **监控端点测试**: 添加 8 个新测试用例覆盖 `/api/metrics` 和 `/api/metrics/summary`

## [0.9.7] - 2026-06-06

### Accessibility (1)

- **屏幕阅读器测试清单**: 创建 NVDA/VoiceOver 手动测试清单，覆盖 10 个主要场景

## [0.9.6] - 2026-06-06

### Test Coverage (2)

- **writer_helpers 单元测试**: 添加 15 个新测试用例覆盖提取的独立函数
- **测试兼容性修复**: 修复 monkeypatch 以支持 writer_helpers 模块

## [0.9.5] - 2026-06-06

### Code Quality (3)

- **writer_helpers 模块提取**: 将 CLI 解析、批评循环、输出写入等逻辑提取为独立函数
- **WriterAgent 重构**: 从 561 行减至 449 行 (-20%)
- **职责分离**: 纯函数更易测试，提升可维护性

## [0.9.4] - 2026-06-06

### Performance Optimization (1)

- **性能优化验证**: 确认数据库 WAL 模式、查询缓存（LRU + TTL）、复合索引、线程本地连接、busy_timeout 等优化已就位

### User Experience Improvements (3)

- **aria-live 播报**: Toast 通知自动播报给屏幕阅读器 (`composables/useToast.ts`)
- **aria-label 补全**: 修复 toast 关闭按钮和配置编辑器关闭按钮的 aria-label
- **focus trap 验证**: 确认 ConfirmDialog 和 ImageGallery 已有实现

### Code Quality (2)

- 删除 3 个 DEPRECATED 模块（writer_xhs, writer_douyin, publisher_toutiao）
- WriterAgent 拆分为 4 个独立方法

### Test Coverage (3)

- 为 3 个核心视图添加组件测试（PipelineView, ApprovalView, TopicsView）
- 前端测试用例数从 48 增加到 69（+21）
- 建立了前端组件测试的标准模式

### Deployment (1)

- 创建 GitHub Actions CI 工作流（.github/workflows/ci.yml）
- 添加后端测试 CI（Python 3.14 + pytest）
- 添加前端测试 CI（Node.js 20 + vitest）
- 添加 Docker 构建 CI（Docker Buildx + 缓存）

### Test Results

- 后端: 807 tests passing
- 前端: 69 tests passing
- 总计: 876 tests passing

## [0.9.3] - 2026-06-06

### User Experience Improvements (3)

- **aria-live 播报**: Toast 通知自动播报给屏幕阅读器 (`composables/useToast.ts`)
- **aria-label 补全**: 修复 toast 关闭按钮和配置编辑器关闭按钮的 aria-label
- **focus trap 验证**: 确认 ConfirmDialog 和 ImageGallery 已有实现

### Code Quality (2)

- 删除 3 个 DEPRECATED 模块（writer_xhs, writer_douyin, publisher_toutiao）
- WriterAgent 拆分为 4 个独立方法

### Test Coverage (3)

- 为 3 个核心视图添加组件测试（PipelineView, ApprovalView, TopicsView）
- 前端测试用例数从 48 增加到 69（+21）
- 建立了前端组件测试的标准模式

### Deployment (1)

- 创建 GitHub Actions CI 工作流（.github/workflows/ci.yml）
- 添加后端测试 CI（Python 3.14 + pytest）
- 添加前端测试 CI（Node.js 20 + vitest）
- 添加 Docker 构建 CI（Docker Buildx + 缓存）

### Test Results

- 后端: 807 tests passing
- 前端: 69 tests passing
- 总计: 876 tests passing

## [0.8.1] - 2026-06-05

### Security Fixes (2)

- SSRF protection `fail-open` vulnerability fixed — `_SSRFSafeTransport` now validates redirect targets before following (`routes/reader.py`)
- Approval action file no longer written when DB recording fails (DEV-002) — prevents orphan action files with no corresponding DB state (`routes/approval.py`)

### New Features (1)

- **Timeout auto-handling**: Topic 30 min unconfirmed → auto-select highest score; Approval 2 hour unresponsive → auto-skip (`background.py` `topic_timeout_target` + `approval_timeout_target`)
- Feishu alerts for topic/approval timeouts

### Review Findings Fixed (6)

- 6 audit findings resolved across codebase (quality gates key normalization, DEPLOYMENT env variable, video distribution config)

### UX Improvements (12)

- ApprovalView: publish panel, queue table, version panel component extraction
- PipelineView: status cards, trigger panel component extraction
- ErrorBoundary component for global error handling
- SkeletonLoader component for loading states
- ReaderPanel, ResizablePanel, ImageGallery improvements
- StatusBadge: design system alignment
- ConfigView, DataView, KbView, SourcesView refinements
- Dashboard store and API utility improvements

### Architecture

- New `skills/writer_stages.py` — extracted writer pipeline stages from `writer.py`
- New `skills/tts.py` — MiMo-V2.5-TTS voice synthesis module
- Database `manual_reviews.py` module for human review records

### Test Improvements

- New `tests/test_reader_ssr.py` — SSRF protection test coverage
- Updated `tests/test_background.py` — timeout auto-handling tests
- Updated `tests/test_api_approval.py` — DEV-002 fix coverage
- Updated `tests/test_llm.py`, `tests/test_main.py`, `tests/test_writer_unit.py`
- Total: 845 tests passing

## [0.8.0] - 2026-06-02

### AI Image Generation (Agnes)

- Replace HTML card screenshots with Agnes AI image generation (`skills/writer_illustration.py`)
- LLM-powered image prompt generation stage with `config/prompts/image_prompt_gen.md`
- `config/image_styles.json` — 8 content types × visual style presets
- Parallel Agnes subprocess calls via `ThreadPoolExecutor`
- Illustration count controlled by `writing_styles.json` per platform/content-type

### Phase 4: Video Generation

- New `skills/writer_video.py` — LLM prompt → Agnes async video generation (up to 15 min polling)
- New `config/prompts/video_prompt_gen.md` — video prompt template
- `config/settings.py` adds `VIDEOS_DIR`
- `writing_styles.json` adds `videos` field (enabled for `douyin_default`)
- `agent_schemas.py` `ArticleDraft` adds `videos`/`video_prompts`/`video_generation_method`
- Writer pipeline Stage 7b: optional video generation after illustration
- 15 new tests in `tests/test_writer_video.py`

### Publishing Overhaul

- New `skills/publisher_webbridge.py` — Kimi WebBridge browser automation for Xiaohongshu/Douyin
- WeChat publishing passes `--cover` and `--image` to baoyu-post-to-wechat
- Parallel multi-platform publishing via `ThreadPoolExecutor`
- AiToEarn MCP kept as fallback for kuaishou/shipinhao
- New `skills/platform_adapters.py` — platform-specific content adaptation
- New `POST /api/approval/publish` endpoint
- New `ImageGallery.vue` component with lightbox in ApprovalView

### Scout Enhancements

- New `skills/scout_collectors.py` — modular source collectors
- New `skills/scout_scorer.py` — extracted scoring logic
- New `skills/scout_dedup.py` — deduplication module
- New `skills/rss_collector.py` — RSS pre-collection system
- New `skills/topic_analyzer.py` — topic analysis
- Source collection parallelized (3.5 min → ~30 s)

### Security Fixes (8)

- WebSocket auth moved from URL query param to first message
- Production/staging env forces `API_KEY` requirement
- FTS5 query escaping strips boolean operators
- `target_id` validation in background dispatcher
- Prompt sanitization adds NFKD unicode normalization
- WebBridge action parameter validation
- Subprocess prompt sanitization (null bytes, control chars, truncation)
- Static file serving with `check_dir=True`

### Performance Fixes (13)

- Critique LLM calls parallelized (scorer + critic concurrent)
- Approval queue reads only 500 chars instead of full file
- Topics pagination applied before JSON parsing
- `image_styles.json` loaded once instead of twice
- RSS cache uses hash index file instead of scanning all files
- Playwright browser reused across batch_convert files
- Scout scorer early exit on cold start check
- KB fallback search capped at 100 files
- Health endpoint uses generator instead of list materialization
- WebBridge replaces fixed sleep with adaptive polling
- `Cache-Control` headers on static image serving
- `RateLimiter` and WebSocket connection limit documented
- Dashboard `/api/images` static file serving for generated images

### Architecture Fixes (9)

- `load_prompt()` tries `.md` then `.txt` extensions
- Hardcoded paths configurable via env vars (`AGNES_SCRIPT_PATH`, `WEBBRIDGE_URL`)
- Unused imports removed from 5 files
- Orphaned modules marked DEPRECATED
- Exception catches narrowed in `writer_illustration`
- Logging standardized to `get_agent_logger()`
- Schedule config deduplication
- `sys.path` manipulation removed from `rss_collector`
- `WriterAgent` god class documented with TODO

### Test Improvements

- New `tests/test_writer_video.py` (15 tests)
- New `tests/test_rss_collector.py`, `tests/test_topic_analyzer.py`, `tests/test_platform_adapters.py`
- New `tests/test_publisher_webbridge.py`, `tests/test_publisher_toutiao.py`
- New `tests/test_screenshot.py`, `tests/test_writer_xhs.py`, `tests/test_writer_douyin.py`
- New `tests/test_api_sources.py`, `tests/test_api_prompts.py`, `tests/test_api_traces.py`
- Total: 721 tests passing

## [0.7.0] - 2026-05-28

### Frontend UX Upgrade

- **PipelineView**: Failed agent retry button, sub-task progress bars, inline error display
- **ApprovalView**: Keyboard shortcut hint bar, platform tags, empty state guidance links
- **DataView**: Chart.js professional charts replacing CSS hand-drawn bar charts, new article/topic stats cards
- **App.vue**: Connection status indicator, notification bell (pending approval count), header layout optimization
- **Dashboard Store**: Request retry with exponential backoff, connection state tracking
- **Accessibility**: Global `:focus-visible` styles, focus trap in ConfirmDialog, DOMPurify XSS sanitization on markdown rendering, touch target minimum sizes (32px), `aria-hidden` on decorative elements
- **Dark mode**: Fixed hardcoded colors, all use CSS variables for theme compatibility
- **Error states**: User-facing error banners with retry buttons on TopicsView, KbView, PipelineView

### Security Hardening

- API Key uses `hmac.compare_digest` for timing-safe comparison
- Rate limiter adds `_MAX_CLIENTS` eviction to prevent memory leak
- Failed actions correctly moved to `FAILED_DIR` instead of `PROCESSED_DIR`
- HTTPException messages sanitized — no internal details leaked to clients
- CORS origins restricted to localhost by default (configurable via `CORS_ORIGINS`)

### Architecture Optimization

- **Database package split**: `database.py` → `database/` package with 7 domain modules (core, sessions, versions, tokens, config_ops, traces, prompts)
- **WebSocket real-time push**: `ws.py` — `ConnectionManager` polls status files every 3s, broadcasts changes to connected clients
- **Batch trace queries**: `get_trace_summaries_batch()` replaces N+1 pattern in sessions endpoint
- Removed all 17 `sys.path.insert` — now uses `pyproject.toml` + `pip install -e .`
- FTS5 search fixed double tokenization (jieba + trigram conflict)
- AI-slop patterns externalized to `config/proofread_patterns.json`
- Background actions reuse `skills/action.py` protocol

### New Features

- **Prompt version management**: CRUD API for prompt templates (`/api/prompts`), database-backed versioning, import from `config/prompts/*.txt`
- **Pipeline traces**: Execution trace API (`/api/pipeline/traces`) — per-stage timing, token usage, error tracking
- **Quality gates configuration**: `config/quality_gates.json` with configurable thresholds (proofread: 60, critique: 70, title: 75)
- **Quality flywheel**: `GET /api/config/quality-flywheel` — analyzes approval history to recommend threshold adjustments
- **Config API**: Schedule, writing styles, quality gates, sources, budget — all configurable via REST API

### Agent Improvements

- Writer pipeline integrates quality gate thresholds from `config/quality_gates.json`
- Scout trace fallback uses `except Exception` instead of `except ImportError`
- Writer removed redundant `import re` inside `_sanitize_text`
- Trace completion failure logged at debug level (non-fatal)

### Testing

- 390+ tests passing
- Coverage: 76% → 80%+
- New test files: `test_api_data.py`, `test_api_config.py`, `test_api_kb.py`, `test_api_traces.py`, `test_api_approval.py`, `test_search.py`, `test_feishu.py`, `test_background.py`
- Three-role deep review: PM, Full-stack Engineer, UI/UX Designer perspectives

### Cleanup

- Deleted 13 redundant files (scan_actions.py/sh, run_*.sh, formatting*.md, .env.example, etc.)

---

## [0.6.0] - 2026-05-28

### Architecture Improvements

- **All Agents migrated to AgentBase**:
  - `skills/writer.py`: Full rewrite using `WriterAgent(AgentBase)` class
  - `skills/publisher.py`: Full rewrite using `PublisherAgent(AgentBase)` class
  - `skills/feedback.py`: Full rewrite using `FeedbackAgent(AgentBase)` class
  - All agents now use unified status writing, logging, and metrics

### Security Fixes

- **Command-line Injection Prevention**: Publisher now uses temp files instead of command-line args for content passing
  - WeChat publishing: content written to temp file, passed via `--file` flag
  - AiToEarn publishing: params written to temp JSON file, passed via `--params-file` flag
  - Temp files are cleaned up in `finally` blocks

### Performance Improvements

- **Playwright Batch Screenshots**: Writer now reuses browser instance for multiple screenshots
  - 3 screenshots: ~6-9s → ~3-4s (50%+ faster)
  - Single `with sync_playwright()` context for all screenshots
  - Browser instance shared across all illustration generations
- **Database Query Cache**: Added `@cached_query` decorator with TTL support
  - `get_pipeline_sessions()` now cached for 10 seconds
  - Cache automatically invalidated on write operations
  - Thread-safe with proper locking

### New Features

- **Performance Metrics Module** (`skills/metrics.py`):
  - `AgentMetrics` class for collecting agent performance data
  - Tracks: LLM calls, token usage, stage durations, errors
  - Auto-saves to `data/metrics/` directory
  - Integrated into `AgentBase` with `start_stage()`, `end_stage()`, `record_llm_call()`
- **Log Rotation**: All agent logs now support file rotation
  - Default: 10MB per file, 5 backup files
  - Logs written to `data/logs/{agent_name}.log`
  - Configurable via `get_agent_logger()` parameters
- **API Rate Limiting**: FastAPI middleware limits requests to 120/minute per IP
  - Health check endpoint exempt from rate limiting
  - Returns 429 status with error message when exceeded
- **Markdown Preview**: Approval view now renders article preview as formatted Markdown
  - Uses `marked` library for rendering
  - Styled with `.markdown-body` CSS class
  - Supports headings, lists, code blocks, links, etc.

### Frontend Improvements

- **PipelineView Dynamic Timeline**: Timeline now reads from config instead of hardcoded values
  - Morning/evening schedule from `store.config.schedule`
  - Fallback to defaults if config not loaded
- **ApprovalView Markdown Rendering**: Article preview now renders Markdown with proper styling

### Testing

- **Integration Tests** (`tests/test_integration.py`):
  - `TestWriterIntegration`: Tests article creation, low quality handling
  - `TestPublisherIntegration`: Tests article finding
  - `TestFeedbackIntegration`: Tests article collection from history
  - `TestCommonIntegration`: Tests atomic writes, file locking

## [0.5.0] - 2026-05-28

### Architecture Improvements

- **skills/common.py**: New shared utilities module with:
  - `atomic_write_json()` / `atomic_write_text()`: Atomic file operations with fsync
  - `file_lock()`: File-based locking mechanism
  - `AgentBase`: Base class for all agents with unified status writing
  - Input validation functions (`validate_source`, `validate_platform`, `validate_action`)
  - `sanitize_filename()`: Path traversal prevention
  - `mask_api_key()`: API key masking for safe logging
  - `safe_subprocess_args()`: Subprocess injection prevention
  - Structured JSON logging with `get_agent_logger()`

### Security Fixes

- **CORS Configuration**: Added validation and production warnings for wildcard origins
- **API Key Masking**: All logs now mask API keys (show first/last 4 chars only)
- **Subprocess Injection**: Added whitelist validation for all subprocess calls in scout.py
- **Input Validation**: Added validation for source names, platform names, and action types

### Thread Safety

- **skills/llm.py**: Complete rewrite for thread safety:
  - Replaced global variables with `threading.local()` for per-thread state
  - Added `threading.Lock()` for shared resources (HTTP client, CSV writes)
  - HTTP client now uses singleton manager with proper locking
  - All agent-specific state is now thread-isolated
- **dashboard/backend/database.py**: 
  - Thread-local database connections
  - Thread-safe query cache with proper locking
  - Added `_invalidate_cache()` for write operations

### Performance Improvements

- **skills/scout.py**: Concurrent LLM scoring with ThreadPoolExecutor:
  - 5 parallel workers for topic scoring
  - Progress tracking for concurrent operations
  - Proper error handling per thread
- **dashboard/backend/database.py**: Query optimization:
  - Added pagination support (`limit`, `offset`)
  - Added field selection to reduce data transfer
  - Added simple query cache with TTL
  - Changed PRAGMA synchronous to NORMAL for better WAL performance

### Code Quality

- **Structured Logging**: All modules now use `logging.getLogger()` with JSON formatting
- **Error Handling**: Consistent error handling patterns across all agents
- **Type Annotations**: Improved type hints in common.py and llm.py

### Frontend Improvements

- **dashboard/frontend/src/stores/dashboard.ts**: Complete TypeScript rewrite:
  - Full type definitions for all data structures
  - `AgentStatus`, `ApprovalArticle`, `Topic`, `BudgetStatus` interfaces
  - Per-operation loading states with `isLoading()` helper
  - Computed properties (`pendingCount`, `isAgentRunning`)
  - Error handling with auto-dismiss
- **dashboard/frontend/src/App.vue**: 
  - Global error toast with auto-dismiss (5s)
  - Page Visibility API for efficient polling (only poll when visible)
- **dashboard/frontend/src/views/ApprovalView.vue**:
  - Per-article loading states
  - Disabled buttons during processing
  - Loading spinners for approve/reject actions

### Testing

- **tests/test_common.py**: 30+ unit tests for common utilities:
  - Atomic file operations
  - File locking
  - Input validation
  - Filename sanitization
  - API key masking
  - Subprocess argument validation
  - AgentBase functionality
- **tests/test_scout.py**: 15+ unit tests for Scout utilities:
  - Topic similarity detection
  - Deduplication and filtering
  - Score calculation formulas
  - Diversity enforcement
  - Allowed sources configuration

## [0.4.0] - 2026-05-27

### UI/UX Improvements

- **Design System**: Created unified CSS design system with variables for colors, spacing, typography, shadows, and transitions
- **App.vue**: Redesigned header and navigation with sticky positioning, smooth transitions, and approval badge
- **PipelineView**: Enhanced with timeline visualization, budget status card, and improved agent cards
- **ApprovalView**: Better article cards with expandable preview, improved reject form, and empty states
- **TopicsView**: Redesigned score badge, score breakdown visualization, and hover effects
- **DataView**: Added stats cards grid, improved chart with tooltips, and loading states
- **KbView**: New search interface with section filters, result cards, and initial state guidance
- **StatusBadge**: Refactored with design system variables, multiple sizes, and hover effects

### Technical

- **design-system.css**: Created comprehensive CSS design system with 520+ lines covering:
  - Color variables (primary, semantic, neutral)
  - Spacing scale (xs to 4xl)
  - Typography scale (xs to 5xl)
  - Shadow system (sm to xl)
  - Transition timing (fast, normal, slow)
  - Border radius scale (sm to full)
  - Layout constants (header, nav, content widths)
  - Global reset and base styles
  - Utility classes for buttons, cards, badges
  - Loading and animation utilities
- All components now use CSS variables from design system
- Consistent spacing, typography, and color usage across all views
- Improved responsive design for mobile devices
- Better loading and empty state handling
- Store updated with budget tracking and error handling
- **Fixed**: setInterval memory leak in App.vue (cleanup on unmount)
- **Fixed**: Store loading state now properly used in all fetch operations
- **Fixed**: fetchSections error handling with loading state
- **Fixed**: TypeScript warnings - removed unused imports and variables

## [0.3.1] - 2026-05-27

### Security

- **skills/publisher_toutiao.py**: Fix XSS vulnerability — use JSON serialization for Playwright evaluate
- **dashboard/backend/main.py**: Use threading.Event for safe thread shutdown

### Fixed

- **dashboard/backend/database.py**: Fix FTS5 tokenizer — change from unicode61 to trigram for Chinese support
- **dashboard/backend/main.py**: Enhanced health check with service status and search index info
- **dashboard/backend/main.py**: Add Pydantic request validation for token logging
- **dashboard/backend/config_service.py**: Improve config save error handling with atomic writes
- **dashboard/frontend/src/stores/dashboard.ts**: Make API base URL configurable via environment variable

### Added

- **requirements.txt**: Python dependencies for Docker and local installation

## [0.3.0] - 2026-05-27

### Security

- **dashboard/backend/main.py**: Fix CORS configuration — restrict to localhost origins only (configurable via CORS_ORIGINS env var)
- **dashboard/backend/main.py**: Bind uvicorn to 127.0.0.1 instead of 0.0.0.0

### Fixed

- **dashboard/backend/main.py**: Add shutdown flag for budget monitor thread
- **dashboard/backend/main.py**: Fix pipeline timeline schema inconsistency between database and filesystem sources
- **dashboard/backend/main.py**: Add warning response when database approval recording fails
- **dashboard/backend/database.py**: Fix check_budget_limit to read budget from configuration
- **dashboard/backend/search.py**: Add FTS5 query escaping to prevent injection
- **dashboard/backend/config_service.py**: Simplify schedule update to apply immediately

### Added

- **dashboard/backend/database.py**: SQLite database layer with 5 core tables (pipeline_sessions, platform_versions, approval_records, token_usage, config_entries)
- **dashboard/backend/database.py**: FTS5 virtual table for knowledge base search
- **dashboard/backend/database.py**: Budget control functions (check_budget_limit, get_monthly_cost)
- **dashboard/backend/search.py**: Knowledge base search service with jieba Chinese tokenization
- **dashboard/backend/search.py**: Auto-indexing on startup with incremental updates
- **dashboard/backend/feishu.py**: Feishu webhook notification module with card messages
- **dashboard/backend/config_service.py**: Configuration management service with dual-version preview
- **dashboard/backend/config_service.py**: Writing style prompt generation
- **dashboard/backend/config_service.py**: Budget, quality gates, source configuration management
- **scripts/watchdog.sh**: Enhanced watchdog with Feishu alerts and auto-restart
- **tests/**: Unit test framework with pytest (test_database.py, test_config.py)
- **Dockerfile**: Docker support for containerized deployment
- **docker-compose.yml**: Docker Compose with watchdog service
- **requirements-test.txt**: Test dependencies
- **pytest.ini**: Pytest configuration

### Changed

- **dashboard/backend/main.py**: Integrate SQLite database for all data operations
- **dashboard/backend/main.py**: Use FTS5 search instead of simple string matching
- **dashboard/backend/main.py**: Add budget monitoring background thread
- **dashboard/backend/main.py**: Enhanced health check with database status
- **dashboard/backend/main.py**: New API endpoints for configuration management
- **skills/llm.py**: Add agent tracking for token usage (set_current_agent)
- **skills/llm.py**: Log token usage to both CSV and SQLite database
- **skills/scout.py**: Set current agent name for token tracking
- **skills/writer.py**: Set current agent name for token tracking
- **config/settings.py**: Add Feishu webhook and notification settings

## [0.2.0] - 2026-05-26

### Fixed

- **writer.py**: Fix `critique_scores` uninitialized variable crash (NameError)
- **writer.py**: Fix rewrite mode topic field lookup for pending/ fallback path
- **scripts/scan_actions.py**: Replace relative paths with absolute PROJECT_ROOT paths

### Changed

- **llm.py**: Implement `config/model_fallback.json` fallback chain — auto-retry with fallback models on primary failure
- **AGENTS.md**: Update status from "pre-development" to reflect Phase 2 code
- **development-plan.md**: Sync status with actual codebase
- **PRD.md**: Fix port numbers (3456→8710) to match actual implementation

### Added

- **publisher.py**: Add shipinhao (视频号) AiToEarn dispatch support
- **feedback.py**: Populate `topic_directions` from article meta for viral analysis

### Removed

- **config/schedule.json**: Remove unused `morning_topic_selected`/`evening_topic_selected` fields

## [0.1.0] - 2026-05-25

### Added

- Scout Agent — multi-channel topic discovery + two-layer LLM scoring + diversity enforcement
- Writer Agent — 7-stage pipeline (fetch → draft → proofread → critique → format → titles → illustrate)
- Writer Router — parallel multi-platform distribution (WeChat + Xiaohongshu + Douyin)
- Writer Workers — platform-specific writers (wechat, xiaohongshu, douyin)
- Publisher Agent — dispatch to WeChat (baoyu) + AiToEarn platforms
- Publisher Toutiao — Playwright browser automation for Toutiao draft box
- Feedback Agent — daily data recovery, viral pattern detection, strategy generation
- Knowledge Agent — article archiving to kb/, topic index updates
- FastAPI Dashboard backend — 6 API route groups + background action scanner
- Vue 3 Dashboard frontend — 5 views (pipeline, approval, topics, data, kb)
- Queue protocol — JSON file system agent communication with atomic writes
- Lightning Talk HTML → PNG screenshot pipeline
- Schedule management, cost tracking, model fallback configuration
