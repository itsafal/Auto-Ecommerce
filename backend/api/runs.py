from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, Header, HTTPException

from backend.api.auth import get_authenticated_user
from backend.schemas import (
    AgentEventsResponse,
    BatchSlotSummary,
    BatchStatusResponse,
    BatchTriggerRequest,
    BatchTriggerResponse,
    Decision,
    LaunchRequest,
    LaunchRun,
    LaunchTriggerResponse,
    RunStatus,
    StoreOutput,
    StorefrontEventRequest,
    StorefrontEventResponse,
    StoreTheme,
    WorkflowInput,
    WorkflowResult,
)
from backend.settings import get_settings
from backend.store import run_store
from backend.workflows.activities import (
    build_store_url,
    discover_new_trending_products,
    discover_trending_products,
    execute_fixture_launch,
    execute_streaming_launch,
    slugify_product,
)
from backend.services.agent_commerce import build_agent_manifest

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
    if result.store is not None:
        run_store.upsert_store(result.store)


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

    # Fallback: a batch run completed and produced a store URL but the rich
    # StoreOutput wasn't persisted (e.g. older runs from before
    # batch-slot stores were saved). Synthesize a minimal but valid storefront
    # from the LaunchRun + the fixture profile so the URL still renders
    # something useful instead of a 404.
    for run in run_store.list_runs_with_stores():
        if run.slug == slug:
            return _store_from_run(run)

    raise HTTPException(status_code=404, detail="Store not found")


@router.post("/stores/{slug}/events", response_model=StorefrontEventResponse)
async def record_storefront_event(
    slug: str,
    request: StorefrontEventRequest,
) -> StorefrontEventResponse:
    store = await get_store(slug)
    matching_run = next(
        (run for run in run_store.list_runs_with_stores() if run.slug == store.slug),
        None,
    )
    run_store.record_storefront_event(
        {
            "run_id": str(matching_run.run_id) if matching_run else None,
            "slug": store.slug,
            "event_type": request.event_type,
            "session_id": request.session_id,
            "source": request.source or "direct",
            "value": float(request.value or 0.0),
            "metadata": request.metadata,
            "timestamp": datetime.now(timezone.utc),
        }
    )
    return StorefrontEventResponse(slug=store.slug, event_type=request.event_type)


@router.get("/stores/{slug}/agent-manifest")
async def get_store_agent_manifest(slug: str) -> dict:
    store = await get_store(slug)
    return build_agent_manifest(store)


_PALETTE_POOL: list[dict[str, str]] = [
    # 10 curated, contrast-safe palettes. Each picked deterministically by
    # hash(slug) so the same product always gets the same colors.
    {"primary": "#0f766e", "accent": "#0d5d56", "bg": "#f5fbf9",
     "surface": "#ffffff", "text": "#0f172a", "text_muted": "#475569",
     "border": "#dbe9e5", "font_pair": "sans-modern"},                 # teal
    {"primary": "#c2410c", "accent": "#9a3412", "bg": "#fff7ed",
     "surface": "#ffffff", "text": "#1c1917", "text_muted": "#57534e",
     "border": "#f5e6d3", "font_pair": "serif-elegant"},               # warm terracotta
    {"primary": "#1d4ed8", "accent": "#1e40af", "bg": "#eef2ff",
     "surface": "#ffffff", "text": "#0f172a", "text_muted": "#475569",
     "border": "#dbe4ff", "font_pair": "sans-modern"},                 # cool blue
    {"primary": "#7c3aed", "accent": "#6d28d9", "bg": "#faf5ff",
     "surface": "#ffffff", "text": "#1e1b3a", "text_muted": "#4c3a72",
     "border": "#e9d5ff", "font_pair": "sans-modern"},                 # violet
    {"primary": "#be123c", "accent": "#9f1239", "bg": "#fff1f2",
     "surface": "#ffffff", "text": "#1f0a13", "text_muted": "#6b1f33",
     "border": "#fecdd3", "font_pair": "serif-elegant"},               # rose
    {"primary": "#0e7490", "accent": "#155e75", "bg": "#ecfeff",
     "surface": "#ffffff", "text": "#0a1f25", "text_muted": "#475569",
     "border": "#cffafe", "font_pair": "mono-tech"},                   # cyan-tech
    {"primary": "#15803d", "accent": "#166534", "bg": "#f0fdf4",
     "surface": "#ffffff", "text": "#14271a", "text_muted": "#3f6f4d",
     "border": "#bbf7d0", "font_pair": "serif-elegant"},               # forest
    {"primary": "#a16207", "accent": "#854d0e", "bg": "#fefce8",
     "surface": "#ffffff", "text": "#1c1303", "text_muted": "#6b5410",
     "border": "#fef08a", "font_pair": "serif-elegant"},               # mustard
    {"primary": "#db2777", "accent": "#be185d", "bg": "#fdf2f8",
     "surface": "#ffffff", "text": "#1f071a", "text_muted": "#6b2150",
     "border": "#fbcfe8", "font_pair": "sans-modern"},                 # magenta
    {"primary": "#475569", "accent": "#334155", "bg": "#f8fafc",
     "surface": "#ffffff", "text": "#0f172a", "text_muted": "#475569",
     "border": "#e2e8f0", "font_pair": "mono-tech"},                   # slate
]


