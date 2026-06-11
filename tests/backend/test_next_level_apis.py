from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas import Decision, LaunchRun, RunStatus, StoreOutput
from backend.store import run_store


def setup_function() -> None:
    run_store.clear()


def _seed_live_business(product_name: str = "Magnetic Phone Mount") -> LaunchRun:
    run_id = uuid4()
    slug = product_name.lower().replace(" ", "")
    run = LaunchRun(
        run_id=run_id,
        temporal_workflow_id=f"launch-store-{run_id}",
        product_name=product_name,
        slug=slug,
        status=RunStatus.fallback_completed,
        launch_score=0.72,
        decision=Decision.launch,
        store_url=f"https://{slug}.fastaisolution.com",
        business_status="live",
        launched_at=datetime.now(timezone.utc) - timedelta(days=3),
        batch_slot=1,
        attempt_index=3,
        product_attempt=2,
        products_tried=2,
    )
    run_store.upsert_run(run)
    run_store.upsert_store(
        StoreOutput(
            store_id=uuid4(),
            slug=slug,
            store_url=run.store_url,
            product_name=product_name,
            tagline="A focused test product.",
            description="A generated storefront used by tests.",
            price=29.99,
            hero_image_url="/demo/test.png",
            supplier="Demo Supplier",
            cta_text="Buy Now",
            shipping_note="Ships in 3 days",
        )
    )
    return run


def test_plan04_retry_counters_round_trip_through_store() -> None:
    run = _seed_live_business()

    fetched = run_store.get_run(run.run_id)

    assert fetched is not None
    assert fetched.product_attempt == 2
    assert fetched.products_tried == 2


def test_agent_manifest_exposes_checkout_contract() -> None:
    run = _seed_live_business()
    client = TestClient(app)

    response = client.get(f"/api/stores/{run.slug}/agent-manifest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "ProductOffer"
    assert payload["store"]["checkout_url"].endswith("#checkout")
    assert payload["json_ld"]["@type"] == "Product"


def test_storefront_events_drive_portfolio_metrics() -> None:
    run = _seed_live_business()
    client = TestClient(app)
    session_id = "session-123456"

    for event_type in ["view_product", "click_cta", "begin_checkout"]:
        response = client.post(
            f"/api/stores/{run.slug}/events",
            json={
                "event_type": event_type,
                "session_id": session_id,
                "source": "google",
                "metadata": {"test": True},
            },
        )
        assert response.status_code == 200

    response = client.post(
        f"/api/stores/{run.slug}/events",
        json={
            "event_type": "purchase_attempt",
            "session_id": session_id,
            "source": "google",
            "value": 29.99,
        },
    )
    assert response.status_code == 200

    portfolio = client.get("/api/businesses").json()

    assert portfolio["data_source"] == "events"
    business = portfolio["businesses"][0]
    assert business["metric_source"] == "events"
    assert business["views_total"] == 1
    assert business["views_24h"] == 1
    assert business["revenue_total"] == 29.99
    assert business["conversion_rate"] == 1.0
    assert business["top_sources"][0]["source"] == "google"


def test_lifecycle_shutdown_underperformers_marks_business(monkeypatch) -> None:
    run = _seed_live_business()
    monkeypatch.setenv("LIFECYCLE_GRACE_DAYS", "0")
    monkeypatch.setenv("LIFECYCLE_MIN_REVENUE_24H", "999999")
    client = TestClient(app)

    response = client.post("/api/lifecycle/shutdown-underperformers")

    assert response.status_code == 200
    shutdowns = response.json()["shutdowns"]
    assert shutdowns[0]["slug"] == run.slug
    updated = run_store.get_run(run.run_id)
    assert updated is not None
    assert updated.business_status == "shutdown"
    assert updated.shutdown_reason.startswith("lifecycle:")


def test_experiment_plan_is_deterministic() -> None:
    run = _seed_live_business()
    client = TestClient(app)

    first = client.get(f"/api/experiments/plan/{run.slug}", params={"daily_budget": 60}).json()
    second = client.get(f"/api/experiments/plan/{run.slug}", params={"daily_budget": 60}).json()

    assert first == second
    assert first["daily_budget"] == 60.0
    assert len(first["creative_variants"]) == 6
    assert {variant["channel"] for variant in first["creative_variants"]} == {
        "tiktok",
        "meta",
        "google_search",
    }


def test_intelligence_projection_groups_portfolio() -> None:
    _seed_live_business("Magnetic Phone Mount")
    _seed_live_business("Wireless Phone Charger")
    client = TestClient(app)

    response = client.get("/api/intelligence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_source"] == "derived_from_launch_runs"
    assert len(payload["similarity_map"]["nodes"]) == 2
    assert payload["category_leaderboard"][0]["category"] == "electronics"
