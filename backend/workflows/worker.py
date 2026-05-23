from __future__ import annotations

import asyncio

from backend.settings import get_settings
from backend.workflows.activities import (
    advertising_activity,
    buyer_activity,
    create_store_activity,
    legal_risk_activity,
    research_activity,
    score_launch_activity,
)
from backend.workflows.launch_store import LaunchStoreWorkflow


async def main() -> None:
    try:
        from temporalio.client import Client
        from temporalio.worker import Worker
    except ImportError as exc:
        raise RuntimeError("Install the temporal extra to run the Temporal worker.") from exc

    settings = get_settings()
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[LaunchStoreWorkflow],
        activities=[
            research_activity,
            buyer_activity,
            legal_risk_activity,
            advertising_activity,
            score_launch_activity,
            create_store_activity,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