def _theme_for_slug(slug: str) -> StoreTheme:
    """Deterministic palette pick keyed on the slug — same product always
    renders with the same colors across requests, even when the real
    StoreTheme wasn't persisted."""
    import hashlib

    digest = hashlib.sha256(slug.encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(_PALETTE_POOL)
    p = _PALETTE_POOL[idx]
    return StoreTheme(**p)


def _store_from_run(run: LaunchRun) -> StoreOutput:
    """Build a minimal StoreOutput for a LaunchRun whose pipeline finished but
    whose StoreOutput wasn't persisted to run_store._stores."""
    from backend.workflows.activities import _product_profile

    profile = _product_profile(run.product_name)
    slug = run.slug
    title = run.product_name
    return StoreOutput(
        store_id=uuid5(NAMESPACE_URL, f"auto-ecommerce-store:{slug}"),
        slug=slug,
        store_url=run.store_url or build_store_url(slug),
        product_name=profile.get("brand", title),
        tagline=profile.get("tagline", f"A focused way to buy {title}."),
        description=profile.get(
            "description",
            f"A clean, single-product storefront for {title}.",
        ),
        price=round(profile.get("low", 29.0) * 1.2, 2),
        hero_image_url=profile.get("hero", "/demo/magnetic-phone-mount.png"),
        supplier="Demo Supplier",
        cta_text="Buy Now",
        shipping_note=f"Ships in {profile.get('shipping_days', 7)} days",
        theme=_theme_for_slug(slug),
    )


@router.get("/agents/status")
async def get_agents_status() -> dict[str, str]:
    return {"status": "ok", "mode": "fixture"}


@router.get("/agents/trending-products")
async def get_trending_products(limit: int = 8) -> dict:
    return await discover_trending_products(limit=max(1, min(limit, 20)))


# ---------------------------------------------------------------------------
# Batch deployment — launch N stores in parallel; each slot retries against
# a different product if its launch_score falls below the threshold.
# ---------------------------------------------------------------------------


async def _build_candidate_queue(count: int, products: list[str] | None) -> asyncio.Queue[str]:
    """Build the FIFO of product names every slot draws from on retry.

    If the caller supplied `products` explicitly (curl / tests), use exactly
    that list — no dedup. Otherwise, ask `discover_new_trending_products` for
    a pool that excludes anything we've researched in the last DEDUP_WINDOW_DAYS
    days. This is what makes the autonomous batch deploy never re-try a product
    it has already attempted.

    Pool sizing (plan 04): count * candidate_pool_multiplier (default 4 → pool
    of 20 for a 5-slot batch). Slots can also lazily top up the queue via
    `_top_up_queue` when this initial pool runs dry mid-batch.
    """
    settings = get_settings()
    queue: asyncio.Queue[str] = asyncio.Queue()

    if products:
        for p in products:
            await queue.put(p)
        return queue

    pool_size = max(count * settings.candidate_pool_multiplier, count)
    excluded: set[str] = set()
    if settings.dedup_window_days > 0:
        try:
            excluded = run_store.recently_tried_products(settings.dedup_window_days)
        except Exception:
            excluded = set()

    fresh = await discover_new_trending_products(
        limit=min(pool_size, 25),
        exclude=excluded,
    )
    for name in fresh:
        await queue.put(name)

    return queue


async def _top_up_queue(
    queue: asyncio.Queue[str],
    *,
    lock: asyncio.Lock,
    already_tried: set[str],
) -> str | None:
    """Pull the next candidate, lazily topping up from Trend Scout if empty.

    The lock guards the "queue empty → top up" critical section so two slots
    arriving simultaneously don't both fire a discovery call and push
    duplicates. Returns None if the trending pool is truly exhausted.
    """
    try:
        return queue.get_nowait()
    except asyncio.QueueEmpty:
        pass

    async with lock:
        # Re-check under the lock — another slot may have already topped up.
        try:
            return queue.get_nowait()
        except asyncio.QueueEmpty:
            pass

        settings = get_settings()
        excluded: set[str] = set(already_tried)
        if settings.dedup_window_days > 0:
            try:
                excluded |= run_store.recently_tried_products(settings.dedup_window_days)
            except Exception:
                pass

        fresh = await discover_new_trending_products(limit=5, exclude=excluded)
        for name in fresh:
            await queue.put(name)

        try:
            return queue.get_nowait()
        except asyncio.QueueEmpty:
            return None


async def _run_batch_slot(
    *,
    batch_id: UUID,
    slot_index: int,
    initial_run_id: UUID,
    initial_product: str,
    candidate_queue: asyncio.Queue[str],
    threshold: float,
    require_auth: bool,
    queue_lock: asyncio.Lock,
) -> None:
    """Run one batch slot until it lands a winner (plan 04 retry policy).

    Outer loop iterates distinct products; inner loop is 2 attempts on the
    same product (LLM scoring is noisy → borderline products often clear on
    a second pass). After both attempts fail, the slot pulls a fresh product
    (lazily topping up the candidate queue from Trend Scout when needed) and
    repeats. Slot stops when either (a) a product lands a launch above
    threshold or (b) `max_products_per_slot` distinct products have all
    failed (safety cap so a degraded scorer can't loop forever).

    Fast-fail: if a product scores below `fast_fail_threshold` on attempt 1,
    skip attempt 2 — the second attempt is almost certainly hopeless and
    burns API budget for nothing.
    """
    settings = get_settings()
    attempts_per_product = max(1, settings.attempts_per_product)
    max_products = max(1, settings.max_products_per_slot)
    fast_fail = settings.fast_fail_threshold

    current_run_id = initial_run_id
    current_product = initial_product
    tried: set[str] = set()           # products this slot has already burned through
    products_tried = 0
    overall_attempt = 0               # monotonic across all pipeline runs in this slot

    while products_tried < max_products:
        products_tried += 1

        for product_attempt in range(1, attempts_per_product + 1):
            overall_attempt += 1
            run = LaunchRun(
                run_id=current_run_id,
                temporal_workflow_id=f"launch-store-{current_run_id}",
                product_name=current_product,
                slug=slugify_product(current_product),
                status=RunStatus.started,
                batch_id=batch_id,
                batch_slot=slot_index,
                attempt_index=overall_attempt,
                product_attempt=product_attempt,
                products_tried=products_tried,
            )
            run_store.upsert_run(run)

            workflow_input = WorkflowInput(
                run_id=current_run_id,
                product_name=current_product,
                temporal_workflow_id=f"launch-store-{current_run_id}",
            )

            try:
                delay_ms = settings.agent_stream_delay_ms
                if delay_ms > 0:
                    await execute_streaming_launch(
                        workflow_input,
                        delay_ms=delay_ms,
                        on_event=lambda ev, _rid=current_run_id: run_store.add_event(_rid, ev),
                        on_progress=lambda r, _bid=batch_id, _slot=slot_index, _att=overall_attempt, _pa=product_attempt, _pt=products_tried: run_store.upsert_run(
                            _enrich_run_with_batch(r, _bid, _slot, _att, _pa, _pt)
                        ),
                        on_store=lambda store: run_store.upsert_store(store),
                    )
                else:
                    result = await execute_fixture_launch(workflow_input)
                    enriched = _enrich_run_with_batch(
                        result.run, batch_id, slot_index, overall_attempt,
                        product_attempt, products_tried,
                    )
                    run_store.upsert_run(enriched)
                    run_store.set_events(current_run_id, result.events)
                    if result.store is not None:
                        run_store.upsert_store(result.store)
            except Exception as exc:
                current_run = run_store.get_run(current_run_id)
                if current_run is not None:
                    current_run.status = RunStatus.failed
                    current_run.error = str(exc)
                    current_run.attempt_index = overall_attempt
                    current_run.product_attempt = product_attempt
                    current_run.products_tried = products_tried
                    run_store.upsert_run(current_run)
                # Hard exception — abandon this product, try a fresh one.
                break

            final_run = run_store.get_run(current_run_id)
            if final_run is None:
                return

            # Workflow rebuilds the model without batch fields; restamp them.
            final_run.batch_id = batch_id
            final_run.batch_slot = slot_index
            final_run.attempt_index = overall_attempt
            final_run.product_attempt = product_attempt
            final_run.products_tried = products_tried
            run_store.upsert_run(final_run)

            score = final_run.launch_score
            passed = (
                score is not None
                and score >= threshold
                and final_run.decision == Decision.launch
            )

            if passed:
                from datetime import datetime, timezone

                final_run.business_status = "live"
                final_run.launched_at = datetime.now(timezone.utc)
                run_store.upsert_run(final_run)
                return

            # Mark this attempt as a reject.
            final_run.decision = Decision.reject
            run_store.upsert_run(final_run)

            # Fast-fail: hopeless score → don't burn attempt 2 on the same product.
            if score is not None and score < fast_fail:
                break

            # Still inside the per-product budget? Try again with same product.
            if product_attempt < attempts_per_product:
                current_run_id = uuid4()

        # Product fully exhausted (no pass after `attempts_per_product` tries
        # or fast-fail). Mark this product as tried and pull a fresh one.
        tried.add(current_product.strip().lower())

        if products_tried >= max_products:
            break

        next_product = await _top_up_queue(
            candidate_queue, lock=queue_lock, already_tried=tried,
        )
        if next_product is None:
            # Trending pool truly exhausted — give up gracefully.
            _mark_slot_exhausted(
                slot_index=slot_index, batch_id=batch_id,
                last_run_id=current_run_id, products_tried=products_tried,
                reason="trending_pool_exhausted",
            )
            return

        current_product = next_product
        current_run_id = uuid4()

    # Hit the safety cap without landing a winner.
    _mark_slot_exhausted(
        slot_index=slot_index, batch_id=batch_id,
        last_run_id=current_run_id, products_tried=products_tried,
        reason=f"exhausted_after_{products_tried}_products",
    )


def _mark_slot_exhausted(
    *, slot_index: int, batch_id: UUID, last_run_id: UUID,
    products_tried: int, reason: str,
) -> None:
    """Stamp a terminal 'safety cap hit' marker on the slot's last run."""
    run = run_store.get_run(last_run_id)
    if run is None:
        return
    run.status = RunStatus.failed
    run.error = reason
    run.products_tried = products_tried
    run_store.upsert_run(run)


def _enrich_run_with_batch(
    run: LaunchRun, batch_id: UUID, slot_index: int, attempt: int,
    product_attempt: int = 1, products_tried: int = 1,
) -> LaunchRun:
    """Stamp batch metadata onto a LaunchRun returned from the workflow."""
    run.batch_id = batch_id
    run.batch_slot = slot_index
    run.attempt_index = attempt
    run.product_attempt = product_attempt
    run.products_tried = products_tried
    return run


@router.post("/batch/launch", response_model=BatchTriggerResponse)
async def trigger_batch(
    request: BatchTriggerRequest | None = None,
    authorization: str | None = Header(default=None),
) -> BatchTriggerResponse:
    return await start_batch(request=request, authorization=authorization, enforce_auth=True)


async def start_batch(
    request: BatchTriggerRequest | None = None,
    authorization: str | None = None,
    *,
    enforce_auth: bool = True,
) -> BatchTriggerResponse:
    """Kick off a batch of N stores; returns immediately with the batch_id.

    Each slot runs its own pipeline in the background. Poll
    `GET /api/batch/{batch_id}` to see progress.
    """
    settings = get_settings()
    if enforce_auth and settings.require_auth_for_runs:
        get_authenticated_user(authorization)

    req = request or BatchTriggerRequest()
    count = req.count
    threshold = req.threshold if req.threshold is not None else settings.launch_score_threshold

    candidate_queue = await _build_candidate_queue(count, req.products)

    # Seed each slot with its first product (popping from the candidate queue);
    # if the queue runs out before we fill all slots, fall back to a placeholder.
    seeded_products: list[str] = []
    for _ in range(count):
        try:
            seeded_products.append(candidate_queue.get_nowait())
        except asyncio.QueueEmpty:
            seeded_products.append("Magnetic Phone Mount")

    batch_id = uuid4()
    # Shared lock so two slots hitting an empty queue don't both top up.
    queue_lock = asyncio.Lock()
    slots: list[BatchSlotSummary] = []
    for slot_index, product in enumerate(seeded_products):
        run_id = uuid4()
        slots.append(
            BatchSlotSummary(slot=slot_index, run_id=run_id, product_name=product)
        )
        asyncio.create_task(
            _run_batch_slot(
                batch_id=batch_id,
                slot_index=slot_index,
                initial_run_id=run_id,
                initial_product=product,
                candidate_queue=candidate_queue,
                threshold=threshold,
                require_auth=settings.require_auth_for_runs,
                queue_lock=queue_lock,
            )
        )

    return BatchTriggerResponse(
        batch_id=batch_id,
        target_count=count,
        threshold=threshold,
        slots=slots,
    )


@router.get("/batch/{batch_id}", response_model=BatchStatusResponse)
async def get_batch(batch_id: UUID) -> BatchStatusResponse:
    runs = run_store.list_runs_by_batch(batch_id)
    # Reuse the operator-configured threshold for the read-side view; if a
    # batch was launched with a non-default threshold the launch response is
    # the source of truth for that specific batch — we expose the current
    # default here so the dashboard has something to render.
    settings = get_settings()
    # Approximate target_count as the highest batch_slot index + 1 in the
    # results; safer than guessing if a slot is still spinning up.
    if runs:
        target = max((r.batch_slot or 0) for r in runs) + 1
    else:
        target = settings.batch_target_count
    return BatchStatusResponse(
        batch_id=batch_id,
        target_count=target,
        threshold=settings.launch_score_threshold,
        runs=runs,
    )
