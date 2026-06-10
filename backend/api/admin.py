"""Localhost-only admin endpoints for live LLM experimentation.

These set os.environ at runtime so the next call to get_settings() picks
up the new values. Useful for "swap to Haiku, retrigger, compare latency"
without restarting the backend. Gated by DEMO_MODE so they're inert in
production.
"""

from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.settings import get_settings

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _ensure_demo_mode() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(
            status_code=403,
            detail="Admin endpoints are only available when DEMO_MODE=true.",
        )


class LLMSnapshot(BaseModel):
    provider: str
    auto_chain_winner: str
    anthropic_model: str
    gemini_model: str
    portkey_model: str
    keys_set: dict[str, bool]


def _snapshot() -> LLMSnapshot:
    s = get_settings()
    # Mirror the auto-chain order in activities._llm_json
    if s.llm_provider == "auto":
        if s.portkey_api_key:
            winner = f"portkey:{s.portkey_model}"
        elif s.anthropic_api_key:
            winner = f"anthropic:{s.anthropic_model}"
        elif s.google_api_key:
            winner = f"gemini:{s.gemini_model}"
        else:
            winner = "fixture"
    elif s.llm_provider == "anthropic":
        winner = f"anthropic:{s.anthropic_model}"
    elif s.llm_provider == "portkey":
        winner = f"portkey:{s.portkey_model}"
    elif s.llm_provider in ("gemini", "google"):
        winner = f"gemini:{s.gemini_model}"
    else:
        winner = "unknown"

    return LLMSnapshot(
        provider=s.llm_provider,
        auto_chain_winner=winner,
        anthropic_model=s.anthropic_model,
        gemini_model=s.gemini_model,
        portkey_model=s.portkey_model,
        keys_set={
            "anthropic": bool(s.anthropic_api_key),
            "portkey": bool(s.portkey_api_key),
            "gemini": bool(s.google_api_key),
        },
    )


@router.get("/health")
async def get_health() -> dict[str, object]:
    """Report which backing services are live vs degraded to a fallback.

    Lets the operator see at a glance that e.g. the ClickHouse subscription
    lapsed and the app is running on the in-memory mirror.
    """
    from backend.db.clickhouse import clickhouse_fallback_reason, get_client, use_clickhouse
    from backend.integrations.nimble import nimble_disabled_reason

    s = get_settings()

    if use_clickhouse():
        # Materialize the connection (cached) so the reported status reflects
        # reality instead of "enabled" before the first query.
        get_client()
    ch_reason = clickhouse_fallback_reason()
    if not use_clickhouse():
        clickhouse = {"status": "disabled", "detail": "USE_CLICKHOUSE!=true"}
    elif ch_reason:
        clickhouse = {"status": "fallback_memory", "detail": ch_reason}
    else:
        clickhouse = {"status": "enabled", "detail": os.environ.get("CLICKHOUSE_HOST", "")}

    nimble_reason = nimble_disabled_reason()
    if not s.nimble_api_key:
        nimble = {"status": "not_configured", "detail": "NIMBLE_API_KEY unset"}
    elif nimble_reason:
        nimble = {"status": "disabled_circuit_open", "detail": nimble_reason}
    else:
        nimble = {"status": "configured", "detail": ""}

    return {
        "clickhouse": clickhouse,
        "nimble": nimble,
        "llm": _snapshot().model_dump(),
    }


class LLMUpdateRequest(BaseModel):
    provider: Literal["auto", "anthropic", "portkey", "gemini", "google"] | None = Field(
        default=None, description="Set LLM_PROVIDER for subsequent calls."
    )
    anthropic_model: str | None = Field(default=None, description="Override ANTHROPIC_MODEL.")
    gemini_model: str | None = Field(default=None, description="Override GEMINI_MODEL.")
    portkey_model: str | None = Field(default=None, description="Override PORTKEY_MODEL.")


@router.get("/llm", response_model=LLMSnapshot)
async def get_llm_config() -> LLMSnapshot:
    """Inspect the current LLM provider + model selection."""
    _ensure_demo_mode()
    return _snapshot()


@router.post("/llm", response_model=LLMSnapshot)
async def update_llm_config(request: LLMUpdateRequest) -> LLMSnapshot:
    """Swap provider/model at runtime without restarting the backend.

    Values are written to os.environ so the next get_settings() call (i.e.
    the next agent run) sees them. Restarting the backend reverts to .env.
    """
    _ensure_demo_mode()

    if request.provider is not None:
        os.environ["LLM_PROVIDER"] = request.provider
    if request.anthropic_model is not None:
        os.environ["ANTHROPIC_MODEL"] = request.anthropic_model
    if request.gemini_model is not None:
        os.environ["GEMINI_MODEL"] = request.gemini_model
    if request.portkey_model is not None:
        os.environ["PORTKEY_MODEL"] = request.portkey_model

    # Bust the trending-products cache so the next dashboard refresh hits
    # the newly-selected LLM instead of serving up to 60s of stale results.
    from backend.workflows.activities import invalidate_trending_cache

    invalidate_trending_cache()

    return _snapshot()
