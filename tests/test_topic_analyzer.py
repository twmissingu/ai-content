"""Tests for skills/topic_analyzer.py — topic saturation and competition analysis."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from skills.topic_analyzer import (
    _extract_keywords,
    _get_history_articles,
    _get_pending_topics,
    analyze_topic_competition,
    calculate_saturation,
)


class TestExtractKeywords:
    def test_extracts_chinese_words(self):
        kw = _extract_keywords("AI 发展趋势 分析")
        assert len(kw) > 0
        assert any("ai" in k for k in kw)

    def test_extracts_english_words(self):
        kw = _extract_keywords("Python Tutorial Guide")
        assert "python" in kw
        assert "tutorial" in kw
        assert "guide" in kw

    def test_removes_stop_words(self):
        kw = _extract_keywords("the best for that")
        assert "the" not in kw
        assert "for" not in kw
        assert "that" not in kw
        assert "best" in kw

    def test_empty_string(self):
        assert _extract_keywords("") == set()

    def test_mixed_chinese_english(self):
        kw = _extract_keywords("Python AI 开发指南")
        assert "python" in kw
        assert any("ai" in k for k in kw)


class TestGetHistoryArticles:
    def test_reads_from_history_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day_dir = tmp_path / "history" / today
        day_dir.mkdir(parents=True)
        (day_dir / "article1.md").write_text("# AI趋势\n内容一")
        (day_dir / "article2.md").write_text("# Python技巧\n内容二")

        articles = _get_history_articles(days=1)
        assert len(articles) == 2
        titles = {a["title"] for a in articles}
        assert "AI趋势" in titles

    def test_skips_old_directories(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
        old_dir = tmp_path / "history" / old_date
        old_dir.mkdir(parents=True)
        (old_dir / "old.md").write_text("# 旧文章\n内容")

        articles = _get_history_articles(days=30)
        assert len(articles) == 0

    def test_non_date_directories_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        misc_dir = tmp_path / "history" / "misc"
        misc_dir.mkdir(parents=True)
        (misc_dir / "note.md").write_text("# 笔记\n内容")

        articles = _get_history_articles()
        assert len(articles) == 0

    def test_empty_history(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        articles = _get_history_articles()
        assert articles == []


class TestGetPendingTopics:
    def test_reads_pending_queue(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.settings.PENDING_DIR", tmp_path)
        (tmp_path / "topic_1.json").write_text(json.dumps({"title": "AI趋势"}))
        (tmp_path / "topic_2.json").write_text(json.dumps({"title": "Python教程"}))

        topics = _get_pending_topics()
        assert len(topics) == 2

    def test_skips_invalid_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.settings.PENDING_DIR", tmp_path)
        (tmp_path / "bad.json").write_text("not json{")
        (tmp_path / "good.json").write_text(json.dumps({"title": "好文章"}))

        topics = _get_pending_topics()
        assert len(topics) == 1
        assert topics[0]["title"] == "好文章"

    def test_empty_queue(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.settings.PENDING_DIR", tmp_path)
        topics = _get_pending_topics()
        assert topics == []


class TestCalculateSaturation:
    def test_no_history_returns_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        monkeypatch.setattr("config.settings.PENDING_DIR", tmp_path / "empty")
        (tmp_path / "empty").mkdir()

        result = calculate_saturation("全新AI选题")
        assert result["saturation_score"] == 0
        assert result["similar_count"] == 0

    def test_similar_articles_increase_score(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        monkeypatch.setattr("config.settings.PENDING_DIR", tmp_path / "empty")
        (tmp_path / "empty").mkdir()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day_dir = tmp_path / "history" / today
        day_dir.mkdir(parents=True)

        for i in range(5):
            (day_dir / f"ai_{i}.md").write_text(f"# AI 发展趋势 分析 第{i}篇\n内容")

        result = calculate_saturation("AI 发展趋势")
        assert result["similar_count"] >= 1
        assert result["saturation_score"] > 0

    def test_queue_overlap_increases_score(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        monkeypatch.setattr("config.settings.PENDING_DIR", tmp_path / "pending")
        (tmp_path / "pending").mkdir()
        for i in range(3):
            (tmp_path / "pending" / f"t{i}.json").write_text(
                json.dumps({"title": "AI 发展趋势 分析"})
            )

        result = calculate_saturation("AI 发展趋势")
        assert result["queue_overlap"] >= 1

    def test_max_score_capped_at_100(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        monkeypatch.setattr("config.settings.PENDING_DIR", tmp_path / "pending")
        (tmp_path / "pending").mkdir()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day_dir = tmp_path / "history" / today
        day_dir.mkdir(parents=True)

        for i in range(20):
            (day_dir / f"ai_{i}.md").write_text(f"# AI 技术 发展趋势 深度分析\n内容{i}")

        for i in range(10):
            (tmp_path / "pending" / f"t{i}.json").write_text(
                json.dumps({"title": "AI 发展趋势"})
            )

        result = calculate_saturation("AI 技术 发展趋势")
        assert result["saturation_score"] <= 100

    def test_returns_similar_titles(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        monkeypatch.setattr("config.settings.PENDING_DIR", tmp_path / "empty")
        (tmp_path / "empty").mkdir()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day_dir = tmp_path / "history" / today
        day_dir.mkdir(parents=True)
        (day_dir / "a1.md").write_text("# AI 发展趋势\n内容")

        result = calculate_saturation("AI 发展趋势 分析")
        assert len(result["similar_titles"]) >= 1


class TestAnalyzeTopicCompetition:
    def test_proceed_for_low_saturation(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        monkeypatch.setattr("config.settings.PENDING_DIR", tmp_path / "empty")
        (tmp_path / "empty").mkdir()

        result = analyze_topic_competition("全新的量子计算突破")
        assert result["recommendation"] == "proceed"

    def test_caution_for_medium_saturation(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        monkeypatch.setattr("config.settings.PENDING_DIR", tmp_path / "empty")
        (tmp_path / "empty").mkdir()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day_dir = tmp_path / "history" / today
        day_dir.mkdir(parents=True)
        for i in range(3):
            (day_dir / f"ai_{i}.md").write_text(f"# AI 发展趋势 分析\n内容{i}")

        result = analyze_topic_competition("AI 发展趋势")
        assert result["recommendation"] in ("caution", "skip")

    def test_skip_for_high_saturation(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        monkeypatch.setattr("config.settings.PENDING_DIR", tmp_path / "pending")
        (tmp_path / "pending").mkdir()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day_dir = tmp_path / "history" / today
        day_dir.mkdir(parents=True)
        for i in range(10):
            (day_dir / f"ai_{i}.md").write_text(f"# AI 技术 发展趋势 深度分析\n内容{i}")
        for i in range(5):
            (tmp_path / "pending" / f"t{i}.json").write_text(
                json.dumps({"title": "AI 发展趋势"})
            )

        result = analyze_topic_competition("AI 发展趋势 分析")
        assert result["recommendation"] == "skip"

    def test_source_overrepresented_flag(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        monkeypatch.setattr("config.settings.PENDING_DIR", tmp_path / "empty")
        (tmp_path / "empty").mkdir()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day_dir = tmp_path / "history" / today
        day_dir.mkdir(parents=True)
        for i in range(5):
            (day_dir / f"techcrunch_{i}.md").write_text(f"# AI News {i}\n内容")

        result = analyze_topic_competition("AI News", source="techcrunch")
        assert result["source_diversity"]["overrepresented"] is True

    def test_includes_saturation_data(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.topic_analyzer.KB_DIR", tmp_path)
        monkeypatch.setattr("config.settings.PENDING_DIR", tmp_path / "empty")
        (tmp_path / "empty").mkdir()

        result = analyze_topic_competition("测试选题")
        assert "saturation" in result
        assert "source_diversity" in result
        assert "recommendation" in result
        assert "reason" in result
