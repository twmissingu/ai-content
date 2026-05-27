"""Shared LLM utility — all agents call LLM through this module.

Reads Hermes-provider config from env (XIAOMI_API_KEY, LLM_BASE_URL, LLM_MODEL).
Uses direct HTTP (OpenAI-compatible) so agents are not coupled to Hermes internals.

Fallback chain: reads config/model_fallback.json for ordered fallback models.
Primary model (LLM_MODEL) is tried first; on failure each fallback is tried in order.

Thread Safety:
- Uses threading.local() for per-thread state (current agent, last model)
- Uses threading.Lock() for shared resources (HTTP client, CSV writes)
- Safe for concurrent use by multiple agents
"""

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

import httpx

from config.settings import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_MAX_TOKENS,
    LOGS_DIR,
    require_api_key,
)

# Logger for this module
logger = logging.getLogger("gaoding.llm")


class LLMError(Exception):
    """Raised when the LLM call fails after exhausting all fallback models."""


# ── Thread-local state ─────────────────────────────────────────────
_thread_local = threading.local()


def set_current_agent(agent: str) -> None:
    """Set the current agent name for token tracking (thread-safe)."""
    _thread_local.current_agent = agent


def get_current_agent() -> str:
    """Get the current agent name (thread-safe)."""
    return getattr(_thread_local, 'current_agent', 'unknown')


def get_last_model() -> str:
    """Return the model that was last used (thread-safe)."""
    return getattr(_thread_local, 'last_model_used', LLM_MODEL)


def _set_last_model(model: str) -> None:
    """Set the last used model (thread-safe)."""
    _thread_local.last_model_used = model


# ── Fallback chain ─────────────────────────────────────────────────
def _load_fallback_chain() -> list[dict]:
    """Read model fallback chain from config/model_fallback.json.

    Returns list of fallback config dicts (may be empty).
    The primary model is NOT included here — it's tried first separately.
    """
    path = Path(__file__).resolve().parent.parent / "config" / "model_fallback.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data.get("fallbacks", [])
    except (json.JSONDecodeError, OSError):
        return []


# Load once at module level (immutable after import)
FALLBACK_CHAIN: list[dict] = _load_fallback_chain()


# ── HTTP Client (thread-safe singleton) ────────────────────────────
class _HTTPClientManager:
    """Thread-safe HTTP client singleton manager."""
    
    def __init__(self):
        self._client: Optional[httpx.Client] = None
        self._lock = threading.Lock()
    
    def get_client(self, base_url: Optional[str] = None, api_key: Optional[str] = None) -> httpx.Client:
        """Get or create HTTP client."""
        with self._lock:
            if self._client is None:
                self._client = self._make_client(base_url, api_key)
            return self._client
    
    def _make_client(self, base_url: Optional[str] = None, api_key: Optional[str] = None) -> httpx.Client:
        """Create a new httpx client."""
        key = api_key or LLM_API_KEY or require_api_key("XIAOMI_API_KEY")
        
        # Log masked key for debugging
        masked_key = f"{key[:4]}****{key[-4:]}" if len(key) > 8 else "****"
        logger.debug(f"Creating LLM client with key: {masked_key}")
        
        return httpx.Client(
            base_url=base_url or LLM_BASE_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            timeout=120,
        )
    
    def reset(self) -> None:
        """Reset the client (for testing or config changes)."""
        with self._lock:
            if self._client:
                self._client.close()
                self._client = None


# Module-level client manager
_client_manager = _HTTPClientManager()


def _get_client() -> httpx.Client:
    """Return the thread-safe httpx singleton."""
    return _client_manager.get_client()


# ── Cost tracking (thread-safe) ────────────────────────────────────
_cost_lock = threading.Lock()


