from __future__ import annotations

import asyncio
from uuid import UUID
from fastapi.testclient import TestClient

from backend.api.runs import _persist_temporal_result
from backend.main import app
from backend.schemas import WorkflowInput
from backend.store import run_store
from backend.workflows.activities import execute_fixture_launch


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


def test_get_store_returns_generated_storefront(monkeypatch) -> None:
    monkeypatch.setenv("USE_TEMPORAL", "false")
    client = TestClient(app)
    trigger = client.post("/api/demo/trigger", json={"product_name": "Magnetic Phone Mount"}).json()
    run = client.get(f"/api/runs/{trigger['run_id']}").json()

    response = client.get(f"/api/stores/{run['slug']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == "magneticphonemount"
    assert payload["store_url"] == "https://magneticphonemount.fastaisolution.com"
    assert payload["product_name"] == "MagSnap Pro"
    assert payload["supplier"] == "Demo Supplier 4821"


def test_get_store_keeps_documented_fixture_slug_available() -> None:
    client = TestClient(app)

    response = client.get("/api/stores/magneticmount")

    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == "magneticmount"
    assert payload["store_url"] == "https://magneticmount.fastaisolution.com"


def test_cors_allows_local_dashboard_preflight() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/demo/trigger",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_temporal_result_persistence_updates_run_and_events(monkeypatch) -> None:
    monkeypatch.setenv("USE_TEMPORAL", "false")
    client = TestClient(app)
    trigger = client.post("/api/demo/trigger", json={"product_name": "Portable Power Station"}).json()
    run_id = trigger["run_id"]
    workflow_input = WorkflowInput(
        run_id=run_id,
        product_name="Portable Power Station",
        temporal_workflow_id=trigger["temporal_workflow_id"],
    )
    result = asyncio.run(execute_fixture_launch(workflow_input))

    class Handle:
        async def result(self):
            return result

    run_store.set_events(result.run.run_id, [])
    asyncio.run(_persist_temporal_result(Handle(), result.run.run_id))

    run = client.get(f"/api/runs/{run_id}").json()
    events = client.get(f"/api/runs/{run_id}/events").json()["events"]
    assert run["status"] == "fallback_completed"
    assert run["store_url"] == "https://portablepowerstation.fastaisolution.com"
    assert len(events) == 6


def test_temporal_result_persistence_marks_failures(monkeypatch) -> None:
    monkeypatch.setenv("USE_TEMPORAL", "false")
    client = TestClient(app)
    trigger = client.post("/api/demo/trigger", json={"product_name": "Mini Portable Projector"}).json()
    run_id = trigger["run_id"]

    class Handle:
        async def result(self):
            raise RuntimeError("workflow failed")

    asyncio.run(_persist_temporal_result(Handle(), UUID(run_id)))

    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "failed"
    assert "workflow failed" in run["error"]
