"""Config routes — system configuration management."""

import logging

from fastapi import APIRouter, HTTPException

from dashboard.backend.config_service import (
    generate_style_prompt,
    get_all_config_summary,
    get_budget_config,
    get_model_config,
    get_quality_gates,
    get_schedule_config,
    get_source_config,
    get_writing_styles,
    update_budget,
    update_quality_gates,
    update_schedule,
    update_source,
    update_writing_style,
)
from dashboard.backend.database import get_quality_flywheel_data
from dashboard.backend.helpers import load_schedule
from dashboard.backend.models import ConfigUpdate

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
def get_config():
    """Read all system configuration."""
    try:
        return get_all_config_summary()
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return load_schedule()


@router.get("/{section}")
def get_config_section(section: str):
    """Read specific configuration section."""
    section_map = {
        "schedule": get_schedule_config,
        "styles": get_writing_styles,
        "gates": get_quality_gates,
        "sources": get_source_config,
        "model": get_model_config,
        "budget": get_budget_config,
    }

    getter = section_map.get(section)
    if not getter:
        raise HTTPException(404, f"Unknown config section: {section}")

    try:
        return getter()
    except Exception as e:
        logger.error(f"Error reading {section}: {e}")
        raise HTTPException(500, f"读取配置失败: {section}")


@router.post("/schedule")
def update_schedule_config(update: ConfigUpdate):
    """Update schedule configuration."""
    try:
        result = update_schedule(update.key, update.value)

        time_keys = {'morning_scout', 'morning_writer', 'evening_scout', 'evening_writer'}
        needs_restart = update.key in time_keys

        response = {
            "status": "ok",
            "key": update.key,
            "value": update.value,
        }

        if needs_restart:
            response["message"] = "配置已更新。需要重启 Hermes gateway 才能使新的调度时间生效。"
            response["needs_restart"] = True

        return response

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error updating schedule: {e}")
        raise HTTPException(500, "更新调度配置失败")


@router.post("/styles/{style_name}")
def update_style_config(style_name: str, updates: dict):
    """Update a writing style preset."""
    try:
        result = update_writing_style(style_name, updates)
        return {"status": "ok", "style": style_name, "config": result}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error updating style: {e}")
        raise HTTPException(500, "更新写作风格失败")


@router.post("/gates")
def update_gates_config(updates: dict):
    """Update quality gate thresholds."""
    try:
        result = update_quality_gates(updates)
        return {"status": "ok", "config": result}
    except Exception as e:
        logger.error(f"Error updating gates: {e}")
        raise HTTPException(500, "更新质量门禁失败")


@router.post("/sources/{source_name}")
def update_source_config(source_name: str, updates: dict):
    """Update source configuration."""
    try:
        result = update_source(source_name, updates)
        return {"status": "ok", "source": source_name, "config": result}
    except Exception as e:
        logger.error(f"Error updating source: {e}")
        raise HTTPException(500, "更新数据源配置失败")


@router.post("/budget")
def update_budget_config(updates: dict):
    """Update budget configuration."""
    try:
        result = update_budget(updates)
        return {"status": "ok", "config": result}
    except Exception as e:
        logger.error(f"Error updating budget: {e}")
        raise HTTPException(500, "更新预算配置失败")


@router.get("/style-prompt/{style_name}")
def get_style_prompt(style_name: str):
    """Get generated prompt for a writing style."""
    prompt = generate_style_prompt(style_name)
    if not prompt:
        raise HTTPException(404, f"Unknown style: {style_name}")
    return {"style": style_name, "prompt": prompt}


@router.get("/quality-flywheel")
def get_quality_flywheel():
    """Get quality gate recommendations based on approval history.

    Analyzes approved/rejected article scores to suggest optimal thresholds.
    This is the 'quality flywheel' — the system learns from human feedback
    to automatically calibrate quality gates.
    """
    try:
        return get_quality_flywheel_data()
    except Exception as e:
        logger.error(f"Error getting flywheel data: {e}")
        raise HTTPException(500, "获取质量飞轮数据失败")
