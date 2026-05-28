"""Pydantic models for API request/response schemas."""

from typing import Optional

from pydantic import BaseModel


class ApproveRequest(BaseModel):
    action: str  # approve | reject | rewrite
    target_id: str
    reason: Optional[str] = None
    platform_versions: Optional[list[str]] = None


class ConfirmRequest(BaseModel):
    target_id: str
    action: str = "confirm"


class ConfigUpdate(BaseModel):
    key: str
    value: str | int | float | bool | list | dict


class TokenLogRequest(BaseModel):
    agent: str = "unknown"
    model: str = "unknown"
    input_tokens: int = 0
    output_tokens: int = 0
    session_id: Optional[int] = None


class TriggerRequest(BaseModel):
    agent: str  # scout | writer
    session: Optional[str] = None  # morning | evening (for scout)
    topic_id: Optional[str] = None  # specific topic for writer


class RerunRequest(BaseModel):
    stage: int  # 1-7, which stage to re-run from


class PromptSaveRequest(BaseModel):
    name: str
    template: str
    variables: Optional[list[str]] = None
