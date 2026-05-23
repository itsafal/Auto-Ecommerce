from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(StrEnum):
    started = "started"
    running = "running"
    completed = "completed"
    failed = "failed"
    fallback_completed = "fallback_completed"


class EventType(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    fallback_used = "fallback_used"


class AgentName(StrEnum):
    research = "research"
    buyer = "buyer"
    legal_risk = "legal_risk"
    advertising = "advertising"
    score_launch = "score_launch"
    store_creator = "store_creator"


class Decision(StrEnum):
    launch = "launch"
    pause = "pause"
    reject = "reject"


class LaunchRequest(BaseModel):
    product_name: str = Field(default="Magnetic Phone Mount", min_length=1)


class AuthSignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    full_name: str = Field(default="", max_length=120)


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class AuthUser(BaseModel):
    id: UUID
    email: str
    full_name: str = ""


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class LaunchTriggerResponse(BaseModel):
    run_id: UUID
    status: RunStatus
    temporal_workflow_id: str


class PriceRange(BaseModel):
    low: float
    high: float


class ResearchOutput(BaseModel):
    product_name: str
    category: str
    trend_score: float = Field(ge=0.0, le=1.0)
    search_volume: int = Field(ge=0)
    social_mentions: int = Field(ge=0)
    competitor_summary: str
    price_range: PriceRange
    confidence: float = Field(ge=0.0, le=1.0)


class BuyerOutput(BaseModel):
    supplier_name: str
    unit_cost: float = Field(ge=0.0)
    shipping_days: int = Field(ge=0)
    rating: float = Field(ge=0.0, le=5.0)
    estimated_margin: float = Field(ge=0.0, le=1.0)
    margin_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    risk_flags: list[str] = Field(default_factory=list)


class RiskOutput(BaseModel):
    cleared: bool
    risk_score: float = Field(ge=0.0, le=1.0)
    flags: list[str] = Field(default_factory=list)
    recommendation: str


class AdvertisingOutput(BaseModel):
    product_name: str
    tagline: str
    description: str
    cta_text: str
    hero_image_prompt: str
    hero_image_url: str


class StoreOutput(BaseModel):
    store_id: UUID
    slug: str
    store_url: str
    product_name: str
    description: str
    price: float = Field(ge=0.0)
    hero_image_url: str
    supplier: str
    cta_text: str


class LaunchScoreOutput(BaseModel):
    launch_score: float
    decision: Decision


class AgentEvent(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    agent_name: AgentName
    event_type: EventType
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentEventsResponse(BaseModel):
    run_id: UUID
    events: list[AgentEvent]


class LaunchRun(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    run_id: UUID
    temporal_workflow_id: str
    product_name: str
    slug: str
    status: RunStatus
    launch_score: float | None = None
    decision: Decision | None = None
    store_url: str | None = None
    error: str | None = None


class WorkflowInput(BaseModel):
    run_id: UUID
    product_name: str
    temporal_workflow_id: str


class WorkflowResult(BaseModel):
    run: LaunchRun
    events: list[AgentEvent]
