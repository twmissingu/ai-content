"""Data routes — cost tracking and analytics."""

import logging
from pathlib import Path

from fastapi import APIRouter

from config.settings import KB_DIR, PROJECT_ROOT
from dashboard.backend.database import check_budget_limit, get_pipeline_sessions, get_token_usage_stats

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/cost")
def get_cost_data():
    """Read cost tracking data from database."""
    try:
        stats = get_token_usage_stats(days=30)

        daily_list = []
        for row in stats.get('daily', []):
            daily_list.append({
                "date": row['date'],
                "cost": round(row.get('cost', 0), 4),
                "input_tokens": row.get('input_tokens', 0),
                "output_tokens": row.get('output_tokens', 0),
                "call_count": row.get('call_count', 0),
            })

        monthly = stats.get('monthly', {})
        monthly_total = round(monthly.get('cost', 0), 4)
        by_agent = stats.get('by_agent', [])

        return {
            "daily": daily_list,
            "monthly_total": monthly_total,
            "by_agent": by_agent,
            "budget": check_budget_limit(),
        }
    except Exception as e:
        logger.error(f"Error getting cost data: {e}")
        cost_path = PROJECT_ROOT / "data/logs/cost.csv"
        if not cost_path.exists():
            return {"daily": [], "monthly_total": 0, "error": str(e)}
        lines = cost_path.read_text().strip().split("\n")[1:]
        daily: dict[str, float] = {}
        for line in lines:
            parts = line.split(",")
            if len(parts) >= 4:
                date = parts[0][:10]
                total_tokens = int(parts[3])
                cost = total_tokens * 0.003 / 1000
                daily[date] = daily.get(date, 0) + cost
        daily_list = [{"date": d, "cost": round(c, 4)} for d, c in sorted(daily.items())]
        monthly = round(sum(daily.values()), 4)
        return {"daily": daily_list, "monthly_total": monthly, "source": "csv_fallback"}


@router.get("/analytics")
def get_analytics():
    """Read analytics data from database and kb/viral/."""
    from dashboard.backend.helpers import read_json

    data = {"topics": [], "keywords": []}

    viral_dir = KB_DIR / "viral"
    if viral_dir.exists():
        for f in viral_dir.glob("*.json"):
            data.update(read_json(f))

    try:
        sessions_result = get_pipeline_sessions(limit=30)
        sessions = sessions_result.get('items', [])
        data['pipeline_stats'] = {
            'total_sessions': sessions_result.get('total', len(sessions)),
            'completed': sum(1 for s in sessions if s.get('status') == 'completed'),
            'failed': sum(1 for s in sessions if s.get('status') == 'failed'),
            'running': sum(1 for s in sessions if s.get('status') == 'running'),
        }
    except Exception as e:
        logger.error(f"Error getting pipeline stats: {e}")

    return data
