from datetime import datetime, timedelta, timezone

from backend.analytics.bias import rank_near_misses


def _now() -> datetime:
    return datetime(2026, 5, 23, 12, 0, 0, tzinfo=timezone.utc)


def test_bias_ranks_failed_recent_high_trend_product_first():
    now = _now()
    businesses = [
        {
            "id": "stale-old",
            "product_name": "Old Failure",
            "category": "wellness",
            "status": "failed",
            "trend_score": 0.40,
            "launch_time": now - timedelta(days=200),
        },
        {
            "id": "hot-near-miss",
            "product_name": "Fresh Near Miss",
            "category": "phone_accessories",
            "status": "failed",
            "trend_score": 0.55,
            "launch_time": now - timedelta(days=3),
        },
        {
            "id": "active-ignored",
            "product_name": "Active Store",
            "category": "phone_accessories",
            "status": "active",
            "trend_score": 0.55,
            "launch_time": now - timedelta(days=3),
        },
    ]
    current = {
        "phone_accessories": 0.90,
        "wellness": 0.42,
    }

    ranked = rank_near_misses(businesses, current, now=now)

    assert [c.business_id for c in ranked] == ["hot-near-miss", "stale-old"]
    assert ranked[0].bias_score > ranked[1].bias_score


def test_bias_skips_active_businesses():
    now = _now()
    businesses = [
        {
            "id": "active",
            "product_name": "Live Store",
            "category": "kitchen_gadgets",
            "status": "active",
            "trend_score": 0.5,
            "launch_time": now - timedelta(days=5),
        },
    ]
    ranked = rank_near_misses(businesses, {"kitchen_gadgets": 0.95}, now=now)
    assert ranked == []


def test_paused_business_is_eligible():
    now = _now()
    businesses = [
        {
            "id": "paused",
            "product_name": "Paused Store",
            "category": "kitchen_gadgets",
            "status": "paused",
            "trend_score": 0.50,
            "launch_time": now - timedelta(days=10),
        },
    ]
    ranked = rank_near_misses(businesses, {"kitchen_gadgets": 0.85}, now=now)
    assert len(ranked) == 1
    assert ranked[0].business_id == "paused"


def test_no_trend_lift_still_gives_some_recency_score():
    now = _now()
    businesses = [
        {
            "id": "recent-no-lift",
            "product_name": "Recent Failure",
            "category": "wellness",
            "status": "failed",
            "trend_score": 0.50,
            "launch_time": now - timedelta(days=1),
        },
    ]
    ranked = rank_near_misses(businesses, {"wellness": 0.50}, now=now)
    assert len(ranked) == 1
    assert ranked[0].bias_score > 0
