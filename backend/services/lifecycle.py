"""Autonomous portfolio lifecycle.

This module is scheduler-agnostic: callers can invoke `run_lifecycle_tick()`
from an admin button, cron job, or worker loop. It uses the existing portfolio
projection and deterministic metrics until real analytics land.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.schemas import BatchTriggerRequest
from backend.settings import get_settings
from backend.store import run_store


@dataclass(frozen=True)
class ShutdownCandidate:
    slug: str
    product_name: str
    reason: str
    revenue_24h: float
    conversion_rate: float
    days_live: float


def _portfolio() -> list[dict[str, Any]]:
    from backend.api.businesses import _business_from_run, _portfolio_runs

    return [_business_from_run(run) for run in _portfolio_runs()]


def evaluate_shutdown_candidates() -> list[ShutdownCandidate]:
    """Return live businesses that miss lifecycle performance targets."""
    settings = get_settings()
    candidates: list[ShutdownCandidate] = []
    for business in _portfolio():
        if business.get("business_status") != "live":
            continue
        days_live = float(business.get("days_live") or 0.0)
        if days_live < settings.lifecycle_grace_days:
            continue
        revenue_24h = float(business.get("revenue_24h") or 0.0)
        conversion_rate = float(business.get("conversion_rate") or 0.0)
        reasons: list[str] = []
        if revenue_24h < settings.lifecycle_min_revenue_24h:
            reasons.append(f"revenue_24h<{settings.lifecycle_min_revenue_24h:g}")
        if conversion_rate < settings.lifecycle_min_conversion_rate:
            reasons.append(f"conversion_rate<{settings.lifecycle_min_conversion_rate:g}")
        if reasons:
            candidates.append(
                ShutdownCandidate(
                    slug=str(business["slug"]),
                    product_name=str(business["product_name"]),
                    reason=";".join(reasons),
                    revenue_24h=revenue_24h,
                    conversion_rate=conversion_rate,
                    days_live=days_live,
                )
            )
    return candidates


def shutdown_underperformers() -> list[dict[str, Any]]:
    """Mark lifecycle candidates as shutdown and return updated projections."""
    from backend.api.businesses import _business_from_run, _portfolio_runs

    candidates = {candidate.slug: candidate for candidate in evaluate_shutdown_candidates()}
    updated: list[dict[str, Any]] = []
    for run in _portfolio_runs():
        candidate = candidates.get(run.slug)
        if candidate is None:
            continue
        run.business_status = "shutdown"
        run.shutdown_at = datetime.now(timezone.utc)
        run.shutdown_reason = f"lifecycle:{candidate.reason}"
        run_store.upsert_run(run)
        updated.append(_business_from_run(run))
    return updated


def live_count() -> int:
    return sum(1 for business in _portfolio() if business.get("business_status") == "live")


def next_backlog_product() -> str | None:
    """Return the highest-ranked backlog product, if one exists."""
    from backend.api.businesses import build_backlog

    items = build_backlog(limit=1)["items"]
    if not items:
        return None
    return str(items[0]["product_name"])


async def promote_top_of_backlog() -> dict[str, Any] | None:
    """If below live cap, trigger a one-slot seeded batch for the top backlog item."""
    settings = get_settings()
    if live_count() >= settings.max_concurrent_live:
        return None

    product = next_backlog_product()
    if not product:
        return None

    from backend.api.runs import start_batch

    response = await start_batch(
        BatchTriggerRequest(count=1, products=[product]),
        authorization=None,
        enforce_auth=False,
    )
    return response.model_dump(mode="json")


async def run_lifecycle_tick(promote: bool = True) -> dict[str, Any]:
    """Apply shutdown policy, then optionally promote backlog into open slots."""
    shutdowns = shutdown_underperformers()
    promotion = await promote_top_of_backlog() if promote else None
    return {
        "shutdown_candidates": [candidate.__dict__ for candidate in evaluate_shutdown_candidates()],
        "shutdowns": shutdowns,
        "promotion": promotion,
        "live_count": live_count(),
        "max_concurrent_live": get_settings().max_concurrent_live,
    }
