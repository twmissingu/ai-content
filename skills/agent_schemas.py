"""Structured output schemas for agents (inspired by CrewAI output_pydantic).

Enforces type-safe communication between pipeline stages.
Each agent stage produces a validated Pydantic model, not free-form text.
"""

from typing import Optional
from pydantic import BaseModel, Field


class TopicCandidate(BaseModel):
    """Scout agent output: a single topic candidate."""
    title: str = Field(description="选题标题")
    description: str = Field(default="", description="选题描述/方向")
    source: str = Field(default="unknown", description="来源平台")
    source_url: Optional[str] = Field(default=None, description="原文链接")
    final_score: float = Field(default=0.0, ge=0, le=100, description="综合评分")
    viral_score: float = Field(default=0.0, ge=0, le=100, description="爆款潜力")
    novelty_score: float = Field(default=0.0, ge=0, le=100, description="新颖度")
    feasibility_score: float = Field(default=0.0, ge=0, le=100, description="可行性")
    direction: Optional[str] = Field(default=None, description="写作方向建议")
    keywords: list[str] = Field(default_factory=list, description="关键词")


class ScoutOutput(BaseModel):
    """Scout agent output: collection of topic candidates."""
    session: str = Field(description="时段: morning/afternoon/evening")
    topics: list[TopicCandidate] = Field(description="选题列表")
    total_collected: int = Field(description="采集总数")
    total_selected: int = Field(description="筛选后数量")
    sources_used: list[str] = Field(default_factory=list, description="使用的数据源")


class ArticleDraft(BaseModel):
    """Writer agent output: article draft with metadata."""
    title: str = Field(description="文章标题")
    content: str = Field(description="文章正文")
    word_count: int = Field(default=0, description="字数")
    topic: str = Field(description="选题标题")
    platform: str = Field(default="wechat", description="目标平台")
    proofread_score: Optional[int] = Field(default=None, ge=0, le=100, description="审校评分")
    critique_scores: list[int] = Field(default_factory=list, description="批评修订各轮评分")
    title_candidates: list[dict] = Field(default_factory=list, description="标题候选列表")
    source_url: Optional[str] = Field(default=None, description="原文链接")
    images: list[str] = Field(default_factory=list, description="配图路径")


class QualityGateResult(BaseModel):
    """Quality gate evaluation result."""
    gate_name: str = Field(description="门禁名称")
    score: int = Field(ge=0, le=100, description="评分")
    threshold: int = Field(ge=0, le=100, description="阈值")
    passed: bool = Field(description="是否通过")
    issues: list[str] = Field(default_factory=list, description="发现的问题")
    suggestions: list[str] = Field(default_factory=list, description="改进建议")


class PublisherResult(BaseModel):
    """Publisher agent output: publish result per platform."""
    platform: str = Field(description="平台名称")
    status: str = Field(description="发布状态: success/failed/skipped")
    draft_url: Optional[str] = Field(default=None, description="草稿箱链接")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    article_id: Optional[str] = Field(default=None, description="文章ID")
    published_at: Optional[str] = Field(default=None, description="发布时间")


class PipelineRunResult(BaseModel):
    """Full pipeline run result."""
    session_id: Optional[int] = Field(default=None, description="数据库会话ID")
    topic: str = Field(description="选题")
    status: str = Field(description="管线状态: completed/failed/partial")
    article: Optional[ArticleDraft] = Field(default=None, description="文章结果")
    publishers: list[PublisherResult] = Field(default_factory=list, description="发布结果")
    total_tokens: int = Field(default=0, description="总Token消耗")
    total_duration_ms: int = Field(default=0, description="总耗时(ms)")
    error_message: Optional[str] = Field(default=None, description="错误信息")
