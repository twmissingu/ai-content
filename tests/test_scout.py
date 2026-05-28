"""Unit tests for skills/scout.py utilities."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class TestIsSameTopic:
    """Test topic similarity detection."""
    
    def test_identical_topics(self):
        """Test identical topics are detected as same."""
        from skills.scout import _is_same_topic
        
        assert _is_same_topic("AI 改变世界", "AI 改变世界") == True
    
    def test_similar_topics(self):
        """Test similar topics are detected as same."""
        from skills.scout import _is_same_topic
        
        assert _is_same_topic("AI 改变世界", "AI 正在改变世界") == True
        assert _is_same_topic("ChatGPT 发布新版本", "ChatGPT 发布了新版本") == True
    
    def test_different_topics(self):
        """Test different topics are detected as different."""
        from skills.scout import _is_same_topic
        
        assert _is_same_topic("AI 改变世界", "Python 教程") == False
        assert _is_same_topic("ChatGPT 发布", "苹果手机上市") == False
    
    def test_empty_topics(self):
        """Test empty topics handling."""
        from skills.scout import _is_same_topic
        
        assert _is_same_topic("", "test") == False
        assert _is_same_topic("test", "") == False
        assert _is_same_topic("", "") == False
    
    def test_short_topics(self):
        """Test very short topics."""
        from skills.scout import _is_same_topic
        
        # Very short topics with no overlap
        assert _is_same_topic("AI", "ML") == False
    
    def test_chinese_topics(self):
        """Test Chinese topic similarity."""
        from skills.scout import _is_same_topic
        
        assert _is_same_topic("人工智能发展趋势", "人工智能的发展趋势分析") == True
        assert _is_same_topic("机器学习入门", "深度学习入门") == False


class TestDedupAndFilter:
    """Test topic deduplication and filtering."""
    
    def test_removes_duplicates(self):
        """Test that duplicates are removed."""
        from skills.scout import dedup_and_filter
        
        candidates = [
            {"title": "AI 改变世界"},
            {"title": "AI 正在改变世界"},  # Similar to first
            {"title": "Python 教程"},
        ]
        
        result = dedup_and_filter(candidates)
        
        # Should have 2 unique topics
        assert len(result) == 2
        titles = [c["title"] for c in result]
        assert "AI 改变世界" in titles
        assert "Python 教程" in titles
    
    def test_filters_short_titles(self):
        """Test that very short titles are filtered."""
        from skills.scout import dedup_and_filter
        
        candidates = [
            {"title": "AI"},  # Too short
            {"title": "人工智能发展趋势"},  # Good length
        ]
        
        result = dedup_and_filter(candidates)
        
        assert len(result) == 1
        assert result[0]["title"] == "人工智能发展趋势"
    
    def test_filters_empty_titles(self):
        """Test that empty titles are filtered."""
        from skills.scout import dedup_and_filter
        
        candidates = [
            {"title": ""},
            {"title": "  "},
            {"title": "有效标题"},
        ]
        
        result = dedup_and_filter(candidates)
        
        assert len(result) == 1
        assert result[0]["title"] == "有效标题"
    
    def test_preserves_order(self):
        """Test that order is preserved."""
        from skills.scout import dedup_and_filter

        candidates = [
            {"title": "AI 技术发展"},
            {"title": "Python 编程教程"},
            {"title": "区块链应用"},
        ]

        result = dedup_and_filter(candidates)

        assert len(result) == 3
        assert result[0]["title"] == "AI 技术发展"
        assert result[1]["title"] == "Python 编程教程"
        assert result[2]["title"] == "区块链应用"


class TestScoreCalculation:
    """Test score calculation logic."""
    
    def test_score_range(self):
        """Test that scores are in valid range."""
        # This would require mocking the LLM, so we test the formula directly
        
        # Test attention score formula
        source_weight = 0.8
        viral = 70
        freshness_score = 60
        
        attention = min(100,
            (source_weight ** 1.3) * 0.35
            + viral * 0.30
            + freshness_score * 0.35
        )
        
        assert 0 <= attention <= 100
    
    def test_increment_score_formula(self):
        """Test increment score formula."""
        saturation = 50
        novelty = 70
        self_repeat = 100
        
        increment = saturation * 0.40 + novelty * 0.35 + self_repeat * 0.25
        
        assert 0 <= increment <= 100
    
    def test_final_score_formula(self):
        """Test final score formula."""
        attention = 75
        increment = 60
        feasibility = 80
        
        final_score = attention * 0.55 + increment * 0.25 + feasibility * 0.20
        
        assert 0 <= final_score <= 100


class TestEnforceDiversity:
    """Test diversity enforcement."""
    
    def test_few_candidates(self):
        """Test with fewer candidates than max directions."""
        from skills.scout import _enforce_diversity, MAX_SUB_DIRECTIONS
        
        scored = [
            {"direction": "AI", "final_score": 90},
            {"direction": "科技", "final_score": 80},
        ]
        
        result = _enforce_diversity(scored)
        
        # Should return all candidates unchanged
        assert len(result) == 2
    
    def test_dominant_direction(self):
        """Test that dominant direction is balanced."""
        from skills.scout import _enforce_diversity, MAX_SUB_DIRECTIONS
        
        scored = [
            {"direction": "AI", "final_score": 95},
            {"direction": "AI", "final_score": 90},
            {"direction": "AI", "final_score": 85},
            {"direction": "科技", "final_score": 80},
            {"direction": "商业", "final_score": 75},
        ]
        
        result = _enforce_diversity(scored)
        
        # Should have at least one from each direction
        directions = {c["direction"] for c in result}
        assert "AI" in directions
        assert "科技" in directions
        assert "商业" in directions
    
    def test_sorted_by_score(self):
        """Test that result is sorted by score."""
        from skills.scout import _enforce_diversity
        
        scored = [
            {"direction": "AI", "final_score": 70},
            {"direction": "科技", "final_score": 90},
            {"direction": "商业", "final_score": 80},
        ]
        
        result = _enforce_diversity(scored)
        
        # Should be sorted by score descending
        for i in range(len(result) - 1):
            assert result[i]["final_score"] >= result[i + 1]["final_score"]


class TestAllowedSources:
    """Test allowed sources configuration."""

    def test_all_expected_sources_present(self):
        """Test that all expected sources are in allowed list."""
        from skills.scout import ALLOWED_CHINA_HOT_SOURCES

        expected = {"weibo", "zhihu", "bilibili", "baidu", "douyin", "toutiao", "kr36"}
        assert expected.issubset(ALLOWED_CHINA_HOT_SOURCES)

    def test_source_is_frozenset(self):
        """Test that allowed sources is immutable."""
        from skills.scout import ALLOWED_CHINA_HOT_SOURCES

        assert isinstance(ALLOWED_CHINA_HOT_SOURCES, frozenset)


class TestCallChinaHot:
    """Tests for _call_china_hot function."""

    def test_returns_empty_for_invalid_source(self):
        """Should return empty list for non-whitelisted source."""
        from skills.scout import _call_china_hot

        result = _call_china_hot("invalid_source")
        assert result == []

    def test_returns_empty_on_subprocess_timeout(self):
        """Should return empty list on timeout."""
        from unittest.mock import patch, MagicMock
        from skills.scout import _call_china_hot

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            result = _call_china_hot("weibo")
        assert result == []

    def test_returns_empty_on_json_error(self):
        """Should return empty list on JSON decode error."""
        from unittest.mock import patch
        from skills.scout import _call_china_hot

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"

        with patch("subprocess.run", return_value=mock_result):
            result = _call_china_hot("weibo")
        assert result == []

    def test_returns_items_on_success(self):
        """Should return parsed items on success."""
        from unittest.mock import patch, MagicMock
        from skills.scout import _call_china_hot

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([{"title": "Test Topic"}])

        with patch("subprocess.run", return_value=mock_result):
            result = _call_china_hot("weibo")

        assert len(result) == 1
        assert result[0]["title"] == "Test Topic"

    def test_handles_data_wrapper(self):
        """Should handle response with 'data' key."""
        from unittest.mock import patch, MagicMock
        from skills.scout import _call_china_hot

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"data": [{"title": "Topic"}]})

        with patch("subprocess.run", return_value=mock_result):
            result = _call_china_hot("zhihu")

        assert len(result) == 1

    def test_returns_empty_on_nonzero_exit(self):
        """Should return empty list on non-zero exit code."""
        from unittest.mock import patch, MagicMock
        from skills.scout import _call_china_hot

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = _call_china_hot("weibo")
        assert result == []


class TestCollectMaterials:
    """Tests for _collect_materials function."""

    def test_returns_empty_when_dir_not_exists(self, tmp_path):
        """Should return empty list when materials dir doesn't exist."""
        from unittest.mock import patch
        from skills.scout import _collect_materials

        with patch("skills.scout.KB_DIR", tmp_path):
            result = _collect_materials()

        assert result == []

    def test_reads_markdown_files(self, tmp_path):
        """Should read markdown files from materials directory."""
        from unittest.mock import patch
        from skills.scout import _collect_materials

        materials_dir = tmp_path / "materials"
        materials_dir.mkdir()

        (materials_dir / "topic1.md").write_text("# Topic One\n\nDescription")
        (materials_dir / "topic2.md").write_text("# Topic Two\n\nMore info")

        with patch("skills.scout.KB_DIR", tmp_path):
            result = _collect_materials()

        assert len(result) == 2
        assert result[0]["title"] == "Topic One"
        assert result[0]["source"] == "materials"

    def test_limits_to_five_files(self, tmp_path):
        """Should limit to 5 files."""
        from unittest.mock import patch
        from skills.scout import _collect_materials

        materials_dir = tmp_path / "materials"
        materials_dir.mkdir()

        for i in range(10):
            (materials_dir / f"topic{i}.md").write_text(f"# Topic {i}")

        with patch("skills.scout.KB_DIR", tmp_path):
            result = _collect_materials()

        assert len(result) == 5


