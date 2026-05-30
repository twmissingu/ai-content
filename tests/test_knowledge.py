"""Unit tests for skills/knowledge.py — article archival."""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def knowledge_dirs(tmp_path, monkeypatch):
    """Create temporary directories for knowledge agent."""
    dirs = {
        'kb': tmp_path / 'kb',
        'review': tmp_path / 'queue' / 'review',
        'status': tmp_path / 'queue' / 'status',
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    # Patch at the module level where KB_DIR is used
    import skills.knowledge
    monkeypatch.setattr(skills.knowledge, 'KB_DIR', dirs['kb'])
    monkeypatch.setattr(skills.knowledge, 'REVIEW_DIR', dirs['review'])

    import config.settings
    monkeypatch.setattr(config.settings, 'KB_DIR', dirs['kb'])
    monkeypatch.setattr(config.settings, 'REVIEW_DIR', dirs['review'])
    monkeypatch.setattr(config.settings, 'STATUS_DIR', dirs['status'])

    return dirs


@pytest.fixture
def sample_article(knowledge_dirs):
    """Create a sample article and meta in review dir."""
    article_path = knowledge_dirs['review'] / "20260528-wechat.md"
    article_path.write_text("# 测试文章\n\n这是测试内容...")

    meta_path = knowledge_dirs['review'] / "20260528-wechat.meta.json"
    meta_path.write_text(json.dumps({
        "topic": "AI 发展趋势",
        "platform_standard": "wechat",
        "word_count": 100,
        "status": "completed",
    }))

    return article_path, meta_path


class TestKnowledgeAgent:
    """Test KnowledgeAgent class."""

    def test_archive_article(self, knowledge_dirs, sample_article):
        from skills.knowledge import KnowledgeAgent

        article_path, meta_path = sample_article
        meta = json.loads(meta_path.read_text())

        agent = KnowledgeAgent()
        agent.logger = MagicMock()
        dest = agent._archive_article(article_path, meta)

        assert dest.exists()
        assert dest.read_text() == article_path.read_text()
        assert "history" in str(dest)

    def test_archive_creates_date_directory(self, knowledge_dirs, sample_article):
        from skills.knowledge import KnowledgeAgent

        article_path, meta_path = sample_article
        meta = json.loads(meta_path.read_text())

        agent = KnowledgeAgent()
        agent.logger = MagicMock()
        dest = agent._archive_article(article_path, meta)

        date_str = datetime.now().strftime("%Y-%m-%d")
        expected_dir = knowledge_dirs['kb'] / 'history' / date_str
        assert expected_dir.exists()
        assert dest.parent == expected_dir

    def test_update_topics_index(self, knowledge_dirs):
        from skills.knowledge import KnowledgeAgent

        agent = KnowledgeAgent()
        agent.logger = MagicMock()
        agent._update_topics_index("AI 发展趋势", "wechat")

        index_path = knowledge_dirs['kb'] / 'topics' / 'INDEX.md'
        assert index_path.exists()

        content = index_path.read_text()
        assert "AI 发展趋势" in content
        assert "wechat" in content

    def test_update_topics_index_appends(self, knowledge_dirs):
        from skills.knowledge import KnowledgeAgent

        agent = KnowledgeAgent()
        agent.logger = MagicMock()
        agent._update_topics_index("第一个话题", "wechat")
        agent._update_topics_index("第二个话题", "xiaohongshu")

        index_path = knowledge_dirs['kb'] / 'topics' / 'INDEX.md'
        content = index_path.read_text()

        assert "第一个话题" in content
        assert "第二个话题" in content
        lines = [l for l in content.strip().split('\n') if l.strip()]
        assert len(lines) == 2

    def test_run_archives_article(self, knowledge_dirs, sample_article, monkeypatch):
        from skills.knowledge import KnowledgeAgent

        monkeypatch.setattr(sys, 'argv', ['knowledge', '20260528-wechat'])

        agent = KnowledgeAgent()
        agent.logger = MagicMock()
        agent.write_status = MagicMock()
        agent.write_error = MagicMock()
        agent.write_completed = MagicMock()
        agent.run()

        date_str = datetime.now().strftime("%Y-%m-%d")
        history_dir = knowledge_dirs['kb'] / 'history' / date_str
        assert history_dir.exists()
        archived_files = list(history_dir.glob("*.md"))
        assert len(archived_files) == 1

        index_path = knowledge_dirs['kb'] / 'topics' / 'INDEX.md'
        assert index_path.exists()
        assert "AI 发展趋势" in index_path.read_text()

    def test_run_no_target_id_finds_latest(self, knowledge_dirs, sample_article, monkeypatch):
        from skills.knowledge import KnowledgeAgent

        monkeypatch.setattr(sys, 'argv', ['knowledge'])

        agent = KnowledgeAgent()
        agent.logger = MagicMock()
        agent.write_status = MagicMock()
        agent.write_error = MagicMock()
        agent.write_completed = MagicMock()
        agent.run()

        date_str = datetime.now().strftime("%Y-%m-%d")
        history_dir = knowledge_dirs['kb'] / 'history' / date_str
        assert history_dir.exists()
        archived_files = list(history_dir.glob("*.md"))
        assert len(archived_files) == 1

    def test_run_no_articles_to_archive(self, knowledge_dirs, monkeypatch):
        from skills.knowledge import KnowledgeAgent

        monkeypatch.setattr(sys, 'argv', ['knowledge'])

        agent = KnowledgeAgent()
        agent.logger = MagicMock()
        agent.write_status = MagicMock()
        agent.write_completed = MagicMock()
        agent.run()

    def test_run_missing_meta(self, knowledge_dirs, monkeypatch):
        from skills.knowledge import KnowledgeAgent

        monkeypatch.setattr(sys, 'argv', ['knowledge', 'nonexistent'])

        agent = KnowledgeAgent()
        agent.logger = MagicMock()
        agent.write_status = MagicMock()
        agent.write_error = MagicMock()
        agent.run()

    def test_run_with_ai_analysis(self, knowledge_dirs, sample_article, monkeypatch):
        from skills.knowledge import KnowledgeAgent

        analysis_result = {
            "keywords": ["ai", "发展", "趋势"],
            "tags": ["AI", "科技"],
            "writing_patterns": ["数据驱动"],
            "summary": "AI发展趋势分析",
            "quality_score": 80,
        }
        monkeypatch.setattr(
            "skills.knowledge.chat_structured",
            MagicMock(return_value=analysis_result),
        )
        monkeypatch.setattr(sys, 'argv', ['knowledge'])

        agent = KnowledgeAgent()
        agent.logger = MagicMock()
        agent.write_status = MagicMock()
        agent.write_completed = MagicMock()
        agent.run()

        date_str = datetime.now().strftime("%Y-%m-%d")
        history_dir = knowledge_dirs['kb'] / 'history' / date_str
        meta_files = list(history_dir.glob("*.meta.json"))
        assert len(meta_files) == 1
        meta = json.loads(meta_files[0].read_text())
        assert meta["analysis"]["keywords"] == ["ai", "发展", "趋势"]
        assert meta["analysis"]["quality_score"] == 80

    def test_run_analysis_failure_does_not_block(self, knowledge_dirs, sample_article, monkeypatch):
        from skills.knowledge import KnowledgeAgent

        monkeypatch.setattr(
            "skills.knowledge.chat_structured",
            MagicMock(side_effect=Exception("LLM unavailable")),
        )
        monkeypatch.setattr(sys, 'argv', ['knowledge'])

        agent = KnowledgeAgent()
        agent.logger = MagicMock()
        agent.write_status = MagicMock()
        agent.write_completed = MagicMock()
        agent.run()

        date_str = datetime.now().strftime("%Y-%m-%d")
        history_dir = knowledge_dirs['kb'] / 'history' / date_str
        archived_files = list(history_dir.glob("*.md"))
        assert len(archived_files) == 1
        meta_files = list(history_dir.glob("*.meta.json"))
        assert len(meta_files) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
