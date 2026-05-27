# Changelog

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
