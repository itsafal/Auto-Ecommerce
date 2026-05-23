"""Launch scoring.

The launch score is a weighted blend of four signals from the agent run.
It is the single number the dashboard uses to decide whether to ship
a store. The formula is fixed; the threshold is tunable.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

TREND_WEIGHT = 0.30
MARGIN_WEIGHT = 0.25
SUPPLIER_WEIGHT = 0.25
COMPLIANCE_WEIGHT = 0.20

LAUNCH_THRESHOLD = 0.55


@dataclass(frozen=True)
class LaunchScoreInput:
    trend_score: float
    margin_score: float
    supplier_confidence: float
    compliance_risk: float


@dataclass(frozen=True)
class LaunchScoreResult:
    launch_score: float
    decision: str  # "launch" or "no_launch"

    def to_dict(self) -> dict:
        return {"launch_score": round(self.launch_score, 4), "decision": self.decision}


def _clamp(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return float(value)


def compute_launch_score(
    trend_score: float,
    margin_score: float,
    supplier_confidence: float,
    compliance_risk: float,
) -> float:
    """Apply the weighted formula. Inputs are clamped to [0, 1] for safety."""
    score = (
        _clamp(trend_score) * TREND_WEIGHT
        + _clamp(margin_score) * MARGIN_WEIGHT
        + _clamp(supplier_confidence) * SUPPLIER_WEIGHT
        - _clamp(compliance_risk) * COMPLIANCE_WEIGHT
    )
    return round(score, 4)


def decide(score: float, threshold: float = LAUNCH_THRESHOLD) -> str:
    return "launch" if score >= threshold else "no_launch"


def score_and_decide(
    trend_score: float,
    margin_score: float,
    supplier_confidence: float,
    compliance_risk: float,
    threshold: float = LAUNCH_THRESHOLD,
) -> LaunchScoreResult:
    score = compute_launch_score(
        trend_score, margin_score, supplier_confidence, compliance_risk
    )
    return LaunchScoreResult(launch_score=score, decision=decide(score, threshold))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute a launch score and decision.")
    parser.add_argument("--trend-score", type=float, required=True)
    parser.add_argument("--margin-score", type=float, required=True)
    parser.add_argument("--supplier-confidence", type=float, required=True)
    parser.add_argument("--compliance-risk", type=float, required=True)
    parser.add_argument("--threshold", type=float, default=LAUNCH_THRESHOLD)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = score_and_decide(
        trend_score=args.trend_score,
        margin_score=args.margin_score,
        supplier_confidence=args.supplier_confidence,
        compliance_risk=args.compliance_risk,
        threshold=args.threshold,
    )
    print(json.dumps(result.to_dict()))


if __name__ == "__main__":
    main()
