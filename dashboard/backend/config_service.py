"""Configuration management service.

Implements PRD 9.1-9.5:
- Schedule configuration with dual-version preview
- Writing style presets
- Quality gate thresholds
- Source toggles
- Model fallback chain
- Monthly budget control
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import (
    CONFIG_DIR,
    MONTHLY_BUDGET_USD,
    QUALITY_THRESHOLD,
    MAX_REWRITE_ROUNDS,
    STAGE_TIMEOUT_MINUTES,
)


def get_default_schedule() -> dict:
    """Get default schedule configuration."""
    return {
        "morning_scout": "09:00",
        "morning_writer": "09:30",
        "morning_approval": "10:45",
        "morning_publish": "11:00",
        "evening_scout": "14:00",
        "evening_writer": "14:30",
        "evening_approval": "16:15",
        "evening_publish": "16:30",
        "feedback_time": "22:00",
        "working_days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "quiet_start": 22,
        "quiet_end": 8,
    }


def get_default_writing_styles() -> dict:
    """Get default writing style presets."""
    return {
        "wechat_default": {
            "name": "公众号默认",
            "platform": "wechat",
            "length": 2500,
            "tone": "口语化",
            "stance": "强烈观点",
            "person": "第一人称(我)",
            "sentence": "短句为主",
            "expertise": "小白友好",
            "structure": "开头3秒抓人 → 层层递进论证 → 总结观点",
            "illustrations": 3,
        },
        "xiaohongshu_default": {
            "name": "小红书默认",
            "platform": "xiaohongshu",
            "length": 600,
            "tone": "轻松口语化+emoji",
            "stance": "第一人称经验分享",
            "person": "第一人称(我)",
            "sentence": "短句为主",
            "expertise": "小白友好",
            "structure": "开头痛点/好奇 → 主体干货 → 结尾互动引导",
            "illustrations": 6,
        },
        "douyin_default": {
            "name": "抖音脚本",
            "platform": "douyin",
            "length": 300,
            "tone": "口语化，语速快",
            "stance": "抓眼球",
            "person": "第一人称(我)",
            "sentence": "短句为主",
            "expertise": "小白友好",
            "structure": "前三秒抓眼球 → 核心观点 → 行动引导",
            "illustrations": 0,
        },
    }


def get_default_quality_gates() -> dict:
    """Get default quality gate thresholds."""
    return {
        "ai_slop_threshold": QUALITY_THRESHOLD,
        "critique_threshold": QUALITY_THRESHOLD,
        "max_rewrite_rounds": MAX_REWRITE_ROUNDS,
        "topic_score_floor": 55,
        "attention_floor": 40,
    }


def get_default_sources() -> dict:
    """Get default source configuration."""
    return {
        "weibo": {"enabled": True, "weight": 0.50},
        "zhihu": {"enabled": True, "weight": 0.70},
        "bilibili": {"enabled": True, "weight": 0.55},
        "baidu": {"enabled": True, "weight": 0.40},
        "douyin": {"enabled": True, "weight": 0.45},
        "toutiao": {"enabled": True, "weight": 0.50},
        "kr36": {"enabled": True, "weight": 0.70},
        "twitter": {"enabled": True, "weight": 0.95},
        "rss": {"enabled": True, "weight": 0.85},
        "github": {"enabled": True, "weight": 0.80},
        "web_search": {"enabled": True, "weight": 0.75},
        "materials": {"enabled": True, "weight": 0.90},
    }


def get_default_model_config() -> dict:
    """Get default model fallback configuration."""
    return {
        "chain": [
            {"provider": "anthropic", "model": "claude-sonnet-4", "label": "Claude Sonnet 4"},
            {"provider": "openai", "model": "gpt-4o", "label": "GPT-4o"},
            {"provider": "deepseek", "model": "deepseek-v3", "label": "DeepSeek V3"},
        ],
        "timeout_seconds": 60,
        "retry_on_error": True,
        "max_retries": 2,
    }


def get_default_budget() -> dict:
    """Get default budget configuration."""
    return {
        "monthly_limit_usd": MONTHLY_BUDGET_USD,
        "warning_threshold_pct": 80,
        "auto_pause_on_exceed": True,
        "notify_on_warning": True,
    }


def load_config_from_file(filename: str, defaults: dict = None) -> dict:
    """Load configuration from JSON file."""
    path = CONFIG_DIR / filename
    if path.exists():
        try:
            data = json.loads(path.read_text())
            if defaults:
                # Merge with defaults
                merged = {**defaults, **data}
                return merged
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return defaults or {}


def save_config_to_file(filename: str, config: dict):
    """Save configuration to JSON file with atomic write."""
    import os
    path = CONFIG_DIR / filename
    tmp = CONFIG_DIR / f".{filename}.tmp"
    
    try:
        # Ensure config directory exists
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Write to temp file first (atomic write pattern)
        tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2))
        
        # Sync to disk before rename
        with open(tmp, 'r') as f:
            os.fsync(f.fileno())
        
        # Atomic rename
        os.rename(tmp, path)
    except Exception as e:
        # Clean up temp file on error
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(f"Failed to save config {filename}: {e}")


def get_schedule_config() -> dict:
    """Get schedule configuration with dual-version support."""
    defaults = get_default_schedule()
    config = load_config_from_file("schedule.json", defaults)
    
    # Add dual-version info
    now = datetime.now(timezone.utc)
    config['_current_time'] = now.isoformat()
    config['_effective_now'] = True
    
    return config


def get_writing_styles() -> dict:
    """Get all writing style presets."""
    defaults = get_default_writing_styles()
    return load_config_from_file("writing_styles.json", defaults)


def get_writing_style(style_name: str) -> Optional[dict]:
    """Get a specific writing style preset."""
    styles = get_writing_styles()
    return styles.get(style_name)


def get_quality_gates() -> dict:
    """Get quality gate thresholds."""
    defaults = get_default_quality_gates()
    return load_config_from_file("quality_gates.json", defaults)


def get_source_config() -> dict:
    """Get source configuration."""
    defaults = get_default_sources()
    return load_config_from_file("sources.json", defaults)


def get_model_config() -> dict:
    """Get model fallback configuration."""
    defaults = get_default_model_config()
    return load_config_from_file("model_fallback.json", defaults)


def get_budget_config() -> dict:
    """Get budget configuration."""
    defaults = get_default_budget()
    return load_config_from_file("budget.json", defaults)


def update_schedule(key: str, value: Any) -> dict:
    """Update schedule configuration.
    
    Args:
        key: Configuration key to update
        value: New value
    
    Returns:
        Updated configuration
    
    Note: Changes are applied immediately to the config file.
    For time-based changes, Hermes gateway restart is required.
    """
    config = get_schedule_config()
    
    # Validate key
    valid_keys = {
        'morning_scout', 'morning_writer', 'morning_approval', 'morning_publish',
        'evening_scout', 'evening_writer', 'evening_approval', 'evening_publish',
        'feedback_time', 'working_days', 'quiet_start', 'quiet_end',
    }
    
    if key not in valid_keys:
        raise ValueError(f"Invalid schedule key: {key}")
    
    # Apply immediately
    config[key] = value
    
    # Remove any pending changes for this key
    config.pop(f'_pending_{key}', None)
    
    save_config_to_file("schedule.json", config)
    return config


def update_writing_style(style_name: str, updates: dict) -> dict:
    """Update a writing style preset."""
    styles = get_writing_styles()
    
    if style_name not in styles:
        raise ValueError(f"Unknown style: {style_name}")
    
    styles[style_name].update(updates)
    save_config_to_file("writing_styles.json", styles)
    return styles[style_name]


def update_quality_gates(updates: dict) -> dict:
    """Update quality gate thresholds."""
    gates = get_quality_gates()
    gates.update(updates)
    save_config_to_file("quality_gates.json", gates)
    return gates


def update_source(source_name: str, updates: dict) -> dict:
    """Update source configuration."""
    sources = get_source_config()
    
    if source_name not in sources:
        sources[source_name] = {'enabled': True, 'weight': 0.5}
    
    sources[source_name].update(updates)
    save_config_to_file("sources.json", sources)
    return sources[source_name]


def update_budget(updates: dict) -> dict:
    """Update budget configuration."""
    budget = get_budget_config()
    budget.update(updates)
    save_config_to_file("budget.json", budget)
    return budget


def generate_style_prompt(style_name: str) -> str:
    """Generate LLM prompt from writing style configuration."""
    style = get_writing_style(style_name)
    if not style:
        return ""
    
    parts = []
    
    # Tone
    tone_map = {
        "口语化": "使用口语化的表达方式，就像在和读者面对面聊天。",
        "正式专业": "使用专业、严谨的表达方式。",
        "轻松幽默": "使用轻松幽默的语气，让读者感到愉悦。",
        "犀利批判": "使用犀利、批判性的语气，直接表达观点。",
    }
    if style.get('tone') in tone_map:
        parts.append(tone_map[style['tone']])
    
    # Stance
    stance_map = {
        "强烈观点": "以强烈观点为立场，明确表达态度和结论。",
        "客观中立": "保持客观中立，呈现多方观点。",
        "第一人称经验": "以第一人称经验分享的方式写作。",
    }
    if style.get('stance') in stance_map:
        parts.append(stance_map[style['stance']])
    
    # Length
    length = style.get('length', 2000)
    parts.append(f"篇幅控制在 {length} 字左右。")
    
    # Person
    person_map = {
        "第一人称(我)": "使用第一人称\"我\"来写作。",
        "第二人称(你)": "使用第二人称\"你\"来与读者对话。",
        "第三人称(读者)": "使用第三人称，客观描述。",
    }
    if style.get('person') in person_map:
        parts.append(person_map[style['person']])
    
    # Sentence style
    sentence_map = {
        "短句为主": "句式以短句为主，保持阅读节奏感。",
        "长短结合": "长短句结合，形成节奏变化。",
        "排比修辞": "适当使用排比修辞增强表达力。",
    }
    if style.get('sentence') in sentence_map:
        parts.append(sentence_map[style['sentence']])
    
    # Expertise
    expertise_map = {
        "小白友好": "专业度设为小白友好，避免专业术语，需要解释每个概念。",
        "行业入门": "面向行业入门读者，可以使用基础术语。",
        "深度技术": "面向专业人士，可以使用专业术语和深度分析。",
    }
    if style.get('expertise') in expertise_map:
        parts.append(expertise_map[style['expertise']])
    
    return "你是一位内容创作者。" + " ".join(parts)


def get_all_config_summary() -> dict:
    """Get summary of all configuration."""
    return {
        "schedule": get_schedule_config(),
        "writing_styles": {
            name: style.get('name', name) 
            for name, style in get_writing_styles().items()
        },
        "quality_gates": get_quality_gates(),
        "sources": {
            name: {"enabled": src.get('enabled', True), "weight": src.get('weight', 0.5)}
            for name, src in get_source_config().items()
        },
        "budget": get_budget_config(),
        "model": get_model_config(),
    }


# ── CLI interface ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Configuration management")
    parser.add_argument("--show", action="store_true", help="Show all configuration")
    parser.add_argument("--schedule", action="store_true", help="Show schedule")
    parser.add_argument("--styles", action="store_true", help="Show writing styles")
    parser.add_argument("--gates", action="store_true", help="Show quality gates")
    parser.add_argument("--sources", action="store_true", help="Show sources")
    parser.add_argument("--budget", action="store_true", help="Show budget")
    
    args = parser.parse_args()
    
    if args.show:
        config = get_all_config_summary()
        print(json.dumps(config, indent=2, ensure_ascii=False))
    elif args.schedule:
        print(json.dumps(get_schedule_config(), indent=2, ensure_ascii=False))
    elif args.styles:
        print(json.dumps(get_writing_styles(), indent=2, ensure_ascii=False))
    elif args.gates:
        print(json.dumps(get_quality_gates(), indent=2, ensure_ascii=False))
    elif args.sources:
        print(json.dumps(get_source_config(), indent=2, ensure_ascii=False))
    elif args.budget:
        print(json.dumps(get_budget_config(), indent=2, ensure_ascii=False))
    else:
        parser.print_help()
