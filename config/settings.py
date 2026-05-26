"""Centralized configuration for the content production system.

All agent code reads settings from this module, never from env directly.
Reads Hermes env vars at import time, falls back to defaults where safe.
"""

import os
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"
QUEUE_DIR = PROJECT_ROOT / "queue"
ACTIONS_DIR = QUEUE_DIR / "actions"
PROCESSED_DIR = ACTIONS_DIR / "processed"
FAILED_ACTIONS_DIR = ACTIONS_DIR / "failed"
STATUS_DIR = QUEUE_DIR / "status"
REVIEW_DIR = QUEUE_DIR / "review"
PENDING_DIR = QUEUE_DIR / "pending"
FAILED_DIR = QUEUE_DIR / "failed"
IMAGES_DIR = QUEUE_DIR / "images"
TMP_DIR = QUEUE_DIR / "tmp"
KB_DIR = PROJECT_ROOT / "kb"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
CONFIG_DIR = PROJECT_ROOT / "config"

# Ensure runtime directories exist
for _d in [ACTIONS_DIR, PROCESSED_DIR, FAILED_ACTIONS_DIR, STATUS_DIR, REVIEW_DIR,
           PENDING_DIR, FAILED_DIR, IMAGES_DIR, TMP_DIR, LOGS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── LLM Provider ───────────────────────────────────────────────────
LLM_BASE_URL: str = os.getenv(
    "LLM_BASE_URL",
    "https://api.xiaomimimo.com/v1",
)
LLM_API_KEY: Optional[str] = os.getenv("XIAOMI_API_KEY")
LLM_MODEL: str = os.getenv("LLM_MODEL", "mimo-v2.5")
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "131072"))
LLM_CONTEXT_LENGTH: int = int(os.getenv("LLM_CONTEXT_LENGTH", "262144"))

# ── Schedules ──────────────────────────────────────────────────────
SCHEDULE_PATH: Path = CONFIG_DIR / "schedule.json"
DEFAULT_SCHEDULE = {
    "morning_scout": "09:00",
    "morning_writer": "09:30",
    "evening_scout": "14:00",
    "evening_writer": "14:30",
    "working_days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
}

# ── Writer defaults ────────────────────────────────────────────────
DOMAIN: str = "科技/AI"
TONE: str = "口语化"
STANCE: str = "强烈观点"
LENGTH: int = 2500          # target characters
QUALITY_THRESHOLD: int = 70  # 0-100 quality gate
MAX_REWRITE_ROUNDS: int = 3
STAGE_TIMEOUT_MINUTES: int = 15

# ── Agent defaults ─────────────────────────────────────────────────
SCOUT_SOURCE_WEIGHT: float = 1.0
MONTHLY_BUDGET_USD: float = 15.0
COST_WARN_PCT: float = 0.8

# ── Platform config ────────────────────────────────────────────────
PLATFORM_PRIORITY: list[str] = [
    "xiaohongshu",
    "wechat",
    "douyin",
    "kuaishou",
    "toutiao",
    "baijiahao",
]
PLATFORM_DISPLAY: dict[str, str] = {
    "xiaohongshu": "小红书",
    "wechat": "微信公众号",
    "douyin": "抖音",
    "kuaishou": "快手",
    "toutiao": "头条号",
    "baijiahao": "百家号",
}

# ── Helper ─────────────────────────────────────────────────────────
def require_api_key(name: str = "XIAOMI_API_KEY") -> str:
    """Return an API key or raise a clear error."""
    key = os.getenv(name)
    if not key:
        raise RuntimeError(
            f"Missing required env var: {name}. "
            f"Set it in ~/.hermes/.env or export it directly."
        )
    return key