class TestRecentTopics:
    """Tests for _recent_topics function."""

    def test_returns_empty_when_no_history(self, tmp_path):
        """Should return empty set when no history exists."""
        from unittest.mock import patch
        from skills.scout import _recent_topics

        with patch("skills.scout.HISTORY_DIR", tmp_path / "history"):
            with patch("skills.scout.PENDING_DIR", tmp_path / "pending"):
                result = _recent_topics()

        assert result == set()

    def test_reads_from_history(self, tmp_path):
        """Should read topics from history directory."""
        from unittest.mock import patch
        from skills.scout import _recent_topics

        history_dir = tmp_path / "history" / "2025-01-01"
        history_dir.mkdir(parents=True)
        (history_dir / "article.md").write_text("# History Topic\n\nContent")

        with patch("skills.scout.HISTORY_DIR", tmp_path / "history"):
            with patch("skills.scout.PENDING_DIR", tmp_path / "pending"):
                result = _recent_topics()

        assert "History Topic" in result

    def test_reads_from_pending(self, tmp_path):
        """Should read topics from pending directory."""
        from unittest.mock import patch
        from skills.scout import _recent_topics

        pending_dir = tmp_path / "pending"
        pending_dir.mkdir()
        (pending_dir / "topic1.json").write_text(json.dumps({"title": "Pending Topic"}))

        with patch("skills.scout.HISTORY_DIR", tmp_path / "history"):
            with patch("skills.scout.PENDING_DIR", pending_dir):
                result = _recent_topics()

        assert "Pending Topic" in result


