"""Common utilities for all agents.

Provides:
- Unified agent status writing with atomic file operations
- Structured JSON logging with agent context and log rotation
- Error handling decorators
- Input validation helpers
- Secure file operations with locking
- Performance metrics collection

Usage:
    from skills.common import AgentBase, agent_main, validate_source
    
    class ScoutAgent(AgentBase):
        name = "scout"
        
        def run(self):
            self.write_status("collecting", 10, "Starting...")
            # ... agent logic
    
    if __name__ == "__main__":
        agent_main(ScoutAgent)
"""

import functools
import json
import logging
import logging.handlers
import os
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Union

from config.settings import STATUS_DIR, FAILED_DIR, DATA_DIR

# Import metrics (lazy to avoid circular imports)
_metrics_module = None

def _get_metrics_module():
    global _metrics_module
    if _metrics_module is None:
        from skills import metrics
        _metrics_module = metrics
    return _metrics_module

# ═══════════════════════════════════════════════════════════════════════
# Structured Logging
# ═══════════════════════════════════════════════════════════════════════

class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "agent": getattr(record, 'agent', 'unknown'),
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)
        if hasattr(record, 'extra_data'):
            log_data["data"] = record.extra_data
        return json.dumps(log_data, ensure_ascii=False)


def get_agent_logger(
    agent_name: str,
    log_dir: Optional[Path] = None,
    enable_file_logging: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.LoggerAdapter:
    """Get a logger with agent context, supporting both console and file output with rotation.
    
    Args:
        agent_name: Name of the agent (used in log format and filename)
        log_dir: Directory for log files (default: data/logs/)
        enable_file_logging: Whether to enable file logging
        max_bytes: Max size per log file before rotation
        backup_count: Number of backup files to keep
    """
    logger = logging.getLogger(f"gaoding.{agent_name}")
    
    # Only add handlers once
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Console handler (stdout)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(JSONFormatter())
        logger.addHandler(console_handler)
        
        # File handler with rotation (optional)
        if enable_file_logging:
            if log_dir is None:
                log_dir = DATA_DIR / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_dir / f"{agent_name}.log",
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(JSONFormatter())
            logger.addHandler(file_handler)
    
    return logging.LoggerAdapter(logger, {'agent': agent_name})


# ═══════════════════════════════════════════════════════════════════════
# Prompt Template Loader
# ═══════════════════════════════════════════════════════════════════════

def load_prompt(template_name: str, **kwargs) -> str:
    """Load a prompt template from config/prompts/ and format with kwargs.

    Args:
        template_name: Template filename (without .txt extension)
        **kwargs: Variables to substitute in the template

    Returns:
        Formatted prompt string
    """
    from config.settings import CONFIG_DIR
    template_path = CONFIG_DIR / "prompts" / f"{template_name}.txt"
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")
    template = template_path.read_text(encoding="utf-8")
    return template.format(**kwargs)


# ═══════════════════════════════════════════════════════════════════════
# Atomic File Operations
# ═══════════════════════════════════════════════════════════════════════

def atomic_write_json(path: Path, data: dict, indent: int = 2) -> None:
    """Write JSON data atomically with fsync.
    
    Uses temp file + rename pattern with explicit fsync to ensure
    data is persisted before rename completes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to temp file
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp"
    )
    
    try:
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        
        # Atomic rename (same filesystem)
        os.rename(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_text(path: Path, content: str, encoding: str = 'utf-8') -> None:
    """Write text data atomically with fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp"
    )
    
    try:
        with os.fdopen(tmp_fd, 'w', encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        
        os.rename(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


@contextmanager
def file_lock(lock_path: Path, timeout: float = 30.0):
    """Simple file-based lock using mkdir (atomic on most filesystems).
    
    Usage:
        with file_lock(path.with_suffix('.lock')):
            # critical section
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    start_time = time.monotonic()
    
    while True:
        try:
            os.mkdir(lock_path)
            break
        except FileExistsError:
            if time.monotonic() - start_time > timeout:
                raise TimeoutError(f"Could not acquire lock: {lock_path}")
            time.sleep(0.1)
    
    try:
        yield
    finally:
        try:
            os.rmdir(lock_path)
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════════════
# Agent Base Class
# ═══════════════════════════════════════════════════════════════════════

class AgentBase:
    """Base class for all agents with common functionality.
    
    Features:
    - Atomic status writing
    - Structured logging with rotation
    - Performance metrics collection
    - Error handling
    """
    
    name: str = "unknown"
    version: str = "1.0.0"
    
    def __init__(self, enable_metrics: bool = True):
        self.logger = get_agent_logger(self.name)
        self._start_time = datetime.now(timezone.utc)
        self._start_timestamp = self._start_time.strftime("%Y%m%d_%H%M%S")
        self._status_path = STATUS_DIR / f"{self.name}.json"
        self._lock = threading.Lock()
        
        # Metrics
        self._enable_metrics = enable_metrics
        self._metrics = None
        if enable_metrics:
            try:
                metrics_mod = _get_metrics_module()
                self._metrics = metrics_mod.AgentMetrics(self.name)
            except Exception:
                self._metrics = None
    
    @property
    def metrics(self):
        """Get the metrics collector."""
        return self._metrics
    
    def start_stage(self, stage_name: str) -> None:
        """Start timing a pipeline stage (metrics)."""
        if self._metrics:
            self._metrics.start_stage(stage_name)
    
    def end_stage(self, stage_name: str) -> float:
        """End timing a pipeline stage. Returns duration in seconds."""
        if self._metrics:
            return self._metrics.end_stage(stage_name)
        return 0.0
    
    def record_llm_call(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        duration: float = 0.0,
        success: bool = True
    ) -> None:
        """Record an LLM API call."""
        if self._metrics:
            self._metrics.record_llm_call(input_tokens, output_tokens, duration, success)
    
    def write_status(
        self,
        stage: str,
        progress_pct: int,
        detail: str,
        error: Optional[str] = None,
        **extra
    ) -> None:
        """Write agent status atomically."""
        status = {
            "agent": self.name,
            "stage": stage,
            "progress_pct": min(max(progress_pct, 0), 100),
            "detail": detail,
            "started_at": self._start_timestamp,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "error": error,
            **extra
        }
        
        with self._lock:
            atomic_write_json(self._status_path, status)
    
    def write_completed(
        self,
        detail: str,
        save_metrics: bool = True,
        **extra
    ) -> None:
        """Write completion status and optionally save metrics."""
        self.write_status(
            stage="completed",
            progress_pct=100,
            detail=detail,
            completed_at=datetime.now(timezone.utc).isoformat(),
            **extra
        )
        
        # Save metrics
        if save_metrics and self._metrics:
            try:
                metrics_path = self._metrics.save()
                self.logger.info(f"Metrics saved to: {metrics_path}")
            except Exception as e:
                self.logger.warning(f"Failed to save metrics: {e}")
    
    def write_error(
        self,
        error: str,
        detail: str = "",
        save_metrics: bool = True,
        **extra
    ) -> None:
        """Write error status and optionally save metrics."""
        self.write_status(
            stage="error",
            progress_pct=0,
            detail=detail or f"Error: {error}",
            error=error,
            **extra
        )

        # Record error in metrics
        if self._metrics:
            self._metrics.record_error("unknown", error)

        # Save metrics
        if save_metrics and self._metrics:
            try:
                self._metrics.save()
            except Exception:
                pass
    
    def write_failed_action(
        self,
        target_id: str,
        platform: str,
        error: str,
        meta: Optional[dict] = None
    ) -> Path:
        """Record a failed action for later analysis."""
        FAILED_DIR.mkdir(parents=True, exist_ok=True)
        
        failed = {
            "target_id": target_id,
            "platform": platform,
            "timestamp": self._start_timestamp,
            "error": error,
            "agent": self.name,
            "meta": meta or {},
        }
        
        filename = f"{self._start_timestamp}-{platform}.json"
        path = FAILED_DIR / filename
        atomic_write_json(path, failed)
        return path
    
    def run(self) -> None:
        """Main agent logic. Override in subclass."""
        raise NotImplementedError


F = TypeVar('F', bound=Callable)


def agent_error_handler(func: F) -> F:
    """Decorator to handle agent errors with logging and status updates.
    
    Catches exceptions, logs them, writes error status, and re-raises.
    """
    @functools.wraps(func)
    def wrapper(self: AgentBase, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except KeyboardInterrupt:
            self.logger.info("Agent interrupted by user")
            self.write_error("Interrupted by user")
            raise
        except Exception as e:
            self.logger.error(f"Agent failed: {e}", exc_info=True)
            self.write_error(str(e))
            raise
    return wrapper


def agent_main(agent_class: type, *args, **kwargs) -> None:
    """Main entry point for agents with error handling.
    
    Usage:
        if __name__ == "__main__":
            agent_main(ScoutAgent)
    """
    agent = agent_class(*args, **kwargs)
    
    try:
        agent.logger.info(f"Starting {agent.name} agent (v{agent.version})")
        agent.run()
        agent.logger.info(f"{agent.name} agent completed")
    except KeyboardInterrupt:
        agent.logger.info(f"{agent.name} interrupted")
        sys.exit(0)
    except Exception as e:
        agent.logger.error(f"{agent.name} failed: {e}", exc_info=True)
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════
# Input Validation
# ═══════════════════════════════════════════════════════════════════════

# Allowed source names for china-hot MCP
ALLOWED_SOURCES = frozenset({
    "weibo", "zhihu", "bilibili", "baidu", "douyin", 
    "toutiao", "kr36", "github", "rss", "web_search", "materials"
})

# Allowed platform names
ALLOWED_PLATFORMS = frozenset({
    "wechat", "xiaohongshu", "douyin", "kuaishou", 
    "toutiao", "baijiahao", "shipinhao"
})

# Allowed action types
ALLOWED_ACTIONS = frozenset({
    "confirm", "approve", "reject", "rewrite", "test_scout"
})


def validate_source(source: str) -> str:
    """Validate and return source name.
    
    Raises ValueError if source is not in allowed list.
    """
    if source not in ALLOWED_SOURCES:
        raise ValueError(f"Invalid source: {source}. Allowed: {ALLOWED_SOURCES}")
    return source


def validate_platform(platform: str) -> str:
    """Validate and return platform name."""
    if platform not in ALLOWED_PLATFORMS:
        raise ValueError(f"Invalid platform: {platform}. Allowed: {ALLOWED_PLATFORMS}")
    return platform


def validate_action(action: str) -> str:
    """Validate and return action type."""
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Invalid action: {action}. Allowed: {ALLOWED_ACTIONS}")
    return action


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """Sanitize filename to prevent path traversal and invalid characters."""
    # Remove path separators and null bytes
    sanitized = filename.replace('/', '_').replace('\\', '_').replace('\0', '')
    
    # Remove leading dots (hidden files)
    sanitized = sanitized.lstrip('.')
    
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # Ensure not empty
    if not sanitized:
        sanitized = "unnamed"
    
    return sanitized


def mask_api_key(key: Optional[str], show_chars: int = 4) -> str:
    """Mask API key for safe display in logs.
    
    Shows first and last N characters with **** in between.
    Returns "****" if key is None or too short.
    """
    if not key:
        return "****"
    if len(key) <= show_chars * 2:
        return "****"
    return f"{key[:show_chars]}****{key[-show_chars:]}"


# ═══════════════════════════════════════════════════════════════════════
# Subprocess Helpers
# ═══════════════════════════════════════════════════════════════════════

def safe_subprocess_args(args: list[str], allowed_binaries: Optional[set[str]] = None) -> list[str]:
    """Validate subprocess arguments to prevent injection.
    
    Args:
        args: Command arguments
        allowed_binaries: Set of allowed binary names (e.g., {"hermes", "curl"})
    
    Returns:
        Validated arguments
    
    Raises:
        ValueError: If binary is not in allowed list
    """
    if not args:
        raise ValueError("Empty command arguments")
    
    if allowed_binaries is None:
        allowed_binaries = {"hermes", "curl", "python3", "python", "npx", "node"}
    
    binary = Path(args[0]).name
    if binary not in allowed_binaries:
        raise ValueError(f"Binary not allowed: {binary}. Allowed: {allowed_binaries}")
    
    # Check for shell metacharacters in arguments
    dangerous_chars = set(';&|`$(){}[]!#~')
    for arg in args[1:]:
        if any(c in arg for c in dangerous_chars):
            # Allow JSON in --params arguments
            if args[args.index(arg) - 1] == '--params':
                try:
                    json.loads(arg)
                    continue
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Dangerous characters in argument: {arg[:50]}...")
    
    return args


# ═══════════════════════════════════════════════════════════════════════
# Convenience Functions (backward compatibility)
# ═══════════════════════════════════════════════════════════════════════

def write_status(
    agent: str,
    stage: str,
    progress_pct: int,
    detail: str,
    error: Optional[str] = None,
    started_at: Optional[str] = None,
    **extra
) -> None:
    """Write agent status (standalone function for backward compatibility)."""
    if started_at is None:
        started_at = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    status = {
        "agent": agent,
        "stage": stage,
        "progress_pct": min(max(progress_pct, 0), 100),
        "detail": detail,
        "started_at": started_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "error": error,
        **extra
    }
    
    path = STATUS_DIR / f"{agent}.json"
    atomic_write_json(path, status)
