"""Centralized configuration for the content production system.

All agent code reads settings from this module, never from env directly.
Auto-loads .env from project root if present (env vars take precedence).
"""

import os
import re
from pathlib import Path
from typing import Optional

# ── .env auto-loader ──────────────────────────────────────────────
def _load_env_dotfile() -> None:
    """Load .env from project root into os.environ (won't overwrite existing env vars)."""
    # Load Hermes global config first (project .env takes precedence)
    hermes_env = Path.home() / ".hermes" / ".env"
    if hermes_env.exists():
        with open(hermes_env) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip("\"'")
                if key and key not in os.environ:
                    os.environ[key] = val
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("\"'")
            # Don't overwrite env vars already set
            if key and key not in os.environ:
                os.environ[key] = val

_load_env_dotfile()

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
VIDEOS_DIR = QUEUE_DIR / "videos"
SOURCES_DIR = QUEUE_DIR / "sources"
TMP_DIR = QUEUE_DIR / "tmp"
KB_DIR = PROJECT_ROOT / "kb"
TOKENS_DIR = QUEUE_DIR / "tokens"
TRAIL_DIR = QUEUE_DIR / "trails"
RSS_CACHE_DIR: Path = QUEUE_DIR / "rss_cache"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
CONFIG_DIR = PROJECT_ROOT / "config"

# Ensure runtime directories exist
for _d in [ACTIONS_DIR, PROCESSED_DIR, FAILED_ACTIONS_DIR, STATUS_DIR, REVIEW_DIR,
           PENDING_DIR, FAILED_DIR, IMAGES_DIR, VIDEOS_DIR, SOURCES_DIR, TMP_DIR, LOGS_DIR,
           TOKENS_DIR, TRAIL_DIR, RSS_CACHE_DIR, QUEUE_DIR / "rss_candidates"]:
    _d.mkdir(parents=True, exist_ok=True)

# ── LLM Provider ───────────────────────────────────────────────────
LLM_BASE_URL: str = os.getenv(
    "LLM_BASE_URL",
    os.getenv("XIAOMI_BASE_URL", "https://api.xiaomimimo.com/v1"),
)
LLM_API_KEY: Optional[str] = os.getenv("XIAOMI_API_KEY")
LLM_MODEL: str = os.getenv("LLM_MODEL", "mimo-v2.5")
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "131072"))
LLM_CONTEXT_LENGTH: int = int(os.getenv("LLM_CONTEXT_LENGTH", "262144"))

# ── Schedules ──────────────────────────────────────────────────────
SCHEDULE_PATH: Path = CONFIG_DIR / "schedule.json"

# ── RSS Collector ───────────────────────────────────────────────────
RSSHUB_BASE_URL: str = os.getenv("RSSHUB_BASE_URL", "http://localhost:1200")
WEWE_RSS_BASE_URL: str = os.getenv("WEWE_RSS_BASE_URL", "http://localhost:4000")
RSS_COLLECTOR_INTERVAL: int = int(os.getenv("RSS_COLLECTOR_INTERVAL", "30"))  # minutes
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

# ── Feishu notification ───────────────────────────────────────────
# ── Runtime environment ─────────────────────────────────────────────
ENVIRONMENT: str = os.getenv("ENV", os.getenv("NODE_ENV", "development"))
API_KEY: str = os.getenv("API_KEY", "")
TRUSTED_PROXIES: str = os.getenv("TRUSTED_PROXIES", "")
PARALLEL_WORKERS: str = os.getenv("PARALLEL_WORKERS", "1")

# ── Feishu notification ───────────────────────────────────────────
FEISHU_WEBHOOK_URL: Optional[str] = os.getenv("FEISHU_WEBHOOK_URL")
NOTIFICATION_QUIET_START: int = int(os.getenv("NOTIFICATION_QUIET_START", "22"))  # 22:00
NOTIFICATION_QUIET_END: int = int(os.getenv("NOTIFICATION_QUIET_END", "8"))      # 08:00
# NOTE: Quiet hours cross midnight (22→8). Use `hour >= start or hour < end` logic, NOT `start <= hour < end`.

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
