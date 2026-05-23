from __future__ import annotations

import asyncio
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, HTTPException

from backend.schemas import (
    AgentEventsResponse,
    LaunchRequest,
    LaunchRun,
    LaunchTriggerResponse,
    RunStatus,
    StoreOutput,
    WorkflowInput,
    WorkflowResult,
)
from backend.settings import get_settings
from backend.store import run_store
from backend.workflows.activities import (
    execute_fixture_launch,
    execute_streaming_launch,
    slugify_product,
)

router = APIRouter(prefix="/api", tags=["runs"])


def _fixture_store(slug: str, run_id: UUID | None = None) -> StoreOutput:
    return StoreOutput(
        store_id=run_id or uuid5(NAMESPACE_URL, f"auto-ecommerce-store:{slug}"),
        slug=slug,
        store_url=f"https://{slug}.fastaisolution.com",
        product_name="MagSnap Pro",
        description="A compact magnetic phone mount built for fast one-handed docking and a cleaner dashboard.",
        price=29.99,
        hero_image_url="/demo/magnetic-phone-mount.png",
        supplier="Demo Supplier 4821",
        cta_text="Buy Now - Ships in 3 days",
    )


async def _start_launch(request: LaunchRequest) -> LaunchTriggerResponse:
    settings = get_settings()
    run_id = uuid4()
    temporal_workflow_id = f"launch-store-{run_id}"
    slug = slugify_product(request.product_name)

    run = LaunchRun(
        run_id=run_id,
        temporal_workflow_id=temporal_workflow_id,
        product_name=request.product_name,
        slug=slug,
        status=RunStatus.started,
    )
    run_store.upsert_run(run)

    workflow_input = WorkflowInput(
        run_id=run_id,
        product_name=request.product_name,
        temporal_workflow_id=temporal_workflow_id,
    )

    if settings.use_temporal:
        try:
            from temporalio.client import Client
            from temporalio.contrib.pydantic import pydantic_data_converter
        except ImportError as exc:
            raise HTTPException(status_code=500, detail="Temporal is enabled but temporalio is not installed.") from exc

        client = await Client.connect(
            settings.temporal_address,
            namespace=settings.temporal_namespace,
            data_converter=pydantic_data_converter,
        )
        handle = await client.start_workflow(
            "LaunchStoreWorkflow",
            workflow_input,
            id=temporal_workflow_id,
            task_queue=settings.temporal_task_queue,
        )
        asyncio.create_task(_persist_temporal_result(handle, run_id))
    elif settings.agent_stream_delay_ms > 0:
        asyncio.create_task(_run_streaming_fixture(workflow_input, settings.agent_stream_delay_ms))
    else:
        result = await execute_fixture_launch(workflow_input)
        run_store.upsert_run(result.run)
        run_store.set_events(run_id, result.events)

    return LaunchTriggerResponse(
        run_id=run_id,
        status=RunStatus.started,
        temporal_workflow_id=temporal_workflow_id,
    )


async def _run_streaming_fixture(workflow_input: WorkflowInput, delay_ms: int) -> None:
    def _on_event(event):
        run_store.add_event(workflow_input.run_id, event)

    def _on_progress(run):
        run_store.upsert_run(run)

    try:
        await execute_streaming_launch(
            workflow_input,
            delay_ms=delay_ms,
            on_event=_on_event,
            on_progress=_on_progress,
        )
    except Exception as exc:
        run = run_store.get_run(workflow_input.run_id)
        if run is not None:
            run.status = RunStatus.failed
            run.error = str(exc)
            run_store.upsert_run(run)


async def _persist_temporal_result(handle, run_id: UUID) -> None:
    try:
        result: WorkflowResult = await handle.result()
    except Exception as exc:
        run = run_store.get_run(run_id)
        if run is not None:
            run.status = RunStatus.failed
            run.error = str(exc)
            run_store.upsert_run(run)
        return

    if not isinstance(result, WorkflowResult):
        result = WorkflowResult.model_validate(result)

    run_store.upsert_run(result.run)
    run_store.set_events(result.run.run_id, result.events)


@router.post("/demo/trigger", response_model=LaunchTriggerResponse)
async def demo_trigger(request: LaunchRequest | None = None) -> LaunchTriggerResponse:
    return await _start_launch(request or LaunchRequest())


@router.post("/launch-store", response_model=LaunchTriggerResponse)
async def launch_store(request: LaunchRequest) -> LaunchTriggerResponse:
    return await _start_launch(request)


@router.get("/runs/{run_id}", response_model=LaunchRun)
async def get_run(run_id: UUID) -> LaunchRun:
    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/events", response_model=AgentEventsResponse)
async def get_run_events(run_id: UUID) -> AgentEventsResponse:
    if run_store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return AgentEventsResponse(run_id=run_id, events=run_store.get_events(run_id))


@router.get("/stores")
async def get_stores() -> dict[str, list[LaunchRun]]:
    runs = [run for run in run_store._runs.values() if run.store_url]
    return {"stores": runs}


@router.get("/stores/{slug}", response_model=StoreOutput)
async def get_store(slug: str) -> StoreOutput:
    for run in run_store._runs.values():
        if run.slug == slug and run.store_url:
            return _fixture_store(slug=run.slug, run_id=run.run_id)

    if slug == "magneticmount":
        return _fixture_store(slug=slug)

    raise HTTPException(status_code=404, detail="Store not found")


@router.get("/agents/status")
async def get_agents_status() -> dict[str, str]:
    return {"status": "ok", "mode": "fixture"}
