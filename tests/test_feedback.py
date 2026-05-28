"""Unit tests for skills/feedback.py — data analysis and strategy."""

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def feedback_dirs(tmp_path, monkeypatch):
    """Create temporary directories for feedback agent."""
    dirs = {
        'kb': tmp_path / 'kb',
        'data': tmp_path / 'data',
        'status': tmp_path / 'queue' / 'status',
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    import skills.feedback
    monkeypatch.setattr(skills.feedback, 'KB_DIR', dirs['kb'])
    monkeypatch.setattr(skills.feedback, 'HISTORY_DIR', dirs['kb'] / 'history')
    monkeypatch.setattr(skills.feedback, 'VIRAL_DIR', dirs['kb'] / 'viral')
    monkeypatch.setattr(skills.feedback, 'STRATEGY_DIR', dirs['kb'] / 'strategy')

    import config.settings
    monkeypatch.setattr(config.settings, 'KB_DIR', dirs['kb'])
    monkeypatch.setattr(config.settings, 'STATUS_DIR', dirs['status'])
    monkeypatch.setattr(config.settings, 'DATA_DIR', dirs['data'])

    return dirs


@pytest.fixture
def sample_articles(feedback_dirs):
    """Create sample articles in history."""
    history_dir = feedback_dirs['kb'] / 'history' / '2026-05-28'
    history_dir.mkdir(parents=True)

    articles = []
    for i in range(5):
        article_path = history_dir / f"article_{i}.md"
        article_path.write_text(f"# 文章标题{i}\n\n这是第{i}篇文章的内容...")

        meta_path = history_dir / f"article_{i}.meta.json"
        meta_path.write_text(json.dumps({
            "topic": f"话题{i}",
            "word_count": 100 + i * 50,
        }))
        articles.append(article_path)

    return articles


class TestCollectArticles:
    """Test _collect_articles method."""

    def test_collects_articles(self, feedback_dirs, sample_articles):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"

        articles = agent._collect_articles()

        assert len(articles) == 5
        for a in articles:
            assert "title" in a
            assert "date" in a
            assert "path" in a
            assert "meta" in a

    def test_collects_empty_history(self, feedback_dirs):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"

        articles = agent._collect_articles()
        assert articles == []

    def test_extracts_title_from_markdown(self, feedback_dirs):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock

        history_dir = feedback_dirs['kb'] / 'history' / '2026-05-28'
        history_dir.mkdir(parents=True)
        (history_dir / "test.md").write_text("# 我的标题\n\n内容")

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"

        articles = agent._collect_articles()
        assert len(articles) == 1
        assert articles[0]["title"] == "我的标题"


class TestDetectViral:
    """Test _detect_viral method."""

    def test_detects_title_patterns(self, feedback_dirs):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"

        articles = [
            {"title": "3个方法提升效率", "meta": {}},
            {"title": "为什么AI会火？", "meta": {}},
            {"title": "Python vs Java对比", "meta": {}},
            {"title": "如何学习编程", "meta": {}},
        ]

        viral = agent._detect_viral(articles, [])

        assert viral is not None
        assert viral["article_count"] == 4
        assert "数字型" in viral["title_patterns"]
        assert "提问型" in viral["title_patterns"]

    def test_extracts_keywords(self, feedback_dirs):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"

        articles = [
            {"title": "人工智能发展趋势", "meta": {}},
            {"title": "人工智能应用场景", "meta": {}},
            {"title": "机器学习入门指南", "meta": {}},
        ]

        viral = agent._detect_viral(articles, [])

        assert viral is not None
        keywords = [kw["word"] for kw in viral["top_keywords"]]
        # The regex matches full Chinese phrases, not individual words
        assert any("人工智能" in kw for kw in keywords)

    def test_returns_none_for_empty_articles(self, feedback_dirs):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"

        viral = agent._detect_viral([], [])
        assert viral is None

    def test_includes_data_source(self, feedback_dirs):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"

        articles = [{"title": "测试文章", "meta": {}}]

        # With platform data
        viral = agent._detect_viral(articles, [{"views": 100}])
        assert viral["data_source"] == "aitoearn"

        # Without platform data
        viral = agent._detect_viral(articles, [])
        assert viral["data_source"] == "local_only"

    def test_extracts_topic_directions(self, feedback_dirs):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"

        articles = [
            {"title": "文章1", "meta": {"topic": "AI应用"}},
            {"title": "文章2", "meta": {"topic": "AI应用"}},
            {"title": "文章3", "meta": {"topic": "Python"}},
        ]

        viral = agent._detect_viral(articles, [])

        assert viral is not None
        assert "topic_directions" in viral
        assert viral["topic_directions"].get("AI应用") == 2


class TestQueryAitoearnAnalytics:
    """Test _query_aitoearn_analytics method."""

    def test_returns_empty_when_no_tools(self, feedback_dirs):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock, patch

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"

        mock_result = MagicMock()
        mock_result.stdout = "No tools available"

        with patch("subprocess.run", return_value=mock_result):
            result = agent._query_aitoearn_analytics()

        assert result == []

    def test_returns_empty_on_failure(self, feedback_dirs):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock, patch

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"

        with patch("subprocess.run", side_effect=Exception("Subprocess error")):
            result = agent._query_aitoearn_analytics()

        assert result == []


class TestUpdateViralKb:
    """Test _update_viral_kb method."""

    def test_writes_viral_data(self, feedback_dirs):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"

        viral = {
            "article_count": 10,
            "title_patterns": {"数字型": 5},
            "top_keywords": [{"word": "AI", "count": 3}],
        }

        agent._update_viral_kb(viral)

        viral_file = feedback_dirs['kb'] / 'viral' / 'viral_2026-05-28.json'
        assert viral_file.exists()
        data = json.loads(viral_file.read_text())
        assert data["article_count"] == 10


class TestUpdateStrategyKb:
    """Test _update_strategy_kb method."""

    def test_writes_strategy_data(self, feedback_dirs):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock, patch

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"
        agent.record_llm_call = MagicMock()

        viral = {
            "article_count": 10,
            "title_patterns": {"数字型": 5},
            "top_keywords": [{"word": "AI", "count": 3}],
            "topic_directions": {"AI应用": 5},
            "data_source": "local_only",
        }

        mock_strategy = {
            "recommendation": "下周重点写AI方向",
            "focus_directions": ["AI应用"],
            "avoid_topics": [],
            "title_style": "数字型",
            "content_gaps": [],
            "suggested_topics": [],
        }

        with patch("skills.feedback.chat_structured", return_value=mock_strategy):
            agent._update_strategy_kb(viral)

        strategy_file = feedback_dirs['kb'] / 'strategy' / 'strategy_2026-05-28.json'
        assert strategy_file.exists()
        data = json.loads(strategy_file.read_text())
        assert data["recommendation"] == "下周重点写AI方向"

    def test_handles_llm_failure(self, feedback_dirs):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock, patch

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"
        agent.record_llm_call = MagicMock()

        viral = {
            "article_count": 10,
            "title_patterns": {},
            "top_keywords": [],
            "topic_directions": {},
            "data_source": "local_only",
        }

        with patch("skills.feedback.chat_structured", side_effect=Exception("LLM error")):
            agent._update_strategy_kb(viral)

        strategy_file = feedback_dirs['kb'] / 'strategy' / 'strategy_2026-05-28.json'
        assert strategy_file.exists()
        data = json.loads(strategy_file.read_text())
        assert "数据不足" in data["recommendation"]


class TestConstants:
    """Test module constants."""

    def test_viral_threshold(self):
        from skills.feedback import VIRAL_THRESHOLD_PCT
        assert 0 < VIRAL_THRESHOLD_PCT < 1

    def test_directory_paths(self):
        from skills.feedback import HISTORY_DIR, VIRAL_DIR, STRATEGY_DIR
        assert HISTORY_DIR.name == "history"
        assert VIRAL_DIR.name == "viral"
        assert STRATEGY_DIR.name == "strategy"


class TestRun:
    """Test the run method of FeedbackAgent."""

    def test_completes_with_no_articles(self, feedback_dirs):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"
        agent.write_status = MagicMock()
        agent.write_completed = MagicMock()
        agent.start_stage = MagicMock()
        agent.end_stage = MagicMock()
        agent.record_llm_call = MagicMock()

        agent.run()

        agent.write_completed.assert_called_once()

    def test_processes_articles(self, feedback_dirs, sample_articles):
        from skills.feedback import FeedbackAgent
        from unittest.mock import MagicMock, patch

        agent = FeedbackAgent.__new__(FeedbackAgent)
        agent.logger = MagicMock()
        agent._run_date = "2026-05-28"
        agent.write_status = MagicMock()
        agent.write_completed = MagicMock()
        agent.start_stage = MagicMock()
        agent.end_stage = MagicMock()
        agent.record_llm_call = MagicMock()

        mock_strategy = {
            "recommendation": "测试策略",
            "focus_directions": [],
            "avoid_topics": [],
            "title_style": "数字型",
            "content_gaps": [],
            "suggested_topics": [],
        }

        with patch("skills.feedback.chat_structured", return_value=mock_strategy):
            with patch("subprocess.run", side_effect=Exception("No MCP")):
                agent.run()

        agent.write_completed.assert_called_once()
        # Should have written viral and strategy files
        viral_file = feedback_dirs['kb'] / 'viral' / 'viral_2026-05-28.json'
        assert viral_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
