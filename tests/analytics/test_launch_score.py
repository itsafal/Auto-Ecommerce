from backend.analytics.launch_score import (
    LAUNCH_THRESHOLD,
    compute_launch_score,
    decide,
    score_and_decide,
)


def test_launch_score_matches_formula():
    score = compute_launch_score(
        trend_score=0.86,
        margin_score=0.72,
        supplier_confidence=0.84,
        compliance_risk=0.12,
    )
    expected = 0.86 * 0.30 + 0.72 * 0.25 + 0.84 * 0.25 - 0.12 * 0.20
    assert score == round(expected, 4)


def test_high_score_returns_launch_decision():
    result = score_and_decide(
        trend_score=0.92,
        margin_score=0.81,
        supplier_confidence=0.88,
        compliance_risk=0.05,
    )
    assert result.decision == "launch"
    assert result.launch_score >= LAUNCH_THRESHOLD


def test_low_score_returns_no_launch_decision():
    result = score_and_decide(
        trend_score=0.20,
        margin_score=0.15,
        supplier_confidence=0.30,
        compliance_risk=0.80,
    )
    assert result.decision == "no_launch"
    assert result.launch_score < LAUNCH_THRESHOLD


def test_inputs_are_clamped_to_unit_interval():
    # Values above 1 or below 0 should not blow up the formula
    score = compute_launch_score(
        trend_score=5.0,
        margin_score=-1.0,
        supplier_confidence=1.0,
        compliance_risk=10.0,
    )
    expected = 1.0 * 0.30 + 0.0 * 0.25 + 1.0 * 0.25 - 1.0 * 0.20
    assert score == round(expected, 4)


def test_decide_threshold_boundary():
    assert decide(LAUNCH_THRESHOLD) == "launch"
    assert decide(LAUNCH_THRESHOLD - 0.0001) == "no_launch"


def test_result_to_dict_is_json_safe():
    result = score_and_decide(0.5, 0.5, 0.5, 0.1)
    payload = result.to_dict()
    assert set(payload.keys()) == {"launch_score", "decision"}
    assert isinstance(payload["launch_score"], float)
    assert payload["decision"] in {"launch", "no_launch"}
