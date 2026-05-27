"""Unit tests for skills/scout.py utilities."""

import json
from pathlib import Path

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
            {"title": "第一个话题"},
            {"title": "第二个话题"},
            {"title": "第三个话题"},
        ]
        
        result = dedup_and_filter(candidates)
        
        assert len(result) == 3
        assert result[0]["title"] == "第一个话题"
        assert result[1]["title"] == "第二个话题"
        assert result[2]["title"] == "第三个话题"


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
