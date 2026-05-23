from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import UUID

from backend.db.clickhouse import get_client, use_clickhouse
from backend.schemas import AgentEvent, AgentName, EventType, LaunchRun, RunStatus, StoreOutput

logger = logging.getLogger(__name__)


def _emit_startup_banner() -> None:
    """Print mode banner once at import so devs see the state in console."""
    if os.environ.get("_RUN_STORE_BANNER_EMITTED") == "1":
        return
    os.environ["_RUN_STORE_BANNER_EMITTED"] = "1"

    if use_clickhouse():
        host = os.environ.get("CLICKHOUSE_HOST", "<missing CLICKHOUSE_HOST>")
        db = os.environ.get("CLICKHOUSE_DATABASE", "default")
        logger.warning("[run_store] ClickHouse mirror ENABLED — host=%s db=%s", host, db)
    else:
        logger.warning(
            "[run_store] ClickHouse mirror DISABLED (USE_CLICKHOUSE!=true) — "
            "runs will only live in this process's memory."
        )


_emit_startup_banner()


class InMemoryRunStore:
    """In-memory fast path for the runs API.

    When USE_CLICKHOUSE=true we dual-write to ClickHouse so the dashboard
    reads remain instant while ClickHouse holds the durable shared copy.
    Reads fall back to ClickHouse on local miss so teammates see each
    other's runs.
    """

    def __init__(self) -> None:
        self._runs: dict[UUID, LaunchRun] = {}
        self._events: dict[UUID, list[AgentEvent]] = {}
        self._stores: dict[str, StoreOutput] = {}

    def clear(self) -> None:
        self._runs.clear()
        self._events.clear()
        self._stores.clear()

    # ----- stores -----

    def upsert_store(self, store: StoreOutput) -> StoreOutput:
        self._stores[store.slug] = store
        return store

    def get_store(self, slug: str) -> StoreOutput | None:
        return self._stores.get(slug)

    # ----- runs -----

    def upsert_run(self, run: LaunchRun) -> LaunchRun:
        existed = run.run_id in self._runs
        self._runs[run.run_id] = run
        self._events.setdefault(run.run_id, [])
        self._mirror_run(run, is_new=not existed)
        return run

    def get_run(self, run_id: UUID) -> LaunchRun | None:
        run = self._runs.get(run_id)
        if run is not None:
            return run
        if use_clickhouse():
            return self._fetch_run_from_clickhouse(run_id)
        return None

    def list_runs_with_stores(self) -> list[LaunchRun]:
        local = [run for run in self._runs.values() if run.store_url]
        if not use_clickhouse():
            return local

        try:
            client = get_client()
            rows = client.list_runs(limit=200)
        except Exception as exc:
            logger.error(
                "[run_store] list_runs_with_stores CH fetch failed: %s", exc, exc_info=True
            )
            return local

        merged: dict[UUID, LaunchRun] = {run.run_id: run for run in local}
        for row in rows:
            try:
                run = _row_to_launch_run(row)
            except Exception as exc:
                logger.warning(
                    "[run_store] could not parse CH run row %s: %s", row.get("run_id"), exc
                )
                continue
            if not run.store_url:
                continue
            merged.setdefault(run.run_id, run)
        return list(merged.values())

    # ----- events -----

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
        local = self._events.get(run_id)
        if local:
            return list(local)
        if not use_clickhouse():
            return []
        return self._fetch_events_from_clickhouse(run_id)

    def record_decision(
        self,
        run_id: UUID,
        agent_name: str,
        action: str,
        input_summary: str = "",
        output_summary: str = "",
        latency_ms: int = 0,
        model_used: str = "",
    ) -> None:
        """Append an entry to the analytics-grade agent_decisions table.

        Best-effort: failures are logged but never raised so they can't
        break the run path.
        """
        if not use_clickhouse():
            return
        try:
            client = get_client()
            if not hasattr(client, "write_agent_decision"):
                return
            client.write_agent_decision(
                run_id=str(run_id),
                agent_name=agent_name,
                action=action,
                input_summary=input_summary,
                output_summary=output_summary,
                latency_ms=latency_ms,
                model_used=model_used,
            )
        except Exception as exc:
            logger.error(
                "[run_store] write_agent_decision FAILED for run %s agent %s: %s",
                run_id,
                agent_name,
                exc,
                exc_info=True,
            )

    # ----- ClickHouse mirror (dual-write side) -----

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
                    status=_enum_value(run.status),
                    temporal_workflow_id=run.temporal_workflow_id or "",
                )
            client.update_run(
                str(run.run_id),
                status=_enum_value(run.status),
                launch_score=float(run.launch_score or 0.0),
                decision=_enum_value(run.decision) if run.decision else "",
                store_url=run.store_url or "",
            )
        except Exception as exc:
            # Loud — these were silently dropping data before.
            logger.error(
                "[run_store] ClickHouse mirror_run FAILED for %s (status=%s): %s",
                run.run_id,
                run.status,
                exc,
                exc_info=True,
            )

    def _mirror_event(self, run_id: UUID, event: AgentEvent) -> None:
        if not use_clickhouse():
            return
        try:
            client = get_client()
            client.write_event(
                run_id=str(run_id),
                agent_name=_enum_value(event.agent_name),
                event_type=_enum_value(event.event_type),
                message=event.message,
                payload=event.payload,
            )
        except Exception as exc:
            logger.error(
                "[run_store] ClickHouse mirror_event FAILED for run %s (%s/%s): %s",
                run_id,
                event.agent_name,
                event.event_type,
                exc,
                exc_info=True,
            )

    # ----- ClickHouse read fallback -----

    def _fetch_run_from_clickhouse(self, run_id: UUID) -> LaunchRun | None:
        try:
            client = get_client()
            row = client.get_run(str(run_id))
        except Exception as exc:
            logger.error("[run_store] CH get_run %s failed: %s", run_id, exc, exc_info=True)
            return None
        if not row:
            return None
        try:
            return _row_to_launch_run(row)
        except Exception as exc:
            logger.error(
                "[run_store] could not parse CH run row %s: %s", run_id, exc, exc_info=True
            )
            return None

    def _fetch_events_from_clickhouse(self, run_id: UUID) -> list[AgentEvent]:
        try:
            client = get_client()
            rows = client.get_events(str(run_id))
        except Exception as exc:
            logger.error(
                "[run_store] CH get_events %s failed: %s", run_id, exc, exc_info=True
            )
            return []
        events: list[AgentEvent] = []
        for row in rows:
            try:
                events.append(_row_to_event(row))
            except Exception as exc:
                logger.warning("[run_store] could not parse CH event row: %s", exc)
        events.sort(key=lambda e: e.timestamp)
        return events


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    return value.value if hasattr(value, "value") else str(value)


