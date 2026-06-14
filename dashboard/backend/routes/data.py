"""Data routes — cost tracking and analytics."""

import logging
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Query

from config.settings import KB_DIR, PROJECT_ROOT
from dashboard.backend.database import (
    check_budget_limit,
    get_approval_records,
    get_pipeline_sessions,
    get_token_usage_stats,
)

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
            return {"daily": [], "monthly_total": 0, "error": "数据加载失败，请稍后重试"}
        import csv
        import io
        lines = cost_path.read_text().strip().split("\n")[1:]
        daily: dict[str, float] = {}
        for line in lines:
            try:
                reader = csv.reader(io.StringIO(line))
                parts = next(reader)
                if len(parts) >= 4:
                    date = parts[0][:10]
                    total_tokens = int(parts[3])
                    # Use default cost from model config (0.003/1K fallback)
                    from dashboard.backend.config_service import get_model_config
                    model_cfg = get_model_config()
                    rate = model_cfg.get("default_cost_per_1k", 0.003)
                    cost = total_tokens * rate / 1000
                    daily[date] = daily.get(date, 0) + cost
            except (ValueError, StopIteration):
                continue
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
        for f in sorted(viral_dir.glob("*.json")):
            file_data = read_json(f)
            # Only merge list fields, don't overwrite with dict.update()
            if isinstance(file_data, dict):
                for key in ("topics", "keywords"):
                    if key in file_data and isinstance(file_data[key], list):
                        data.setdefault(key, []).extend(file_data[key])

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


@router.get("/approval-stats")
def get_approval_stats(days: int = Query(30, ge=1, le=90)):
    """Get approval statistics including pass/reject rates and rewrite distribution."""
    try:
        records = get_approval_records(limit=1000)

        # Filter by date range
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = []
        for r in records:
            created = r.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if dt >= cutoff:
                        recent.append(r)
                except (ValueError, TypeError):
                    recent.append(r)  # include if can't parse

        total = len(recent)
        if total == 0:
            return {
                "total": 0,
                "pass_rate": 0,
                "reject_rate": 0,
                "rewrite_rate": 0,
                "by_action": {},
                "daily_trend": [],
            }

        by_action = Counter(r.get("action", "unknown") for r in recent)
        pass_count = by_action.get("pass", 0)
        reject_count = by_action.get("reject", 0)
        rewrite_count = by_action.get("rewrite", 0)

        # Daily trend
        daily: dict[str, dict] = {}
        for r in recent:
            created = r.get("created_at", "")
            if created:
                date = created[:10]
                if date not in daily:
                    daily[date] = {"pass": 0, "reject": 0, "rewrite": 0, "total": 0}
                action = r.get("action", "unknown")
                daily[date][action] = daily[date].get(action, 0) + 1
                daily[date]["total"] += 1

        daily_trend = [
            {"date": d, **counts}
            for d, counts in sorted(daily.items())
        ]

        return {
            "total": total,
            "pass_rate": round(pass_count / total * 100, 1),
            "reject_rate": round(reject_count / total * 100, 1),
            "rewrite_rate": round(rewrite_count / total * 100, 1),
            "by_action": dict(by_action),
            "daily_trend": daily_trend,
        }
    except Exception as e:
        logger.error(f"Error getting approval stats: {e}")
        return {"total": 0, "error": str(e)}


@router.get("/topic-distribution")
def get_topic_distribution():
    """Get topic distribution from kb/history/ for word cloud visualization."""
    from dashboard.backend.helpers import read_json
    import re

    history_dir = KB_DIR / "history"
    if not history_dir.exists():
        return {"topics": [], "keywords": [], "directions": {}}

    topic_counter: Counter = Counter()
    keyword_counter: Counter = Counter()
    direction_counter: Counter = Counter()

    for date_dir in sorted(history_dir.iterdir(), reverse=True)[:30]:  # last 30 days
        if not date_dir.is_dir():
            continue

        # Check meta files for structured data
        for meta_file in date_dir.glob("*.meta.json"):
            meta = read_json(meta_file)
            if not meta:
                continue

            # Extract topic direction
            analysis = meta.get("analysis", {})
            tags = analysis.get("tags", [])
            for tag in tags:
                direction_counter[tag] += 1

            # Extract keywords
            keywords = analysis.get("keywords", [])
            for kw in keywords:
                keyword_counter[kw.lower()] += 1

        # Extract topics from markdown files
        for md_file in date_dir.glob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8", errors="ignore")
                title = text.split("\n")[0].removeprefix("# ").strip()
                if title:
                    topic_counter[title] += 1

                    # Simple keyword extraction from title (fallback for files without LLM analysis)
                    words = re.findall(r'[一-鿿]{2,}', title)
                    for w in words:
                        keyword_counter[w] += 1
            except OSError:
                continue

    return {
        "topics": [{"text": t, "count": c} for t, c in topic_counter.most_common(50)],
        "keywords": [{"text": k, "count": c} for k, c in keyword_counter.most_common(50)],
        "directions": dict(direction_counter.most_common(20)),
    }