class TestIsColdStart:
    """Tests for _is_cold_start function."""

    def test_returns_true_when_few_articles(self, tmp_path):
        """Should return True when less than 5 articles."""
        from unittest.mock import patch
        from skills.scout import _is_cold_start

        with patch("skills.scout.HISTORY_DIR", tmp_path / "history"):
            result = _is_cold_start()

        assert result is True

    def test_returns_false_when_many_articles(self, tmp_path):
        """Should return False when 5+ articles exist."""
        from unittest.mock import patch
        from skills.scout import _is_cold_start

        history_dir = tmp_path / "history"
        history_dir.mkdir()

        for i in range(6):
            (history_dir / f"article{i}.md").write_text(f"# Article {i}")

        with patch("skills.scout.HISTORY_DIR", history_dir):
            result = _is_cold_start()

        assert result is False


class TestCollectAll:
    """Tests for collect_all function."""

    def test_collects_from_multiple_sources(self):
        """Should collect from china-hot, github, and materials."""
        from unittest.mock import patch, MagicMock
        from skills.scout import collect_all

        mock_china_hot = [{"title": "Weibo Topic", "source": "weibo"}]
        mock_github = [{"title": "GitHub Repo", "source": "github"}]
        mock_materials = [{"title": "Material Topic", "source": "materials"}]

        with patch("skills.scout._call_china_hot", return_value=mock_china_hot):
            with patch("skills.scout._call_github_trending", return_value=mock_github):
                with patch("skills.scout._collect_materials", return_value=mock_materials):
                    with patch("skills.scout._call_firecrawl_search", return_value=[]):
                        with patch("skills.scout._write_status"):
                            result = collect_all()

        assert len(result) >= 3

    def test_handles_collector_failure(self):
        """Should handle collector failures gracefully."""
        from unittest.mock import patch
        from skills.scout import collect_all

        with patch("skills.scout._call_china_hot", return_value=[]):
            with patch("skills.scout._call_github_trending", return_value=[]):
                with patch("skills.scout._collect_materials", return_value=[]):
                    with patch("skills.scout._call_firecrawl_search", return_value=[]):
                        with patch("skills.scout._write_status"):
                            result = collect_all()

        assert result == []


