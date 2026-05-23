from __future__ import annotations

import asyncio
from uuid import uuid4

from backend.schemas import WorkflowInput
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