def _record_usage(data: dict, agent: str = "unknown") -> None:
    """Record token usage to CSV and SQLite database (thread-safe)."""
    usage = data.get("usage", {})
    if not usage:
        return
    
    used_model = get_last_model()
    prompt_tokens = usage.get('prompt_tokens', 0)
    completion_tokens = usage.get('completion_tokens', 0)
    total_tokens = usage.get('total_tokens', 0)
    
    # Record to CSV (with lock for thread safety)
    with _cost_lock:
        try:
            cost_path = LOGS_DIR / "cost.csv"
            cost_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if file exists and has old header (5 columns vs 6)
            needs_migration = False
            if cost_path.exists():
                with open(cost_path, 'r') as f:
                    first_line = f.readline().strip()
                    # Old header: timestamp,prompt_tokens,completion_tokens,total_tokens,model
                    if first_line and 'agent' not in first_line:
                        needs_migration = True
            
            if needs_migration:
                # Migrate: read all lines, add agent column, rewrite
                with open(cost_path, 'r') as f:
                    lines = f.readlines()
                with open(cost_path, 'w') as f:
                    f.write("timestamp,prompt_tokens,completion_tokens,total_tokens,model,agent\n")
                    for line in lines[1:]:  # skip old header
                        line = line.rstrip('\n')
                        if line:
                            f.write(f"{line},unknown\n")
                logger.info("Migrated cost.csv to new format with agent column")
            elif not cost_path.exists():
                cost_path.write_text("timestamp,prompt_tokens,completion_tokens,total_tokens,model,agent\n")
            
            row = (
                f"{time.strftime('%Y-%m-%dT%H:%M:%S')},"
                f"{prompt_tokens},"
                f"{completion_tokens},"
                f"{total_tokens},"
                f"{used_model},"
                f"{agent}\n"
            )
            with open(cost_path, "a") as f:
                f.write(row)
                f.flush()
        except Exception as e:
            logger.warning(f"Failed to write cost CSV: {e}")
    
    # Record to SQLite database (non-blocking)
    try:
        from dashboard.backend.database import log_token_usage
        log_token_usage(
            agent=agent,
            model=used_model,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
        )
    except Exception as e:
        # Don't fail if database logging fails
        logger.debug(f"Failed to log to database: {e}")


# ── Main API functions ─────────────────────────────────────────────

def chat(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
    json_mode: bool = False,
    track_cost: bool = True,
) -> str:
    """Send a chat completion request and return the text content.

    Parameters
    ----------
    system_prompt : str
        System-level instruction.
    user_prompt : str
        The user message.
    model : str, optional
        Override the default model.
    max_tokens : int, optional
        Override default max output tokens.
    temperature : float
        Sampling temperature (default 0.7).
    json_mode : bool
        If True, request structured JSON output.
    track_cost : bool
        If True, log token usage to data/logs/cost.csv.

    Returns
    -------
    str
        The model's response text.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Collect models to try: explicit override, or primary + fallbacks
    if model:
        models_to_try = [model]
    else:
        models_to_try = [LLM_MODEL] + [f.get("model", "") for f in FALLBACK_CHAIN]
        models_to_try = [m for m in models_to_try if m]  # remove empties

    last_error: Optional[Exception] = None
    data = None

    for attempt_model in models_to_try:
        body: dict = {
            "model": attempt_model,
            "messages": messages,
            "max_tokens": max_tokens or LLM_MAX_TOKENS,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        try:
            resp = _get_client().post("/chat/completions", json=body)
            resp.raise_for_status()
            data = resp.json()
            _set_last_model(attempt_model)
            break  # success — exit the retry loop
        except httpx.HTTPStatusError as e:
            last_error = e
            detail = e.response.text[:200]
            logger.warning(f"Model {attempt_model} failed (HTTP {e.response.status_code}): {detail}")
            if attempt_model == models_to_try[-1]:
                raise LLMError(f"LLM API error {e.response.status_code}: {detail}") from e
        except httpx.TimeoutException as e:
            last_error = e
            logger.warning(f"Model {attempt_model} timed out")
            if attempt_model == models_to_try[-1]:
                raise LLMError("LLM request timed out after 120s") from e
        except Exception as e:
            last_error = e
            logger.warning(f"Model {attempt_model} failed: {e}")
            if attempt_model == models_to_try[-1]:
                raise LLMError(f"LLM request failed: {e}") from e

    # Guard (should not reach here if all models failed)
    if data is None:
        raise LLMError(f"All {len(models_to_try)} models failed. Last error: {last_error}") from last_error

    # Extract content
    try:
        choice = data["choices"][0]
        content = choice["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected LLM response format: {json.dumps(data, indent=2)[:300]}") from e

    # Cost tracking
    if track_cost:
        _record_usage(data, agent=get_current_agent())

    return content.strip()


def chat_structured(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.3,
) -> dict:
    """Like chat() but enforces JSON output and returns a parsed dict."""
    raw = chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=temperature,
        json_mode=True,
    )
    # Some models return markdown-wrapped JSON even in json_mode
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM returned invalid JSON: {e}\nRaw: {raw[:300]}") from e


def reset_client() -> None:
    """Reset the HTTP client (for testing or config changes)."""
    _client_manager.reset()


# ── Backward compatibility aliases ─────────────────────────────────
# These maintain compatibility with existing code that imports these names

def get_last_model_used() -> str:
    """Alias for get_last_model()."""
    return get_last_model()
