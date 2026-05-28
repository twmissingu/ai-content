"""Token usage tracking and budget control."""

import json as _json
import logging
from pathlib import Path

from .core import get_db

logger = logging.getLogger("gaoding.database")


def _load_model_costs() -> tuple[dict[str, float], float]:
    """Load model cost rates from config/models.json."""
    config_path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "models.json"
    default_cost = 0.003
    if not config_path.exists():
        return {}, default_cost
    try:
        data = _json.loads(config_path.read_text())
        models = data.get("models", {})
        costs = {name: cfg.get("cost_per_1k_tokens", default_cost) for name, cfg in models.items()}
        return costs, data.get("default_cost_per_1k", default_cost)
    except Exception:
        return {}, default_cost


_MODEL_COSTS, _DEFAULT_COST = _load_model_costs()


def log_token_usage(agent: str, model: str, input_tokens: int,
                   output_tokens: int, session_id: int = None) -> int:
    """Log token usage with cost estimation."""
    base_cost = _MODEL_COSTS.get(model, _DEFAULT_COST)
    estimated_cost = (input_tokens + output_tokens) * base_cost / 1000

    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO token_usage (session_id, agent, model, input_tokens, output_tokens, estimated_cost)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, agent, model, input_tokens, output_tokens, estimated_cost))
        return cursor.lastrowid


def get_token_usage_stats(days: int = 30) -> dict:
    """Get token usage statistics for the last N days."""
    with get_db() as conn:
        daily = conn.execute("""
            SELECT
                DATE(created_at) as date,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(estimated_cost) as cost,
                COUNT(*) as call_count
            FROM token_usage
            WHERE created_at >= DATE('now', ? || ' days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """, (f'-{days}',)).fetchall()

        by_agent = conn.execute("""
            SELECT
                agent,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(estimated_cost) as cost,
                COUNT(*) as call_count
            FROM token_usage
            WHERE created_at >= DATE('now', ? || ' days')
            GROUP BY agent
            ORDER BY cost DESC
        """, (f'-{days}',)).fetchall()

        monthly = conn.execute("""
            SELECT
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(estimated_cost) as cost,
                COUNT(*) as call_count
            FROM token_usage
            WHERE created_at >= DATE('now', 'start of month')
        """).fetchone()

        return {
            'daily': [dict(row) for row in daily],
            'by_agent': [dict(row) for row in by_agent],
            'monthly': dict(monthly) if monthly else {},
        }


def get_monthly_cost() -> float:
    """Get current month's total cost."""
    with get_db() as conn:
        result = conn.execute("""
            SELECT COALESCE(SUM(estimated_cost), 0) as total
            FROM token_usage
            WHERE created_at >= DATE('now', 'start of month')
        """).fetchone()
        return result['total']


def check_budget_limit(budget_usd: float = None) -> dict:
    """Check if monthly cost exceeds budget limit."""
    if budget_usd is None:
        try:
            from .config_ops import get_config_value
            config_value = get_config_value('budget')
            if config_value and isinstance(config_value, dict):
                budget_usd = config_value.get('monthly_limit_usd', 15.0)
            else:
                budget_usd = 15.0
        except Exception:
            budget_usd = 15.0

    current_cost = get_monthly_cost()
    percentage = (current_cost / budget_usd * 100) if budget_usd > 0 else 0

    return {
        'current_cost': round(current_cost, 4),
        'budget': budget_usd,
        'percentage': round(percentage, 2),
        'is_warning': percentage >= 80,
        'is_exceeded': percentage >= 100,
        'remaining': round(max(0, budget_usd - current_cost), 4),
    }
