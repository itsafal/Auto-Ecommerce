from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.store import run_store


def setup_function() -> None:
    run_store.clear()


def test_demo_trigger_returns_run_id(monkeypatch) -> None:
    monkeypatch.setenv("USE_TEMPORAL", "false")
    client = TestClient(app)

    response = client.post("/api/demo/trigger", json={"product_name": "Magnetic Phone Mount"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"]
    assert payload["status"] == "started"
    assert payload["temporal_workflow_id"] == f"launch-store-{payload['run_id']}"


def test_launch_store_returns_run_id(monkeypatch) -> None:
    monkeypatch.setenv("USE_TEMPORAL", "false")
    client = TestClient(app)

    response = client.post("/api/launch-store", json={"product_name": "Magnetic Phone Mount"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"]
    assert payload["status"] == "started"
    assert payload["temporal_workflow_id"].startswith("launch-store-")


def test_get_run_returns_known_run(monkeypatch) -> None:
    monkeypatch.setenv("USE_TEMPORAL", "false")
    client = TestClient(app)
    trigger = client.post("/api/demo/trigger", json={"product_name": "Magnetic Phone Mount"}).json()

    response = client.get(f"/api/runs/{trigger['run_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == trigger["run_id"]
    assert payload["product_name"] == "Magnetic Phone Mount"
    assert payload["status"] == "fallback_completed"
    assert payload["launch_score"] == 0.624
    assert payload["decision"] == "launch"
    assert payload["store_url"] == "https://magneticphonemount.fastaisolution.com"


def test_get_events_returns_ordered_events(monkeypatch) -> None:
    monkeypatch.setenv("USE_TEMPORAL", "false")
    client = TestClient(app)
    trigger = client.post("/api/demo/trigger", json={"product_name": "Magnetic Phone Mount"}).json()

    response = client.get(f"/api/runs/{trigger['run_id']}/events")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == trigger["run_id"]
    assert [event["agent_name"] for event in payload["events"]] == [
        "research",
        "buyer",
        "legal_risk",
        "advertising",
        "score_launch",
        "store_creator",
    ]
    assert all(event["event_type"] == "completed" for event in payload["events"])
