"""Unit tests for the configuration service."""

import json
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


@pytest.fixture(autouse=True)
def mock_config_dir(monkeypatch, tmp_path):
    """Mock config directory for testing."""
    import dashboard.backend.config_service as cs
    monkeypatch.setattr(cs, 'CONFIG_DIR', tmp_path)
    yield tmp_path


class TestScheduleConfig:
    """Test schedule configuration."""
    
    def test_default_schedule(self):
        """Test getting default schedule."""
        from dashboard.backend.config_service import get_schedule_config
        
        config = get_schedule_config()
        assert 'morning_scout' in config
        assert 'evening_scout' in config
        assert 'working_days' in config
        assert config['morning_scout'] == '09:00'
    
    def test_update_schedule(self):
        """Test updating schedule."""
        from dashboard.backend.config_service import update_schedule, get_schedule_config
        
        update_schedule('morning_scout', '08:30')
        
        config = get_schedule_config()
        assert config['morning_scout'] == '08:30'
    
    def test_invalid_schedule_key(self):
        """Test invalid schedule key."""
        from dashboard.backend.config_service import update_schedule
        
        with pytest.raises(ValueError, match="Invalid schedule key"):
            update_schedule('invalid_key', '10:00')


class TestWritingStyles:
    """Test writing style configuration."""
    
    def test_default_styles(self):
        """Test getting default writing styles."""
        from dashboard.backend.config_service import get_writing_styles
        
        styles = get_writing_styles()
        assert 'wechat_default' in styles
        assert 'xiaohongshu_default' in styles
        assert 'douyin_default' in styles
    
    def test_get_specific_style(self):
        """Test getting a specific style."""
        from dashboard.backend.config_service import get_writing_style
        
        style = get_writing_style('wechat_default')
        assert style is not None
        assert style['name'] == '公众号默认'
        assert style['platform'] == 'wechat'
    
    def test_update_style(self):
        """Test updating a style."""
        from dashboard.backend.config_service import update_writing_style, get_writing_style
        
        update_writing_style('wechat_default', {'length': 3000})
        
        style = get_writing_style('wechat_default')
        assert style['length'] == 3000
    
    def test_invalid_style(self):
        """Test updating invalid style."""
        from dashboard.backend.config_service import update_writing_style
        
        with pytest.raises(ValueError, match="Unknown style"):
            update_writing_style('nonexistent', {'length': 1000})


class TestQualityGates:
    """Test quality gate configuration."""
    
    def test_default_gates(self):
        """Test getting default quality gates."""
        from dashboard.backend.config_service import get_quality_gates
        
        gates = get_quality_gates()
        assert 'ai_slop_threshold' in gates
        assert 'critique_threshold' in gates
        assert 'max_rewrite_rounds' in gates
        assert gates['ai_slop_threshold'] == 70
    
    def test_update_gates(self):
        """Test updating quality gates."""
        from dashboard.backend.config_service import update_quality_gates, get_quality_gates
        
        update_quality_gates({'ai_slop_threshold': 75})
        
        gates = get_quality_gates()
        assert gates['ai_slop_threshold'] == 75


class TestSourceConfig:
    """Test source configuration."""
    
    def test_default_sources(self):
        """Test getting default sources."""
        from dashboard.backend.config_service import get_source_config
        
        sources = get_source_config()
        assert 'weibo' in sources
        assert 'zhihu' in sources
        assert 'twitter' in sources
        assert sources['weibo']['enabled'] is True
    
    def test_update_source(self):
        """Test updating a source."""
        from dashboard.backend.config_service import update_source, get_source_config
        
        update_source('weibo', {'enabled': False, 'weight': 0.3})
        
        sources = get_source_config()
        assert sources['weibo']['enabled'] is False
        assert sources['weibo']['weight'] == 0.3


class TestBudgetConfig:
    """Test budget configuration."""
    
    def test_default_budget(self):
        """Test getting default budget."""
        from dashboard.backend.config_service import get_budget_config
        
        budget = get_budget_config()
        assert 'monthly_limit_usd' in budget
        assert 'warning_threshold_pct' in budget
        assert budget['monthly_limit_usd'] == 15.0
    
    def test_update_budget(self):
        """Test updating budget."""
        from dashboard.backend.config_service import update_budget, get_budget_config
        
        update_budget({'monthly_limit_usd': 20.0})
        
        budget = get_budget_config()
        assert budget['monthly_limit_usd'] == 20.0


class TestStylePrompt:
    """Test style prompt generation."""
    
    def test_generate_prompt(self):
        """Test generating a style prompt."""
        from dashboard.backend.config_service import generate_style_prompt
        
        prompt = generate_style_prompt('wechat_default')
        assert len(prompt) > 0
        assert '内容创作者' in prompt
        assert '口语化' in prompt or '强烈观点' in prompt
    
    def test_invalid_style_prompt(self):
        """Test generating prompt for invalid style."""
        from dashboard.backend.config_service import generate_style_prompt
        
        prompt = generate_style_prompt('nonexistent')
        assert prompt == ""


class TestModelConfig:
    """Test model configuration."""
    
    def test_default_model_config(self):
        """Test getting default model config."""
        from dashboard.backend.config_service import get_model_config
        
        config = get_model_config()
        assert 'chain' in config
        assert len(config['chain']) > 0
        assert config['chain'][0]['model'] == 'claude-sonnet-4'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
