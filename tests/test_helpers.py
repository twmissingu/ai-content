"""Tests for dashboard/backend/helpers.py — shared helper functions."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dashboard.backend.helpers import read_json, detect_timeout, load_schedule


class TestReadJson:
    """Test read_json function."""

    def test_reads_valid_json(self, tmp_path):
        path = tmp_path / "test.json"
        path.write_text(json.dumps({"key": "value"}))
        assert read_json(path) == {"key": "value"}

    def test_returns_empty_on_missing_file(self, tmp_path):
        assert read_json(tmp_path / "missing.json") == {}

    def test_returns_empty_on_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json {{{")
        assert read_json(path) == {}


class TestDetectTimeout:
    """Test detect_timeout function."""

    def test_returns_false_when_no_started_at(self):
        assert detect_timeout({}) is False
        assert detect_timeout({"started_at": ""}) is False

    def test_returns_false_when_recent(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        assert detect_timeout({"started_at": stamp}, max_minutes=30) is False

    def test_returns_true_when_old(self):
        old_stamp = "20260101_000000"
        assert detect_timeout({"started_at": old_stamp}, max_minutes=30) is True

    def test_returns_false_on_invalid_format(self):
        assert detect_timeout({"started_at": "invalid-format"}) is False


class TestLoadSchedule:
    """Test load_schedule function."""

    def test_returns_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dashboard.backend.helpers.CONFIG_DIR", tmp_path / "config")
        result = load_schedule()
        assert "morning_scout" in result
        assert result["morning_scout"] == "09:00"

    def test_reads_existing_file(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        schedule = {"morning_scout": "10:00", "evening_scout": "15:00"}
        (config_dir / "schedule.json").write_text(json.dumps(schedule))
        # helpers.load_schedule() now delegates to config_service.get_schedule_config()
        monkeypatch.setattr("dashboard.backend.config_service.CONFIG_DIR", config_dir)
        result = load_schedule()
        assert result["morning_scout"] == "10:00"
