"""Performance metrics collection for agents.

Collects and reports:
- LLM call counts and token usage
- Stage durations
- Error counts
- Overall pipeline duration

Usage:
    from skills.metrics import AgentMetrics
    
    metrics = AgentMetrics("writer")
    metrics.start_stage("draft")
    # ... do work
    metrics.end_stage("draft")
    metrics.record_llm_call(tokens=1500, duration=2.3)
    print(metrics.summary())
"""

import json
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DATA_DIR


@dataclass
class StageTiming:
    """Timing for a single pipeline stage."""
    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    
    def start(self):
        self.start_time = time.monotonic()
    
    def stop(self):
        self.end_time = time.monotonic()
        self.duration = self.end_time - self.start_time


class AgentMetrics:
    """Collects performance metrics for an agent run."""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.start_time = time.monotonic()
        self.start_datetime = datetime.now(timezone.utc)
        
        # LLM metrics
        self.llm_calls: int = 0
        self.llm_tokens_input: int = 0
        self.llm_tokens_output: int = 0
        self.llm_errors: int = 0
        self.llm_duration: float = 0.0
        
        # Stage metrics
        self._stages: dict[str, StageTiming] = {}
        self._current_stage: Optional[str] = None
        
        # Error tracking
        self.errors: list[dict] = []
        
        # Thread safety
        self._lock = threading.Lock()
    
    def start_stage(self, stage_name: str) -> None:
        """Start timing a pipeline stage."""
        with self._lock:
            timing = StageTiming(name=stage_name)
            timing.start()
            self._stages[stage_name] = timing
            self._current_stage = stage_name
    
    def end_stage(self, stage_name: str) -> float:
        """End timing a pipeline stage. Returns duration in seconds."""
        with self._lock:
            if stage_name in self._stages:
                self._stages[stage_name].stop()
                return self._stages[stage_name].duration
            return 0.0
    
    def record_llm_call(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        duration: float = 0.0,
        success: bool = True
    ) -> None:
        """Record an LLM API call."""
        with self._lock:
            self.llm_calls += 1
            self.llm_tokens_input += input_tokens
            self.llm_tokens_output += output_tokens
            self.llm_duration += duration
            if not success:
                self.llm_errors += 1
    
    def record_error(self, stage: str, error: str, details: Optional[dict] = None) -> None:
        """Record an error."""
        with self._lock:
            self.errors.append({
                "stage": stage,
                "error": error,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    
    @property
    def total_duration(self) -> float:
        """Total duration in seconds."""
        return time.monotonic() - self.start_time
    
    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.llm_tokens_input + self.llm_tokens_output
    
    def get_stage_durations(self) -> dict[str, float]:
        """Get durations for all completed stages."""
        return {
            name: timing.duration
            for name, timing in self._stages.items()
            if timing.duration > 0
        }
    
    def summary(self) -> dict:
        """Get a summary of all metrics."""
        return {
            "agent": self.agent_name,
            "started_at": self.start_datetime.isoformat(),
            "total_duration_seconds": round(self.total_duration, 2),
            "llm": {
                "calls": self.llm_calls,
                "input_tokens": self.llm_tokens_input,
                "output_tokens": self.llm_tokens_output,
                "total_tokens": self.total_tokens,
                "errors": self.llm_errors,
                "duration_seconds": round(self.llm_duration, 2),
            },
            "stages": {
                name: round(timing.duration, 2)
                for name, timing in self._stages.items()
            },
            "errors": self.errors,
            "error_count": len(self.errors),
        }
    
    def save(self, path: Optional[Path] = None) -> Path:
        """Save metrics to a JSON file."""
        if path is None:
            metrics_dir = DATA_DIR / "metrics"
            metrics_dir.mkdir(parents=True, exist_ok=True)
            timestamp = self.start_datetime.strftime("%Y%m%d_%H%M%S")
            path = metrics_dir / f"{self.agent_name}_{timestamp}.json"
        
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.summary(), ensure_ascii=False, indent=2))
        return path
    
    def __repr__(self) -> str:
        return (
            f"AgentMetrics(agent={self.agent_name}, "
            f"duration={self.total_duration:.1f}s, "
            f"llm_calls={self.llm_calls}, "
            f"tokens={self.total_tokens})"
        )


# Decorator for timing functions
def timed(metrics: AgentMetrics, stage_name: str):
    """Decorator to time a function and record in metrics."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            metrics.start_stage(stage_name)
            try:
                result = func(*args, **kwargs)
                metrics.end_stage(stage_name)
                return result
            except Exception as e:
                metrics.end_stage(stage_name)
                metrics.record_error(stage_name, str(e))
                raise
        return wrapper
    return decorator
