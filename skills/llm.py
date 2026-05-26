"""Shared LLM utility — all agents call LLM through this module.

Reads Hermes-provider config from env (XIAOMI_API_KEY, LLM_BASE_URL, LLM_MODEL).
Uses direct HTTP (OpenAI-compatible) so agents are not coupled to Hermes internals.
"""

import json
import time
from typing import Optional

import httpx

from config.settings import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_MAX_TOKENS,
    require_api_key,
)


class LLMError(Exception):
    """Raised when the LLM call fails."""


def _client() -> httpx.Client:
    key = LLM_API_KEY or require_api_key("XIAOMI_API_KEY")
    return httpx.Client(
        base_url=LLM_BASE_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        timeout=120,
    )


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

    body: dict = {
        "model": model or LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens or LLM_MAX_TOKENS,
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    try:
        resp = _client().post("/chat/completions", json=body)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:500]
        raise LLMError(f"LLM API error {e.response.status_code}: {detail}") from e
    except httpx.TimeoutException as e:
        raise LLMError(f"LLM request timed out after 120s") from e
    except Exception as e:
        raise LLMError(f"LLM request failed: {e}") from e

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
    from pathlib import Path

    usage = data.get("usage", {})
    if not usage:
        return
    row = (
        f"{time.strftime('%Y-%m-%dT%H:%M:%S')},"
        f"{usage.get('prompt_tokens', 0)},"
        f"{usage.get('completion_tokens', 0)},"
        f"{usage.get('total_tokens', 0)},"
        f"{LLM_MODEL}\n"
    )
    cost_path = Path("data/logs/cost.csv")
    cost_path.parent.mkdir(parents=True, exist_ok=True)
    if not cost_path.exists():
        cost_path.write_text("timestamp,prompt_tokens,completion_tokens,total_tokens,model\n")
    with open(cost_path, "a") as f:
        f.write(row)
