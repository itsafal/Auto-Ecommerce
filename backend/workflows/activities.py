from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Awaitable, Callable
from uuid import uuid4

from backend.schemas import (
    AdvertisingOutput,
    AgentEvent,
    AgentName,
    BuyerOutput,
    Decision,
    EventType,
    LaunchRun,
    LaunchScoreOutput,
    ResearchOutput,
    RiskOutput,
    RunStatus,
    StoreOutput,
    WorkflowInput,
    WorkflowResult,
)

try:
    from temporalio import activity
except ImportError:

    class _ActivityCompat:
        @staticmethod
        def defn(fn):
            return fn

    activity = _ActivityCompat()


def slugify_product(product_name: str) -> str:
    return "".join(ch for ch in product_name.lower() if ch.isalnum())


def make_event(
    agent_name: AgentName,
    event_type: EventType,
    message: str,
    payload: dict | None = None,
    timestamp: datetime | None = None,
) -> AgentEvent:
    return AgentEvent(
        agent_name=agent_name,
        event_type=event_type,
        message=message,
        payload=payload or {},
        **({"timestamp": timestamp} if timestamp is not None else {}),
    )


@activity.defn
async def research_activity(product_name: str) -> ResearchOutput:
    return ResearchOutput(
        product_name=product_name,
        category="phone_accessories",
        trend_score=0.86,
        search_volume=42000,
        social_mentions=18000,
        competitor_summary="Several compact car-mount brands are trending with prices from $24 to $39.",
        price_range={"low": 24.0, "high": 39.0},
        confidence=0.82,
    )


@activity.defn
async def buyer_activity(research: ResearchOutput) -> BuyerOutput:
    return BuyerOutput(
        supplier_name="Demo Supplier 4821",
        unit_cost=8.4,
        shipping_days=6,
        rating=4.7,
        estimated_margin=0.61,
        margin_score=0.72,
        confidence_score=0.84,
        risk_flags=[],
    )


@activity.defn
async def legal_risk_activity(research: ResearchOutput, buyer: BuyerOutput) -> RiskOutput:
    return RiskOutput(
        cleared=True,
        risk_score=0.12,
        flags=[],
        recommendation="Safe for demo launch. Avoid claims about crash prevention or guaranteed safety.",
    )


@activity.defn
async def advertising_activity(research: ResearchOutput, buyer: BuyerOutput, risk: RiskOutput) -> AdvertisingOutput:
    return AdvertisingOutput(
        product_name="MagSnap Pro",
        tagline="Mount your phone in one clean snap.",
        description="A compact magnetic phone mount built for fast one-handed docking and a cleaner dashboard.",
        cta_text="Buy Now - Ships in 3 days",
        hero_image_prompt="Clean studio product photo of a compact magnetic phone mount on a car dashboard",
        hero_image_url="/demo/magnetic-phone-mount.png",
    )


@activity.defn
async def score_launch_activity(research: ResearchOutput, buyer: BuyerOutput, risk: RiskOutput) -> LaunchScoreOutput:
    launch_score = (
        research.trend_score * 0.30
        + buyer.margin_score * 0.25
        + buyer.confidence_score * 0.25
        - risk.risk_score * 0.20
    )
    decision = Decision.launch if launch_score >= 0.5 and risk.cleared else Decision.pause
    return LaunchScoreOutput(launch_score=round(launch_score, 3), decision=decision)


@activity.defn
async def create_store_activity(
    workflow_input: WorkflowInput,
    advertising: AdvertisingOutput,
    buyer: BuyerOutput,
) -> StoreOutput:
    slug = slugify_product(workflow_input.product_name)
    return StoreOutput(
        store_id=uuid4(),
        slug=slug,
        store_url=f"https://{slug}.fastaisolution.com",
        product_name=advertising.product_name,
        description=advertising.description,
        price=29.99,
        hero_image_url=advertising.hero_image_url,
        supplier=buyer.supplier_name,
        cta_text=advertising.cta_text,
    )


def build_launch_result(
    workflow_input: WorkflowInput,
    research: ResearchOutput,
    buyer: BuyerOutput,
    risk: RiskOutput,
    advertising: AdvertisingOutput,
    score: LaunchScoreOutput,
    store: StoreOutput,
    status: RunStatus,
    timestamp: datetime | None = None,
) -> WorkflowResult:
    events = [
        make_event(
            AgentName.research,
            EventType.completed,
            f"Research completed with trend score {research.trend_score}",
            {"trend_score": research.trend_score, "confidence": research.confidence},
            timestamp=timestamp,
        ),
        make_event(
            AgentName.buyer,
            EventType.completed,
            f"Buyer selected {buyer.supplier_name} with confidence {buyer.confidence_score}",
            {"supplier_confidence": buyer.confidence_score, "margin_score": buyer.margin_score},
            timestamp=timestamp,
        ),
        make_event(
            AgentName.legal_risk,
            EventType.completed,
            f"Legal risk completed with risk score {risk.risk_score}",
            {"cleared": risk.cleared, "risk_score": risk.risk_score},
            timestamp=timestamp,
        ),
        make_event(
            AgentName.advertising,
            EventType.completed,
            f"Advertising generated storefront copy for {advertising.product_name}",
            {"product_name": advertising.product_name, "tagline": advertising.tagline},
            timestamp=timestamp,
        ),
        make_event(
            AgentName.score_launch,
            EventType.completed,
            f"Launch score is {score.launch_score} with decision {score.decision}",
            {"launch_score": score.launch_score, "decision": score.decision},
            timestamp=timestamp,
        ),
        make_event(
            AgentName.store_creator,
            EventType.completed,
            f"Store created at {store.store_url}",
            {"store_url": store.store_url, "slug": store.slug},
            timestamp=timestamp,
        ),
    ]

    run = LaunchRun(
        run_id=workflow_input.run_id,
        temporal_workflow_id=workflow_input.temporal_workflow_id,
        product_name=workflow_input.product_name,
        slug=store.slug,
        status=status,
        launch_score=score.launch_score,
        decision=score.decision,
        store_url=store.store_url,
        error=None,
    )
    return WorkflowResult(run=run, events=events)


