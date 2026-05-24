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
    assert payload["supplier"].startswith("Demo Supplier ")
    assert len(payload["variants"]) >= 3
    assert len(payload["features"]) >= 3
    assert len(payload["faq"]) >= 2


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


def test_cors_allows_alternate_local_dev_port() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/auth/signup",
        headers={
            "Origin": "http://127.0.0.1:3010",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3010"


def test_trigger_requires_auth_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("USE_TEMPORAL", "false")
    monkeypatch.setenv("REQUIRE_AUTH_FOR_RUNS", "true")
    client = TestClient(app)

    response = client.post("/api/demo/trigger", json={"product_name": "Magnetic Phone Mount"})

    assert response.status_code == 401


def test_trigger_accepts_bearer_token_when_auth_enabled(monkeypatch) -> None:
    monkeypatch.setenv("USE_TEMPORAL", "false")
    monkeypatch.setenv("REQUIRE_AUTH_FOR_RUNS", "true")
    monkeypatch.setenv("AUTH_SECRET", "test-secret")
    client = TestClient(app)
    signup = client.post(
        "/api/auth/signup",
        json={"email": "owner@fastaisolution.com", "password": "correct horse battery", "full_name": "Store Owner"},
    ).json()

    response = client.post(
        "/api/demo/trigger",
        json={"product_name": "Magnetic Phone Mount"},
        headers={"Authorization": f"Bearer {signup['access_token']}"},
    )

    assert response.status_code == 200


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


def test_temporal_result_persistence_accepts_serialized_workflow_result(monkeypatch) -> None:
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
            return result.model_dump(mode="json")

    run_store.set_events(result.run.run_id, [])
    asyncio.run(_persist_temporal_result(Handle(), result.run.run_id))

    run = client.get(f"/api/runs/{run_id}").json()
    events = client.get(f"/api/runs/{run_id}/events").json()["events"]
    assert run["status"] == "fallback_completed"
    assert run["store_url"] == "https://portablepowerstation.fastaisolution.com"
    assert len(events) == 6


def test_streaming_launch_emits_running_then_completed_per_agent() -> None:
    from backend.workflows.activities import execute_streaming_launch

    run_id = UUID("11111111-1111-1111-1111-111111111111")
    workflow_input = WorkflowInput(
        run_id=run_id,
        product_name="Magnetic Phone Mount",
        temporal_workflow_id=f"launch-store-{run_id}",
    )
    captured: list[tuple[str, str]] = []

    def on_event(event):
        captured.append((event.agent_name, event.event_type))

    progressed: list[str] = []

    def on_progress(run):
        progressed.append(run.status)

    asyncio.run(
        execute_streaming_launch(
            workflow_input, delay_ms=0, on_event=on_event, on_progress=on_progress
        )
    )

    agents = ["research", "buyer", "legal_risk", "advertising", "score_launch", "store_creator"]
    for agent in agents:
        assert (agent, "running") in captured, f"missing running for {agent}"
        assert (agent, "completed") in captured, f"missing completed for {agent}"
    # Running fires before completed for each agent.
    for agent in agents:
        running_idx = captured.index((agent, "running"))
        completed_idx = captured.index((agent, "completed"))
        assert running_idx < completed_idx
    assert "running" in progressed
    assert progressed[-1] == "fallback_completed"


def test_build_store_url_uses_localhost_scheme_for_local_domain(monkeypatch) -> None:
    from backend.workflows.activities import build_store_url

    assert build_store_url("magneticphonemount", "localhost:3000") == "http://magneticphonemount.localhost:3000"
    assert build_store_url("magneticphonemount", "fastaisolution.com") == "https://magneticphonemount.fastaisolution.com"


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
