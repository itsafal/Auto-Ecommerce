from __future__ import annotations

from datetime import timedelta

from backend.schemas import RunStatus, WorkflowInput, WorkflowResult
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

    def _inside_temporal_workflow() -> bool:
        try:
            workflow.info()
        except Exception:
            return False
        return True

    @workflow.defn
    class LaunchStoreWorkflow:
        @workflow.run
        async def run(self, workflow_input: WorkflowInput) -> WorkflowResult:
            if not _inside_temporal_workflow():
                return await activities.execute_fixture_launch(workflow_input)

            timeout = timedelta(seconds=30)
            research = await workflow.execute_activity(
                activities.research_activity,
                workflow_input.product_name,
                start_to_close_timeout=timeout,
            )
            buyer = await workflow.execute_activity(
                activities.buyer_activity,
                research,
                start_to_close_timeout=timeout,
            )
            risk = await workflow.execute_activity(
                activities.legal_risk_activity,
                args=[research, buyer],
                start_to_close_timeout=timeout,
            )
            advertising = await workflow.execute_activity(
                activities.advertising_activity,
                args=[research, buyer, risk],
                start_to_close_timeout=timeout,
            )
            score = await workflow.execute_activity(
                activities.score_launch_activity,
                args=[research, buyer, risk],
                start_to_close_timeout=timeout,
            )
            store = await workflow.execute_activity(
                activities.create_store_activity,
                args=[workflow_input, advertising, buyer],
                start_to_close_timeout=timeout,
            )
            return activities.build_launch_result(
                workflow_input=workflow_input,
                research=research,
                buyer=buyer,
                risk=risk,
                advertising=advertising,
                score=score,
                store=store,
                status=RunStatus.completed,
                timestamp=workflow.now(),
            )

else:

    class LaunchStoreWorkflow:
        async def run(self, workflow_input: WorkflowInput) -> WorkflowResult:
            return await activities.execute_fixture_launch(workflow_input)