async def execute_fixture_launch(workflow_input: WorkflowInput) -> WorkflowResult:
    research = await research_activity(workflow_input.product_name)
    buyer = await buyer_activity(research)
    risk = await legal_risk_activity(research, buyer)
    advertising = await advertising_activity(research, buyer, risk)
    score = await score_launch_activity(research, buyer, risk)
    store = await create_store_activity(workflow_input, advertising, buyer)

    return build_launch_result(
        workflow_input=workflow_input,
        research=research,
        buyer=buyer,
        risk=risk,
        advertising=advertising,
        score=score,
        store=store,
        status=RunStatus.fallback_completed,
    )


EventSink = Callable[[AgentEvent], Awaitable[None] | None]
ProgressSink = Callable[[LaunchRun], Awaitable[None] | None]


async def _emit(sink: EventSink | None, event: AgentEvent) -> None:
    if sink is None:
        return
    result = sink(event)
    if asyncio.iscoroutine(result):
        await result


async def _progress(sink: ProgressSink | None, run: LaunchRun) -> None:
    if sink is None:
        return
    result = sink(run)
    if asyncio.iscoroutine(result):
        await result


_RUNNING_MESSAGES: dict[AgentName, str] = {
    AgentName.research: "Scanning trend signals and competitor pricing...",
    AgentName.buyer: "Negotiating with suppliers and checking margins...",
    AgentName.legal_risk: "Reviewing compliance and risk exposure...",
    AgentName.advertising: "Drafting storefront copy and hero creative...",
    AgentName.score_launch: "Calculating final launch score...",
    AgentName.store_creator: "Provisioning storefront and DNS...",
}


async def execute_streaming_launch(
    workflow_input: WorkflowInput,
    *,
    delay_ms: int,
    on_event: EventSink | None = None,
    on_progress: ProgressSink | None = None,
) -> WorkflowResult:
    """Run the fixture pipeline emitting `running` + `completed` events per agent.

    Used by the API in real-time mode so the dashboard can render progress as it
    happens. The terminal `WorkflowResult` is also returned for callers that want
    a single snapshot at the end (e.g. Temporal persistence).
    """

    delay = max(delay_ms, 0) / 1000.0
    base_run = LaunchRun(
        run_id=workflow_input.run_id,
        temporal_workflow_id=workflow_input.temporal_workflow_id,
        product_name=workflow_input.product_name,
        slug=slugify_product(workflow_input.product_name),
        status=RunStatus.running,
    )
    await _progress(on_progress, base_run)

    async def _step(agent: AgentName, runner):
        await _emit(
            on_event,
            make_event(agent, EventType.running, _RUNNING_MESSAGES[agent]),
        )
        if delay:
            await asyncio.sleep(delay)
        return await runner()

    research = await _step(AgentName.research, lambda: research_activity(workflow_input.product_name))
    await _emit(
        on_event,
        make_event(
            AgentName.research,
            EventType.completed,
            f"Research completed with trend score {research.trend_score}",
            {"trend_score": research.trend_score, "confidence": research.confidence},
        ),
    )

    buyer = await _step(AgentName.buyer, lambda: buyer_activity(research))
    await _emit(
        on_event,
        make_event(
            AgentName.buyer,
            EventType.completed,
            f"Buyer selected {buyer.supplier_name} with confidence {buyer.confidence_score}",
            {"supplier_confidence": buyer.confidence_score, "margin_score": buyer.margin_score},
        ),
    )

    risk = await _step(AgentName.legal_risk, lambda: legal_risk_activity(research, buyer))
    await _emit(
        on_event,
        make_event(
            AgentName.legal_risk,
            EventType.completed,
            f"Legal risk completed with risk score {risk.risk_score}",
            {"cleared": risk.cleared, "risk_score": risk.risk_score},
        ),
    )

    advertising = await _step(
        AgentName.advertising, lambda: advertising_activity(research, buyer, risk)
    )
    await _emit(
        on_event,
        make_event(
            AgentName.advertising,
            EventType.completed,
            f"Advertising generated storefront copy for {advertising.product_name}",
            {"product_name": advertising.product_name, "tagline": advertising.tagline},
        ),
    )

    score = await _step(AgentName.score_launch, lambda: score_launch_activity(research, buyer, risk))
    await _emit(
        on_event,
        make_event(
            AgentName.score_launch,
            EventType.completed,
            f"Launch score is {score.launch_score} with decision {score.decision}",
            {"launch_score": score.launch_score, "decision": score.decision},
        ),
    )

    store = await _step(AgentName.store_creator, lambda: create_store_activity(workflow_input, advertising, buyer))
    await _emit(
        on_event,
        make_event(
            AgentName.store_creator,
            EventType.completed,
            f"Store created at {store.store_url}",
            {"store_url": store.store_url, "slug": store.slug},
        ),
    )

    result = build_launch_result(
        workflow_input=workflow_input,
        research=research,
        buyer=buyer,
        risk=risk,
        advertising=advertising,
        score=score,
        store=store,
        status=RunStatus.fallback_completed,
    )
    await _progress(on_progress, result.run)
    return result
