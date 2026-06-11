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
        try:
            client = get_client()
            if hasattr(client, "reset"):
                client.reset()
        except Exception:
            pass

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

    def list_runs_by_batch(self, batch_id: UUID) -> list[LaunchRun]:
        """All runs (attempts) for a batch. Falls back to ClickHouse if local
        memory doesn't have them yet (e.g. queried from a different process)."""
        batch_id_str = str(batch_id)
        local = [
            run
            for run in self._runs.values()
            if run.batch_id and str(run.batch_id) == batch_id_str
        ]
        if local or not use_clickhouse():
            local.sort(key=lambda r: (r.batch_slot or 0, r.attempt_index))
            return local
        try:
            client = get_client()
            if not hasattr(client, "list_runs_by_batch"):
                return []
            rows = client.list_runs_by_batch(batch_id_str)
        except Exception as exc:
            logger.error(
                "[run_store] list_runs_by_batch CH fetch failed: %s", exc, exc_info=True
            )
            return []
        parsed: list[LaunchRun] = []
        for row in rows:
            try:
                parsed.append(_row_to_launch_run(row))
            except Exception as exc:
                logger.warning("[run_store] could not parse CH batch row: %s", exc)
        parsed.sort(key=lambda r: (r.batch_slot or 0, r.attempt_index))
        return parsed

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

    def recently_tried_products(self, window_days: int) -> set[str]:
        """Set of distinct lowercased product names researched in the last
        `window_days` days. Drives batch-slot dedup so the autonomous
        candidate queue never re-attempts a product the system has already
        scored recently.

        Uses ClickHouse when enabled (cross-process truth) and falls back to
        the in-memory mirror otherwise.
        """
        if use_clickhouse():
            try:
                client = get_client()
                if hasattr(client, "recently_tried_products"):
                    return client.recently_tried_products(window_days)
            except Exception as exc:
                logger.warning(
                    "[run_store] CH recently_tried_products failed; using local: %s", exc
                )
        # Walk the memory mirror (matches MemoryStore shape).
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=int(window_days))
        # _trend_signals lives inside the underlying MemoryStore when
        # use_clickhouse=false; access via get_client()'s method when present.
        client = get_client()
        if hasattr(client, "recently_tried_products"):
            return client.recently_tried_products(window_days)
        return set()

    def record_trend_signal(self, signal: dict[str, Any]) -> None:
        """Append a row to trend_signals (analytics time-series of researched products).

        Best-effort: failures are logged but never raised.
        """
        try:
            client = get_client()
            if not hasattr(client, "write_trend_signal"):
                return
            client.write_trend_signal(signal)
        except Exception as exc:
            logger.error(
                "[run_store] write_trend_signal FAILED for %r: %s",
                signal.get("product_name"),
                exc,
                exc_info=True,
            )

    def list_trend_signals(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent trend signals from the active backing store."""
        try:
            client = get_client()
            if hasattr(client, "list_trend_signals"):
                return client.list_trend_signals(limit=limit)
        except Exception as exc:
            logger.warning("[run_store] list_trend_signals failed: %s", exc)
        return []

    def record_storefront_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Append a storefront analytics event to the active backing store."""
        try:
            client = get_client()
            if not hasattr(client, "write_storefront_event"):
                return None
            return client.write_storefront_event(event)
        except Exception as exc:
            logger.error(
                "[run_store] write_storefront_event FAILED for %r/%r: %s",
                event.get("slug"),
                event.get("event_type"),
                exc,
                exc_info=True,
            )
            return None

    def list_storefront_events(
        self,
        slug: str | None = None,
        run_id: str | None = None,
        limit: int = 10000,
    ) -> list[dict[str, Any]]:
        """Return storefront analytics events from the active backing store."""
        try:
            client = get_client()
            if hasattr(client, "list_storefront_events"):
                return client.list_storefront_events(slug=slug, run_id=run_id, limit=limit)
        except Exception as exc:
            logger.warning("[run_store] list_storefront_events failed: %s", exc)
        return []

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
                    batch_id=str(run.batch_id) if run.batch_id else None,
                    batch_slot=run.batch_slot,
                    attempt_index=run.attempt_index,
                    product_attempt=run.product_attempt,
                    products_tried=run.products_tried,
                )
            update_fields: dict[str, Any] = {
                "status": _enum_value(run.status),
                "launch_score": float(run.launch_score or 0.0),
                "decision": _enum_value(run.decision) if run.decision else "",
                "store_url": run.store_url or "",
                "product_attempt": int(run.product_attempt or 1),
                "products_tried": int(run.products_tried or 1),
                "business_status": run.business_status or "",
                "shutdown_reason": run.shutdown_reason or "",
            }
            # ClickHouse's ALTER UPDATE doesn't love None for Nullable columns
            # via the SDK's parameter dict — only include timestamps when set.
            if run.launched_at is not None:
                update_fields["launched_at"] = run.launched_at
            if run.shutdown_at is not None:
                update_fields["shutdown_at"] = run.shutdown_at
            client.update_run(str(run.run_id), **update_fields)
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
        batch_id=row.get("batch_id") or None,
        batch_slot=row.get("batch_slot") if row.get("batch_slot") is not None else None,
        attempt_index=int(row.get("attempt_index") or 1),
        product_attempt=int(row.get("product_attempt") or 1),
        products_tried=int(row.get("products_tried") or 1),
        business_status=row.get("business_status") or "",
        launched_at=row.get("launched_at"),
        shutdown_at=row.get("shutdown_at"),
        shutdown_reason=row.get("shutdown_reason") or "",
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
