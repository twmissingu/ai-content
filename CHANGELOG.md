# Changelog

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
