"""Paid-traffic experiment planning.

The first useful version of an ad engine is a deterministic test plan: channels,
creative angles, budget allocation, and rules for kill/scale decisions. External
ad-platform execution can plug into this contract later.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from backend.schemas import LaunchRun


CHANNELS = ("tiktok", "meta", "google_search")
ANGLES = (
    "problem_solution",
    "comparison",
    "social_proof",
    "urgency",
    "demo",
)


@dataclass(frozen=True)
class CreativeVariant:
    id: str
    channel: str
    angle: str
    headline: str
    primary_text: str
    budget: float


def _seed(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _money(value: float) -> float:
    return round(value, 2)


def _angle_headline(product_name: str, angle: str) -> str:
    if angle == "problem_solution":
        return f"Fix the daily hassle with {product_name}"
    if angle == "comparison":
        return f"{product_name} vs the usual alternative"
    if angle == "social_proof":
        return f"Why shoppers are testing {product_name}"
    if angle == "urgency":
        return f"Try {product_name} while demand is climbing"
    return f"See {product_name} in action"


def build_experiment_plan(run: LaunchRun, daily_budget: float = 50.0) -> dict[str, Any]:
    """Build a deterministic micro-budget experiment for a launched business."""
    slug = run.slug or str(run.run_id)
    budget = max(5.0, float(daily_budget))
    channel_weights = {
        "tiktok": 0.40,
        "meta": 0.35,
        "google_search": 0.25,
    }
    if (run.launch_score or 0.0) >= 0.75:
        channel_weights["google_search"] += 0.10
        channel_weights["tiktok"] -= 0.05
        channel_weights["meta"] -= 0.05

    variants: list[CreativeVariant] = []
    for channel in CHANNELS:
        channel_budget = budget * channel_weights[channel]
        selected = sorted(ANGLES, key=lambda angle: _seed(f"{slug}:{channel}:{angle}"))[:2]
        for index, angle in enumerate(selected, start=1):
            variant_id = f"{slug}-{channel}-{index}"
            variants.append(
                CreativeVariant(
                    id=variant_id,
                    channel=channel,
                    angle=angle,
                    headline=_angle_headline(run.product_name, angle),
                    primary_text=(
                        f"Test {run.product_name} with a clear offer, product proof, "
                        "and a direct checkout path."
                    ),
                    budget=_money(channel_budget / 2),
                )
            )

    return {
        "run_id": str(run.run_id),
        "slug": slug,
        "product_name": run.product_name,
        "daily_budget": _money(budget),
        "channels": [
            {
                "channel": channel,
                "budget": _money(budget * channel_weights[channel]),
                "objective": "purchase_intent",
            }
            for channel in CHANNELS
        ],
        "creative_variants": [variant.__dict__ for variant in variants],
        "success_metrics": {
            "min_ctr": 0.012,
            "max_cpc": 1.25,
            "min_add_to_cart_rate": 0.03,
            "min_checkout_intent_rate": 0.01,
        },
        "decision_rules": {
            "kill_after_spend": _money(budget * 1.5),
            "kill_if": "ctr<0.008 OR checkout_intent_rate<0.004",
            "scale_if": "ctr>=0.018 AND checkout_intent_rate>=0.015",
            "fork_if": "one creative beats median checkout_intent_rate by 2x",
        },
    }


def summarize_portfolio_experiments(runs: list[LaunchRun], daily_budget: float = 50.0) -> dict[str, Any]:
    plans = [build_experiment_plan(run, daily_budget=daily_budget) for run in runs]
    return {
        "plans": plans,
        "total_daily_budget": _money(sum(plan["daily_budget"] for plan in plans)),
        "experiment_count": len(plans),
    }
