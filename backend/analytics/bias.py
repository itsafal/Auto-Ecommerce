"""Bias mechanism — surfaces failed/paused businesses worth retrying.

A business gets a higher bias score when:
  - it failed or is paused (only those are considered)
  - its product category now has a higher live trend score than at launch
  - it failed recently (recent failure = signal still fresh, not stale)

We rank by this score and return the top candidates for re-launch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

RECENCY_HALFLIFE_DAYS = 30.0
TREND_LIFT_WEIGHT = 0.70
RECENCY_WEIGHT = 0.30


@dataclass(frozen=True)
class BiasCandidate:
    business_id: str
    product_name: str
    category: str
    status: str
    original_trend_score: float
    current_trend_score: float
    bias_score: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "business_id": self.business_id,
            "product_name": self.product_name,
            "category": self.category,
            "status": self.status,
            "original_trend_score": round(self.original_trend_score, 4),
            "current_trend_score": round(self.current_trend_score, 4),
            "bias_score": round(self.bias_score, 4),
            "reason": self.reason,
        }


def _to_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        # Best-effort ISO parse
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _recency_factor(launched_at: datetime, now: datetime) -> float:
    """Exponential decay. 1.0 at launch, ~0.5 at one half-life, approaching 0."""
    delta: timedelta = now - launched_at
    days = max(delta.total_seconds() / 86400.0, 0.0)
    return 0.5 ** (days / RECENCY_HALFLIFE_DAYS)


def _trend_lift(original: float, current: float) -> float:
    """How much hotter is this category now vs. when we tried it? Clamped to [0, 1]."""
    lift = current - original
    if lift <= 0:
        return 0.0
    if lift >= 1:
        return 1.0
    return lift


def rank_near_misses(
    businesses: Iterable[dict[str, Any]],
    current_trend_scores: dict[str, float],
    now: datetime | None = None,
    limit: int = 10,
) -> list[BiasCandidate]:
    """Rank failed/paused businesses by retry potential.

    Args:
        businesses: rows from the businesses table.
        current_trend_scores: {category: latest_trend_score} from Nimble/fixtures.
        now: override for tests; defaults to UTC now.
        limit: max candidates to return.
    """
    now = now or datetime.now(timezone.utc)
    candidates: list[BiasCandidate] = []

    for business in businesses:
        status = business.get("status")
        if status not in {"failed", "paused"}:
            continue

        category = business.get("category", "")
        original_trend = float(business.get("trend_score", 0.0))
        current_trend = float(current_trend_scores.get(category, original_trend))

        lift = _trend_lift(original_trend, current_trend)
        launched_at = _to_utc(business.get("launch_time") or business.get("created_at"))
        recency = _recency_factor(launched_at, now)

        bias_score = lift * TREND_LIFT_WEIGHT + recency * RECENCY_WEIGHT

        if current_trend > original_trend:
            reason = (
                f"Category '{category}' trend climbed from "
                f"{original_trend:.2f} to {current_trend:.2f} since the {status} attempt."
            )
        else:
            reason = (
                f"{status.capitalize()} attempt is still recent; revisit if a new signal appears."
            )

        candidates.append(
            BiasCandidate(
                business_id=str(business.get("id", "")),
                product_name=business.get("product_name", ""),
                category=category,
                status=status,
                original_trend_score=original_trend,
                current_trend_score=current_trend,
                bias_score=bias_score,
                reason=reason,
            )
        )

    candidates.sort(key=lambda c: c.bias_score, reverse=True)
    return candidates[:limit]