def _row_to_launch_run(row: dict[str, Any]) -> LaunchRun:
    decision_raw = row.get("decision") or None
    return LaunchRun(
        run_id=row["run_id"],
        temporal_workflow_id=row.get("temporal_workflow_id") or "",
        product_name=row.get("product_name") or "",
        slug=row.get("slug") or "",
        status=RunStatus(row.get("status") or "started"),
        launch_score=float(row["launch_score"]) if row.get("launch_score") is not None else None,
        decision=_safe_decision(decision_raw) if decision_raw else None,
        store_url=row.get("store_url") or None,
        error=row.get("error") or None,
    )


def _row_to_event(row: dict[str, Any]) -> AgentEvent:
    payload_raw = row.get("payload") or "{}"
    if isinstance(payload_raw, str):
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            payload = {}
    elif isinstance(payload_raw, dict):
        payload = payload_raw
    else:
        payload = {}
    return AgentEvent(
        agent_name=AgentName(row["agent_name"]),
        event_type=EventType(row["event_type"]),
        message=row.get("message") or "",
        timestamp=row["timestamp"],
        payload=payload,
    )


def _safe_decision(value: str):
    """Tolerate decision values we don't recognise — return None rather than raise."""
    from backend.schemas import Decision

    try:
        return Decision(value)
    except ValueError:
        return None


run_store = InMemoryRunStore()
