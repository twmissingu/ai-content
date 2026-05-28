"""SQLite database layer for Dashboard.

Re-exports all functions from domain modules for backward compatibility.
All existing imports like `from dashboard.backend.database import get_db` continue to work.
"""

# Core: connection, cache, init
from .core import (
    DATABASE_PATH,
    cached_query,
    get_db,
    init_db,
    _invalidate_cache,
)

# Pipeline sessions
from .sessions import (
    create_pipeline_session,
    get_pipeline_sessions,
    get_today_sessions,
    update_pipeline_session,
)

# Platform versions + approval records
from .versions import (
    create_approval_record,
    create_platform_version,
    get_approval_records,
    get_pending_versions,
    get_platform_versions,
    get_quality_flywheel_data,
    update_platform_version,
)

# Token usage + budget
from .tokens import (
    check_budget_limit,
    get_monthly_cost,
    get_token_usage_stats,
    log_token_usage,
)

# Configuration entries
from .config_ops import (
    get_all_config,
    get_config_value,
    get_pending_config,
    set_config_value,
)

# Pipeline execution traces (n8n-style)
from .traces import (
    complete_trace,
    create_trace,
    get_trace_summaries_batch,
    get_trace_summary,
    get_traces,
    trace_stage,
    update_trace_duration,
)

# Prompt version management
from .prompts import (
    activate_prompt,
    delete_prompt_version,
    get_prompt,
    import_prompts_from_files,
    list_prompt_versions,
    list_prompts,
    save_prompt,
)

__all__ = [
    # Core
    'DATABASE_PATH', 'cached_query', 'get_db', 'init_db', '_invalidate_cache',
    # Sessions
    'create_pipeline_session', 'get_pipeline_sessions', 'get_today_sessions', 'update_pipeline_session',
    # Versions + Approval
    'create_approval_record', 'create_platform_version', 'get_approval_records',
    'get_pending_versions', 'get_platform_versions', 'get_quality_flywheel_data', 'update_platform_version',
    # Tokens + Budget
    'check_budget_limit', 'get_monthly_cost', 'get_token_usage_stats', 'log_token_usage',
    # Config
    'get_all_config', 'get_config_value', 'get_pending_config', 'set_config_value',
    # Traces
    'complete_trace', 'create_trace', 'get_trace_summaries_batch', 'get_trace_summary', 'get_traces', 'trace_stage', 'update_trace_duration',
    # Prompts
    'activate_prompt', 'delete_prompt_version', 'get_prompt', 'import_prompts_from_files',
    'list_prompt_versions', 'list_prompts', 'save_prompt',
]