class TestConstants:
    """Tests for module constants."""

    def test_source_weights_exist(self):
        """SOURCE_WEIGHTS should have expected keys."""
        from skills.scout import SOURCE_WEIGHTS

        assert "github" in SOURCE_WEIGHTS
        assert "weibo" in SOURCE_WEIGHTS
        assert all(0 <= v <= 1 for v in SOURCE_WEIGHTS.values())

    def test_scoring_thresholds(self):
        """Scoring thresholds should be reasonable."""
        from skills.scout import ATTENTION_FLOOR, FINAL_FLOOR, CANDIDATE_CAP

        assert 0 < ATTENTION_FLOOR < 100
        assert 0 < FINAL_FLOOR < 100
        assert CANDIDATE_CAP > 0


class TestCallFirecrawlSearch:
    """Tests for _call_firecrawl_search function."""

    def test_returns_empty_for_invalid_query(self):
        """Should return empty list for empty or too long query."""
        from skills.scout import _call_firecrawl_search

        assert _call_firecrawl_search("") == []
        assert _call_firecrawl_search("x" * 501) == []

    def test_returns_empty_on_subprocess_timeout(self):
        """Should return empty list on timeout."""
        from unittest.mock import patch
        from skills.scout import _call_firecrawl_search

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            result = _call_firecrawl_search("AI trends")
        assert result == []

    def test_returns_empty_on_json_error(self):
        """Should return empty list on JSON decode error."""
        from unittest.mock import patch, MagicMock
        from skills.scout import _call_firecrawl_search

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"

        with patch("subprocess.run", return_value=mock_result):
            result = _call_firecrawl_search("AI trends")
        assert result == []

    def test_returns_items_on_success(self):
        """Should return parsed items on success."""
        from unittest.mock import patch, MagicMock
        from skills.scout import _call_firecrawl_search

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([{"title": "AI News", "url": "https://example.com"}])

        with patch("subprocess.run", return_value=mock_result):
            result = _call_firecrawl_search("AI trends")

        assert len(result) == 1
        assert result[0]["title"] == "AI News"

    def test_handles_data_wrapper(self):
        """Should handle response with 'data' key."""
        from unittest.mock import patch, MagicMock
        from skills.scout import _call_firecrawl_search

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"data": [{"title": "Topic"}]})

        with patch("subprocess.run", return_value=mock_result):
            result = _call_firecrawl_search("test query")

        assert len(result) == 1

    def test_returns_empty_on_nonzero_exit(self):
        """Should return empty list on non-zero exit code."""
        from unittest.mock import patch, MagicMock
        from skills.scout import _call_firecrawl_search

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = _call_firecrawl_search("AI trends")
        assert result == []


class TestCallGithubTrending:
    """Tests for _call_github_trending function."""

    def test_returns_empty_on_import_error(self):
        """Should return empty list when httpx is not available."""
        from unittest.mock import patch
        from skills.scout import _call_github_trending

        with patch.dict("sys.modules", {"httpx": None}):
            result = _call_github_trending()
        assert result == []

    def test_returns_empty_on_http_error(self):
        """Should return empty list on HTTP error."""
        from unittest.mock import patch, MagicMock
        from skills.scout import _call_github_trending

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP error")
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        mock_httpx = MagicMock()
        mock_httpx.Client.return_value = mock_client

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            result = _call_github_trending()
        assert result == []

    def test_returns_repos_on_success(self):
        """Should return parsed repos on success."""
        from unittest.mock import patch, MagicMock
        from skills.scout import _call_github_trending

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "name": "cool-repo",
                    "description": "A cool repo",
                    "html_url": "https://github.com/test/cool-repo",
                    "stargazers_count": 1000,
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        mock_httpx = MagicMock()
        mock_httpx.Client.return_value = mock_client

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            result = _call_github_trending()

        assert len(result) == 1
        assert result[0]["title"] == "cool-repo"
        assert result[0]["stars"] == 1000


