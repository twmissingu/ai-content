"""Shared LLM utility — all agents call LLM through this module.

Reads Hermes-provider config from env (XIAOMI_API_KEY, LLM_BASE_URL, LLM_MODEL).
Uses direct HTTP (OpenAI-compatible) so agents are not coupled to Hermes internals.

Fallback chain: reads config/model_fallback.json for ordered fallback models.
Primary model (LLM_MODEL) is tried first; on failure each fallback is tried in order.
"""

import json
import os
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


class LLMError(Exception):
    """Raised when the LLM call fails after exhausting all fallback models."""


# ── Fallback chain ──────────────────────────────────────────────
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


FALLBACK_CHAIN = _load_fallback_chain()
"""List of fallback model configs. Each has at least a 'model' key."""


_HTTP_CLIENT: httpx.Client | None = None
_LAST_MODEL_USED: str = LLM_MODEL


def get_last_model() -> str:
    """Return the model that was last used (primary or fallback)."""
    return _LAST_MODEL_USED


def _make_client(base_url: str | None = None, api_key: str | None = None) -> httpx.Client:
    """Create a new httpx client for a specific endpoint."""
    key = api_key or LLM_API_KEY or require_api_key("XIAOMI_API_KEY")
    return httpx.Client(
        base_url=base_url or LLM_BASE_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        timeout=120,
    )


def _get_client() -> httpx.Client:
    """Return the module-level httpx singleton (connection reuse)."""
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = _make_client()
    return _HTTP_CLIENT


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

    last_error: Exception | None = None
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
            global _LAST_MODEL_USED
            _LAST_MODEL_USED = attempt_model
            break  # success — exit the retry loop
        except httpx.HTTPStatusError as e:
            last_error = e
            detail = e.response.text[:200]
            print(f"[llm] Model {attempt_model} failed (HTTP {e.response.status_code}): {detail}")
            if attempt_model == models_to_try[-1]:
                raise LLMError(f"LLM API error {e.response.status_code}: {detail}") from e
        except httpx.TimeoutException as e:
            last_error = e
            print(f"[llm] Model {attempt_model} timed out")
            if attempt_model == models_to_try[-1]:
                raise LLMError(f"LLM request timed out after 120s") from e
        except Exception as e:
            last_error = e
            print(f"[llm] Model {attempt_model} failed: {e}")
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
        _record_usage(data)

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


def _record_usage(data: dict) -> None:
    """Append a CSV row with token usage for cost tracking."""
    usage = data.get("usage", {})
    if not usage:
        return
    used_model = _LAST_MODEL_USED or LLM_MODEL
    row = (
        f"{time.strftime('%Y-%m-%dT%H:%M:%S')},"
        f"{usage.get('prompt_tokens', 0)},"
        f"{usage.get('completion_tokens', 0)},"
        f"{usage.get('total_tokens', 0)},"
        f"{used_model}\n"
    )
    cost_path = LOGS_DIR / "cost.csv"
    cost_path.parent.mkdir(parents=True, exist_ok=True)
    if not cost_path.exists():
        cost_path.write_text("timestamp,prompt_tokens,completion_tokens,total_tokens,model\n")
    with open(cost_path, "a") as f:
        f.write(row)
