from __future__ import annotations

import asyncio
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, Header, HTTPException

from backend.api.auth import get_authenticated_user
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
    build_store_url,
    discover_trending_products,
    execute_fixture_launch,
    execute_streaming_launch,
    slugify_product,
)

router = APIRouter(prefix="/api", tags=["runs"])


def _fixture_store(slug: str, run_id: UUID | None = None) -> StoreOutput:
    from backend.schemas import FAQItem, ProductVariant, Review

    base_price = 29.99
    return StoreOutput(
        store_id=run_id or uuid5(NAMESPACE_URL, f"auto-ecommerce-store:{slug}"),
        slug=slug,
        store_url=build_store_url(slug),
        product_name="MagSnap Pro",
        tagline="Mount your phone in one clean snap.",
        description="A compact magnetic phone mount built for fast one-handed docking and a cleaner dashboard.",
        price=base_price,
        hero_image_url="/demo/magnetic-phone-mount.png",
        supplier="Demo Supplier 4821",
        cta_text="Buy Now - Ships in 3 days",
        features=[
            "Strong N52 neodymium magnets - no slipping at highway speed",
            "Adhesive 3M VHB pad for dashboard, vent, or wall mounts",
            "Compatible with MagSafe and standard cases under 4mm",
            "Compact footprint, hides cleanly behind your phone",
            "30-day satisfaction guarantee, free returns",
        ],
        specs={
            "Material": "Aluminum + N52 neodymium",
            "Compatibility": "MagSafe + ring adapter",
            "Mount type": "Dashboard / vent / wall",
            "Weight": "38g",
            "Warranty": "1 year limited",
        },
        variants=[
            ProductVariant(name="MagSnap Standard", price=base_price, blurb="Single mount with 3M adhesive pad.", badge="Most popular", accent="#0f766e"),
            ProductVariant(name="MagSnap Pro", price=39.99, blurb="Premium aluminum body, stronger magnet array.", badge="Best build", accent="#1d4ed8"),
            ProductVariant(name="MagSnap Mini", price=22.99, blurb="Slimmer profile for compact dashboards.", badge="Travel", accent="#9333ea"),
            ProductVariant(name="MagSnap Duo Bundle", price=49.99, blurb="Two mounts + ring adapter pack.", badge="Save 18%", accent="#b45309"),
        ],
        faq=[
            FAQItem(question="Will it hold a phone in a heavy case?", answer="Yes, holds phones up to 250g including most rugged cases under 4mm thick."),
            FAQItem(question="How long does shipping take?", answer="Orders ship in 3 days with full tracking."),
            FAQItem(question="Does it damage the dashboard?", answer="3M VHB residue removes cleanly with isopropyl alcohol."),
            FAQItem(question="What if I don't have MagSafe?", answer="Bundle includes a magnetic ring adapter that sticks to any case."),
        ],
        reviews=[
            Review(name="Avery K.", rating=5.0, text="Holds rock solid on rough roads. Best mount I've owned."),
            Review(name="Jordan M.", rating=4.5, text="Sleek and tiny. Magnet is way stronger than expected."),
            Review(name="Priya S.", rating=5.0, text="Set up in 30 seconds, working perfectly two months in."),
        ],
        shipping_note="Ships in 3 days · Tracked delivery",
    )


async def _start_launch(request: LaunchRequest, authorization: str | None = None) -> LaunchTriggerResponse:
    settings = get_settings()
    if settings.require_auth_for_runs:
        get_authenticated_user(authorization)

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
        if result.store is not None:
            run_store.upsert_store(result.store)

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

    def _on_store(store):
        run_store.upsert_store(store)

    try:
        await execute_streaming_launch(
            workflow_input,
            delay_ms=delay_ms,
            on_event=_on_event,
            on_progress=_on_progress,
            on_store=_on_store,
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
async def demo_trigger(
    request: LaunchRequest | None = None,
    authorization: str | None = Header(default=None),
) -> LaunchTriggerResponse:
    return await _start_launch(request or LaunchRequest(), authorization=authorization)


@router.post("/launch-store", response_model=LaunchTriggerResponse)
async def launch_store(
    request: LaunchRequest,
    authorization: str | None = Header(default=None),
) -> LaunchTriggerResponse:
    return await _start_launch(request, authorization=authorization)


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
    return {"stores": run_store.list_runs_with_stores()}


@router.get("/stores/{slug}", response_model=StoreOutput)
async def get_store(slug: str) -> StoreOutput:
    real = run_store.get_store(slug)
    if real is not None:
        return real

    # In demo mode only, fall back to the magneticmount fixture so the dashboard
    # has something to render before an agent run has populated the store.
    if get_settings().demo_mode and slug == "magneticmount":
        return _fixture_store(slug=slug)

    raise HTTPException(status_code=404, detail="Store not found")


@router.get("/agents/status")
async def get_agents_status() -> dict[str, str]:
    return {"status": "ok", "mode": "fixture"}


@router.get("/agents/trending-products")
async def get_trending_products(limit: int = 8) -> dict:
    return await discover_trending_products(limit=max(1, min(limit, 20)))
