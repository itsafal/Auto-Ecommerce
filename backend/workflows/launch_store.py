from __future__ import annotations

from backend.schemas import WorkflowInput, WorkflowResult
from backend.workflows import activities


ACTIVITY_ORDER = [
    "research_activity",
    "buyer_activity",
    "legal_risk_activity",
    "advertising_activity",
    "score_launch_activity",
    "create_store_activity",
]


try:
    from temporalio import workflow
except ImportError:
    workflow = None


if workflow is not None:

    @workflow.defn
    class LaunchStoreWorkflow:
        @workflow.run
        async def run(self, workflow_input: WorkflowInput) -> WorkflowResult:
            return await activities.execute_fixture_launch(workflow_input)

else:

    class LaunchStoreWorkflow:
        async def run(self, workflow_input: WorkflowInput) -> WorkflowResult:
            return await activities.execute_fixture_launch(workflow_input)
