from __future__ import annotations

import asyncio
from uuid import uuid4

from backend.schemas import WorkflowInput
from backend.workflows import activities
from backend.workflows.activities import execute_fixture_launch
from backend.workflows.launch_store import ACTIVITY_ORDER, LaunchStoreWorkflow


def test_workflow_calls_activities_in_expected_order() -> None:
    workflow = LaunchStoreWorkflow()
    workflow_input = WorkflowInput(
        run_id=uuid4(),
        product_name="Magnetic Phone Mount",
        temporal_workflow_id="launch-store-test",
    )

    result = asyncio.run(workflow.run(workflow_input))

    assert ACTIVITY_ORDER == [
        "research_activity",
        "buyer_activity",
        "legal_risk_activity",
        "advertising_activity",
        "score_launch_activity",
        "create_store_activity",
    ]
    assert [event.agent_name for event in result.events] == [
        "research",
        "buyer",
        "legal_risk",
        "advertising",
        "score_launch",
        "store_creator",
    ]


def test_sync_fallback_completes_run_without_temporal() -> None:
    workflow_input = WorkflowInput(
        run_id=uuid4(),
        product_name="Magnetic Phone Mount",
        temporal_workflow_id="launch-store-test",
    )

    result = asyncio.run(execute_fixture_launch(workflow_input))

    assert result.run.status == "fallback_completed"
    assert result.run.store_url == "https://magneticphonemount.fastaisolution.com"
    assert result.run.launch_score == 0.624
    assert len(result.events) == 6


def test_portkey_json_uses_gateway_chat_completion(monkeypatch) -> None:
    monkeypatch.setenv("USE_AGENT_FIXTURES", "false")
    monkeypatch.setenv("PORTKEY_API_KEY", "test-portkey-key")
    monkeypatch.setenv("PORTKEY_BASE_URL", "https://ai-gateway.example/v1")
    monkeypatch.setenv("PORTKEY_MODEL", "@vertexai/gemini-3.5-flash")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"products": ["Smart Ring"]}'}}]}

    class FakeAsyncClient:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, headers: dict, json: dict) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(activities.httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(activities._gemini_json("Return JSON"))

    assert result == {"products": ["Smart Ring"]}
    assert captured["url"] == "https://ai-gateway.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-portkey-key"
    assert captured["payload"]["model"] == "@vertexai/gemini-3.5-flash"
    assert captured["payload"]["max_tokens"] == 900
