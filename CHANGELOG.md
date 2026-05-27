# Changelog

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
