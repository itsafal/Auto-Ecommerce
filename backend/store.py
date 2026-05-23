from __future__ import annotations

import logging
from uuid import UUID

from backend.db.clickhouse import get_client, use_clickhouse
from backend.schemas import AgentEvent, LaunchRun, StoreOutput

logger = logging.getLogger(__name__)


class InMemoryRunStore:
    """In-memory fast path for the runs API.

    When USE_CLICKHOUSE=true we also dual-write to ClickHouse so the dashboard
    reads remain instant while ClickHouse holds the durable copy.
    """

    def __init__(self) -> None:
        self._runs: dict[UUID, LaunchRun] = {}
        self._events: dict[UUID, list[AgentEvent]] = {}
        self._stores: dict[str, StoreOutput] = {}

    def clear(self) -> None:
        self._runs.clear()
        self._events.clear()
        self._stores.clear()

    def upsert_store(self, store: StoreOutput) -> StoreOutput:
        self._stores[store.slug] = store
        return store

    def get_store(self, slug: str) -> StoreOutput | None:
        return self._stores.get(slug)

    def upsert_run(self, run: LaunchRun) -> LaunchRun:
        existed = run.run_id in self._runs
        self._runs[run.run_id] = run
        self._events.setdefault(run.run_id, [])
        self._mirror_run(run, is_new=not existed)
        return run

    def get_run(self, run_id: UUID) -> LaunchRun | None:
        return self._runs.get(run_id)

    def add_event(self, run_id: UUID, event: AgentEvent) -> AgentEvent:
        self._events.setdefault(run_id, []).append(event)
        self._events[run_id].sort(key=lambda item: item.timestamp)
        self._mirror_event(run_id, event)
        return event

    def set_events(self, run_id: UUID, events: list[AgentEvent]) -> None:
        self._events[run_id] = sorted(events, key=lambda item: item.timestamp)
        for event in self._events[run_id]:
            self._mirror_event(run_id, event)

    def get_events(self, run_id: UUID) -> list[AgentEvent]:
        return list(self._events.get(run_id, []))

    # ----- ClickHouse mirror (best-effort) -----

    def _mirror_run(self, run: LaunchRun, is_new: bool) -> None:
        if not use_clickhouse():
            return
        try:
            client = get_client()
            if is_new:
                client.write_run(
                    run_id=str(run.run_id),
                    product_name=run.product_name,
                    slug=run.slug,
                    status=run.status.value if hasattr(run.status, "value") else str(run.status),
                    temporal_workflow_id=run.temporal_workflow_id or "",
                )
            client.update_run(
                str(run.run_id),
                status=run.status.value if hasattr(run.status, "value") else str(run.status),
                launch_score=float(run.launch_score or 0.0),
                decision=(run.decision.value if hasattr(run.decision, "value") else str(run.decision or "")),
                store_url=run.store_url or "",
            )
        except Exception as exc:
            logger.warning("ClickHouse mirror_run failed for %s: %s", run.run_id, exc)

    def _mirror_event(self, run_id: UUID, event: AgentEvent) -> None:
        if not use_clickhouse():
            return
        try:
            client = get_client()
            client.write_event(
                run_id=str(run_id),
                agent_name=event.agent_name.value if hasattr(event.agent_name, "value") else str(event.agent_name),
                event_type=event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
                message=event.message,
                payload=event.payload,
            )
        except Exception as exc:
            logger.warning("ClickHouse mirror_event failed for %s: %s", run_id, exc)


run_store = InMemoryRunStore()
