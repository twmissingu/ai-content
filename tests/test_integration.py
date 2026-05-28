"""Integration tests for Agent pipelines.

Tests the full workflow of each agent with mocked LLM calls.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories for testing."""
    dirs = {
        'queue': tmp_path / 'queue',
        'pending': tmp_path / 'queue' / 'pending',
        'review': tmp_path / 'queue' / 'review',
        'status': tmp_path / 'queue' / 'status',
        'actions': tmp_path / 'queue' / 'actions',
        'failed': tmp_path / 'queue' / 'failed',
        'images': tmp_path / 'queue' / 'images',
        'kb': tmp_path / 'kb',
        'data': tmp_path / 'data',
        'logs': tmp_path / 'data' / 'logs',
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


@pytest.fixture
def sample_topic(temp_dirs):
    """Create a sample topic file."""
    topic = {
        "title": "AI 改变世界",
        "description": "人工智能技术的最新发展",
        "source": "weibo",
        "final_score": 75.5,
        "url": "https://example.com/ai-article"
    }
    topic_file = temp_dirs['pending'] / "topic_20260528_120000.json"
    topic_file.write_text(json.dumps(topic, ensure_ascii=False, indent=2))
    return topic


class TestWriterIntegration:
    """Integration tests for Writer agent."""
    
    @patch('skills.llm.chat')
    @patch('skills.llm.chat_structured')
    def test_writer_creates_article(self, mock_structured, mock_chat, temp_dirs, sample_topic, monkeypatch):
        """Test that Writer creates an article file."""
        # Mock LLM responses
        mock_chat.return_value = "这是一篇测试文章的内容..."
        mock_structured.return_value = {
            "score": 80,
            "candidates": [
                {"title": "AI 如何改变世界", "score": 90, "rationale": "吸引人"},
                {"title": "人工智能的未来", "score": 85, "rationale": "准确"},
                {"title": "AI 技术前沿", "score": 80, "rationale": "专业"},
            ]
        }
        
        # Monkeypatch settings
        monkeypatch.chdir(temp_dirs['queue'].parent.parent)
        
        import config.settings
        monkeypatch.setattr(config.settings, 'PENDING_DIR', temp_dirs['pending'])
        monkeypatch.setattr(config.settings, 'REVIEW_DIR', temp_dirs['review'])
        monkeypatch.setattr(config.settings, 'STATUS_DIR', temp_dirs['status'])
        monkeypatch.setattr(config.settings, 'ACTIONS_DIR', temp_dirs['actions'])
        
        # Run writer
        from skills.writer import WriterAgent
        agent = WriterAgent()
        
        # Mock _fetch_source to avoid subprocess call
        agent._fetch_source = MagicMock(return_value="测试素材内容")
        
        agent.run()
        
        # Verify article was created
        review_files = list(temp_dirs['review'].glob("*.md"))
        assert len(review_files) > 0, "No article file created"
        
        # Verify meta was created
        meta_files = list(temp_dirs['review'].glob("*.meta.json"))
        assert len(meta_files) > 0, "No meta file created"
        
        # Verify meta content
        meta = json.loads(meta_files[0].read_text())
        assert meta['status'] == 'completed'
        assert meta['word_count'] > 0
    
    @patch('skills.writer.chat')
    @patch('skills.writer.chat_structured')
    def test_writer_handles_low_quality(self, mock_structured, mock_chat, temp_dirs, sample_topic, monkeypatch):
        """Test that Writer handles low quality scores with rewriting."""
        # Mock LLM responses - first draft is low quality
        call_count = 0
        def mock_chat_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return "低质量文章..."
            return "改进后的高质量文章..."

        mock_chat.side_effect = mock_chat_side_effect
        mock_structured.return_value = {
            "score": 50,  # Below threshold
            "weakness": "论点不够鲜明",
            "suggestions": ["加强论点", "增加案例"]
        }

        # Monkeypatch settings
        monkeypatch.chdir(temp_dirs['queue'].parent.parent)

        import config.settings
        monkeypatch.setattr(config.settings, 'PENDING_DIR', temp_dirs['pending'])
        monkeypatch.setattr(config.settings, 'REVIEW_DIR', temp_dirs['review'])
        monkeypatch.setattr(config.settings, 'STATUS_DIR', temp_dirs['status'])
        monkeypatch.setattr(config.settings, 'ACTIONS_DIR', temp_dirs['actions'])

        # Run writer
        from skills.writer import WriterAgent
        agent = WriterAgent()
        agent._fetch_source = MagicMock(return_value="测试素材")

        agent.run()

        # Verify multiple LLM calls were made (draft + critique + rewrite)
        assert call_count >= 3, f"Expected at least 3 LLM calls, got {call_count}"


class TestPublisherIntegration:
    """Integration tests for Publisher agent."""

    def test_publisher_finds_article(self, temp_dirs, monkeypatch):
        """Test that Publisher can find article files."""
        # Create test article
        article_path = temp_dirs['review'] / "20260528-wechat.md"
        article_path.write_text("# 测试文章\n\n这是测试内容...")

        meta_path = temp_dirs['review'] / "20260528-wechat.meta.json"
        meta_path.write_text(json.dumps({
            "topic": "测试选题",
            "platform_standard": "wechat",
            "status": "completed"
        }))

        # Monkeypatch settings
        monkeypatch.chdir(temp_dirs['queue'].parent.parent)

        import config.settings
        import skills.publisher
        monkeypatch.setattr(config.settings, 'REVIEW_DIR', temp_dirs['review'])
        monkeypatch.setattr(config.settings, 'STATUS_DIR', temp_dirs['status'])
        monkeypatch.setattr(config.settings, 'FAILED_DIR', temp_dirs['failed'])
        monkeypatch.setattr(skills.publisher, 'REVIEW_DIR', temp_dirs['review'])
        monkeypatch.setattr(skills.publisher, 'STATUS_DIR', temp_dirs['status'])
        monkeypatch.setattr(skills.publisher, 'FAILED_DIR', temp_dirs['failed'])

        # Run publisher
        from skills.publisher import PublisherAgent
        agent = PublisherAgent()

        article, meta = agent.find_article("20260528-wechat")

        assert article is not None
        assert meta is not None
        assert meta['topic'] == "测试选题"


class TestFeedbackIntegration:
    """Integration tests for Feedback agent."""
    
    def test_feedback_collects_articles(self, temp_dirs, monkeypatch):
        """Test that Feedback can collect articles from history."""
        # Create test history
        history_dir = temp_dirs['kb'] / 'history' / '2026-05-28'
        history_dir.mkdir(parents=True)

        article_path = history_dir / "test-article.md"
        article_path.write_text("# 测试文章\n\n这是测试内容...")

        meta_path = history_dir / "test-article.meta.json"
        meta_path.write_text(json.dumps({
            "topic": "测试选题",
            "word_count": 100
        }))

        # Monkeypatch settings
        monkeypatch.chdir(temp_dirs['queue'].parent.parent)

        import config.settings
        monkeypatch.setattr(config.settings, 'KB_DIR', temp_dirs['kb'])
        monkeypatch.setattr(config.settings, 'STATUS_DIR', temp_dirs['status'])
        monkeypatch.setattr(config.settings, 'DATA_DIR', temp_dirs['data'])

        # Patch module-level constants in feedback.py
        import skills.feedback
        monkeypatch.setattr(skills.feedback, 'KB_DIR', temp_dirs['kb'])
        monkeypatch.setattr(skills.feedback, 'HISTORY_DIR', temp_dirs['kb'] / 'history')

        # Run feedback
        from skills.feedback import FeedbackAgent
        agent = FeedbackAgent()

        articles = agent._collect_articles()

        assert len(articles) == 1
        assert articles[0]['title'] == "测试文章"


class TestCommonIntegration:
    """Integration tests for common utilities."""
    
    def test_atomic_write_creates_file(self, tmp_path):
        """Test that atomic_write_json creates files correctly."""
        from skills.common import atomic_write_json
        
        path = tmp_path / "test.json"
        data = {"key": "value", "nested": {"a": 1}}
        
        atomic_write_json(path, data)
        
        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded == data
    
    def test_file_lock_prevents_concurrent_access(self, tmp_path):
        """Test that file_lock works correctly."""
        import threading
        from skills.common import file_lock
        
        results = []
        lock_path = tmp_path / "test.lock"
        
        def worker(worker_id):
            with file_lock(lock_path):
                results.append(f"start-{worker_id}")
                import time
                time.sleep(0.1)
                results.append(f"end-{worker_id}")
        
        # Run two workers
        t1 = threading.Thread(target=worker, args=(1,))
        t2 = threading.Thread(target=worker, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Verify they didn't interleave
        assert len(results) == 4
        # Should be either [start-1, end-1, start-2, end-2] or [start-2, end-2, start-1, end-1]
        assert results[0].startswith("start-")
        assert results[1].startswith("end-")
        assert results[0].split("-")[1] == results[1].split("-")[1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