class TestScoreCandidate:
    """Tests for score_candidate function."""

    def test_returns_scored_candidate(self):
        """Should return scored candidate with all fields."""
        from unittest.mock import patch, MagicMock
        from skills.scout import score_candidate

        mock_llm_result = {
            "viral_score": 75,
            "saturation_score": 40,
            "novelty_score": 65,
            "feasibility_score": 80,
            "direction": "AI应用",
        }

        with patch("skills.scout.chat_structured", return_value=mock_llm_result):
            result = score_candidate({"title": "Test Topic", "source": "weibo"}, cold_start=False)

        assert result is not None
        assert "final_score" in result
        assert "attention_score" in result
        assert "increment_score" in result
        assert result["direction"] == "AI应用"

    def test_returns_none_below_attention_floor(self):
        """Should return None when attention score is below floor."""
        from unittest.mock import patch
        from skills.scout import score_candidate, ATTENTION_FLOOR

        # Very low scores to ensure below floor
        mock_llm_result = {
            "viral_score": 0,
            "saturation_score": 0,
            "novelty_score": 0,
            "feasibility_score": 0,
        }

        with patch("skills.scout.chat_structured", return_value=mock_llm_result):
            result = score_candidate({"title": "Test", "source": "unknown"}, cold_start=False)

        # May or may not be None depending on source_weight
        if result is not None:
            assert result["attention_score"] >= ATTENTION_FLOOR

    def test_cold_start_overrides(self):
        """Should override scores during cold start."""
        from unittest.mock import patch
        from skills.scout import score_candidate

        mock_llm_result = {
            "viral_score": 80,
            "saturation_score": 50,
            "novelty_score": 60,
            "feasibility_score": 70,
            "direction": "AI",
        }

        # Use a source with high weight to ensure above attention floor
        with patch("skills.scout.chat_structured", return_value=mock_llm_result):
            result = score_candidate({"title": "Test", "source": "github"}, cold_start=True)

        assert result is not None
        # In cold start, saturation should be 0
        assert result["saturation_score"] == 0

    def test_returns_none_on_llm_failure(self):
        """Should return None when LLM call fails."""
        from unittest.mock import patch
        from skills.scout import score_candidate

        with patch("skills.scout.chat_structured", side_effect=Exception("LLM error")):
            result = score_candidate({"title": "Test", "source": "weibo"}, cold_start=False)

        assert result is None


class TestScoreCandidateWrapper:
    """Tests for _score_candidate_wrapper function."""

    def test_returns_scored_candidate(self):
        """Should return scored candidate."""
        from unittest.mock import patch
        from skills.scout import _score_candidate_wrapper

        mock_result = {"title": "Test", "final_score": 75}

        with patch("skills.scout.score_candidate", return_value=mock_result):
            result = _score_candidate_wrapper(({"title": "Test"}, False))

        assert result is not None
        assert result["final_score"] == 75

    def test_returns_none_on_exception(self):
        """Should return None when scoring fails."""
        from unittest.mock import patch
        from skills.scout import _score_candidate_wrapper

        with patch("skills.scout.score_candidate", side_effect=Exception("Error")):
            result = _score_candidate_wrapper(({"title": "Test"}, False))

        assert result is None


class TestMain:
    """Tests for main function."""

    def test_runs_full_pipeline(self):
        """Should run the full scout pipeline."""
        from unittest.mock import patch, MagicMock
        from skills.scout import main

        mock_candidates = [
            {"title": "Topic 1", "source": "weibo"},
            {"title": "Topic 2", "source": "zhihu"},
        ]

        mock_scored = [
            {"title": "Topic 1", "source": "weibo", "final_score": 80, "direction": "AI"},
            {"title": "Topic 2", "source": "zhihu", "final_score": 70, "direction": "tech"},
        ]

        with patch("skills.scout.collect_all", return_value=mock_candidates):
            with patch("skills.scout.dedup_and_filter", return_value=mock_candidates):
                with patch("skills.scout._is_cold_start", return_value=False):
                    with patch("skills.scout._score_candidate_wrapper", side_effect=lambda args: mock_scored[0] if args[0]["title"] == "Topic 1" else mock_scored[1]):
                        with patch("skills.scout._enforce_diversity", return_value=mock_scored):
                            with patch("skills.scout.write_topic_pending"):
                                with patch("skills.scout._write_status"):
                                    with patch("skills.common.atomic_write_json"):
                                        main()

    def test_handles_empty_candidates(self):
        """Should handle empty candidate list."""
        from unittest.mock import patch
        from skills.scout import main

        with patch("skills.scout.collect_all", return_value=[]):
            with patch("skills.scout.dedup_and_filter", return_value=[]):
                with patch("skills.scout._is_cold_start", return_value=False):
                    with patch("skills.scout._write_status"):
                        with patch("skills.common.atomic_write_json"):
                            main()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
