"""Unit tests for skills/metrics.py — performance metrics collection."""

import json
import time
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestStageTiming:
    """Test StageTiming dataclass."""

    def test_start_and_stop(self):
        from skills.metrics import StageTiming

        timing = StageTiming(name="draft")
        timing.start()
        time.sleep(0.01)
        timing.stop()

        assert timing.duration > 0
        assert timing.end_time > timing.start_time

    def test_initial_duration_is_zero(self):
        from skills.metrics import StageTiming

        timing = StageTiming(name="draft")
        assert timing.duration == 0.0


class TestAgentMetrics:
    """Test AgentMetrics class."""

    def test_initialization(self):
        from skills.metrics import AgentMetrics

        metrics = AgentMetrics("writer")
        assert metrics.agent_name == "writer"
        assert metrics.llm_calls == 0
        assert metrics.llm_tokens_input == 0
        assert metrics.llm_tokens_output == 0
        assert metrics.llm_errors == 0
        assert metrics.errors == []

    def test_start_and_end_stage(self):
        from skills.metrics import AgentMetrics

        metrics = AgentMetrics("writer")
        metrics.start_stage("draft")
        time.sleep(0.01)
        duration = metrics.end_stage("draft")

        assert duration > 0
        assert "draft" in metrics.get_stage_durations()

    def test_end_nonexistent_stage_returns_zero(self):
        from skills.metrics import AgentMetrics

        metrics = AgentMetrics("writer")
        duration = metrics.end_stage("nonexistent")
        assert duration == 0.0

    def test_record_llm_call(self):
        from skills.metrics import AgentMetrics

        metrics = AgentMetrics("writer")
        metrics.record_llm_call(input_tokens=100, output_tokens=200, duration=1.5)

        assert metrics.llm_calls == 1
        assert metrics.llm_tokens_input == 100
        assert metrics.llm_tokens_output == 200
        assert metrics.llm_duration == 1.5
        assert metrics.llm_errors == 0

    def test_record_llm_call_failure(self):
        from skills.metrics import AgentMetrics

        metrics = AgentMetrics("writer")
        metrics.record_llm_call(success=False)

        assert metrics.llm_calls == 1
        assert metrics.llm_errors == 1

    def test_record_multiple_llm_calls(self):
        from skills.metrics import AgentMetrics

        metrics = AgentMetrics("writer")
        metrics.record_llm_call(input_tokens=100, output_tokens=200, duration=1.0)
        metrics.record_llm_call(input_tokens=150, output_tokens=250, duration=2.0)

        assert metrics.llm_calls == 2
        assert metrics.llm_tokens_input == 250
        assert metrics.llm_tokens_output == 450
        assert metrics.llm_duration == 3.0

    def test_record_error(self):
        from skills.metrics import AgentMetrics

        metrics = AgentMetrics("writer")
        metrics.record_error("draft", "LLM timeout", {"model": "gpt-4"})

        assert len(metrics.errors) == 1
        assert metrics.errors[0]["stage"] == "draft"
        assert metrics.errors[0]["error"] == "LLM timeout"
        assert metrics.errors[0]["details"] == {"model": "gpt-4"}
        assert "timestamp" in metrics.errors[0]

    def test_total_tokens(self):
        from skills.metrics import AgentMetrics

        metrics = AgentMetrics("writer")
        metrics.record_llm_call(input_tokens=100, output_tokens=200)

        assert metrics.total_tokens == 300

    def test_total_duration(self):
        from skills.metrics import AgentMetrics

        metrics = AgentMetrics("writer")
        time.sleep(0.01)

        assert metrics.total_duration > 0

    def test_summary_structure(self):
        from skills.metrics import AgentMetrics

        metrics = AgentMetrics("writer")
        metrics.start_stage("draft")
        time.sleep(0.01)
        metrics.end_stage("draft")
        metrics.record_llm_call(input_tokens=100, output_tokens=200, duration=1.5)
        metrics.record_error("proofread", "test error")

        summary = metrics.summary()

        assert summary["agent"] == "writer"
        assert "started_at" in summary
        assert summary["total_duration_seconds"] > 0
        assert summary["llm"]["calls"] == 1
        assert summary["llm"]["input_tokens"] == 100
        assert summary["llm"]["output_tokens"] == 200
        assert summary["llm"]["total_tokens"] == 300
        assert summary["llm"]["errors"] == 0
        assert summary["llm"]["duration_seconds"] == 1.5
        assert "draft" in summary["stages"]
        assert summary["error_count"] == 1
        assert len(summary["errors"]) == 1

    def test_save_to_file(self, tmp_path):
        from skills.metrics import AgentMetrics

        metrics = AgentMetrics("writer")
        metrics.record_llm_call(input_tokens=100, output_tokens=200)

        path = metrics.save(tmp_path / "test_metrics.json")

        assert path.exists()
        data = json.loads(path.read_text())
        assert data["agent"] == "writer"
        assert data["llm"]["calls"] == 1

    def test_save_auto_path(self, tmp_path, monkeypatch):
        from skills.metrics import AgentMetrics
        import config.settings

        monkeypatch.setattr(config.settings, 'DATA_DIR', tmp_path / 'data')

        metrics = AgentMetrics("feedback")
        path = metrics.save()

        assert path.exists()
        assert "feedback_" in path.name

    def test_repr(self):
        from skills.metrics import AgentMetrics

        metrics = AgentMetrics("writer")
        metrics.record_llm_call(input_tokens=100, output_tokens=200)

        repr_str = repr(metrics)
        assert "writer" in repr_str
        assert "llm_calls=1" in repr_str
        assert "tokens=300" in repr_str

    def test_multiple_stages(self):
        from skills.metrics import AgentMetrics

        metrics = AgentMetrics("writer")

        for stage in ["fetch", "draft", "proofread", "critique"]:
            metrics.start_stage(stage)
            time.sleep(0.01)
            metrics.end_stage(stage)

        durations = metrics.get_stage_durations()
        assert len(durations) == 4
        for stage in ["fetch", "draft", "proofread", "critique"]:
            assert stage in durations
            assert durations[stage] > 0


class TestTimedDecorator:
    """Test timed decorator."""

    def test_timed_function(self):
        from skills.metrics import AgentMetrics, timed

        metrics = AgentMetrics("writer")

        @timed(metrics, "test_stage")
        def my_function():
            time.sleep(0.01)
            return "result"

        result = my_function()

        assert result == "result"
        assert "test_stage" in metrics.get_stage_durations()
        assert metrics.get_stage_durations()["test_stage"] > 0

    def test_timed_function_records_error(self):
        from skills.metrics import AgentMetrics, timed

        metrics = AgentMetrics("writer")

        @timed(metrics, "failing_stage")
        def failing_function():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            failing_function()

        # Stage should still be recorded
        assert "failing_stage" in metrics.get_stage_durations()
        # Error should be recorded
        assert len(metrics.errors) == 1
        assert metrics.errors[0]["stage"] == "failing_stage"
        assert "test error" in metrics.errors[0]["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
