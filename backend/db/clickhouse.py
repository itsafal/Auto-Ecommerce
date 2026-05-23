"""Unified data-access layer.

Routes to the in-memory store when USE_CLICKHOUSE=false (default) and to a
real ClickHouse Cloud connection when USE_CLICKHOUSE=true. Same method names
either way so callers never branch on backend.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from backend.db.memory_store import MemoryStore, get_memory_store

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def use_clickhouse() -> bool:
    return _truthy(os.environ.get("USE_CLICKHOUSE"))


class ClickHouseClient:
    """Thin wrapper around clickhouse-connect with the same surface as MemoryStore."""

    def __init__(self) -> None:
        import clickhouse_connect  # imported lazily so tests don't need the lib

        self._client = clickhouse_connect.get_client(
            host=os.environ["CLICKHOUSE_HOST"],
            port=int(os.environ.get("CLICKHOUSE_PORT", "8443")),
            username=os.environ.get("CLICKHOUSE_USER", "default"),
            password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
            database=os.environ.get("CLICKHOUSE_DATABASE", "default"),
            secure=_truthy(os.environ.get("CLICKHOUSE_SECURE", "true")),
        )

    def ensure_schema(self) -> None:
        sql = SCHEMA_PATH.read_text()
        for stmt in (s.strip() for s in sql.split(";")):
            if stmt:
                self._client.command(stmt)

    def write_run(self, run_id, product_name, slug, status="started", temporal_workflow_id=""):
        self._client.insert(
            "launch_runs",
            [[run_id, temporal_workflow_id, product_name, slug, status, 0.0, "", ""]],
            column_names=[
                "run_id", "temporal_workflow_id", "product_name", "slug",
                "status", "launch_score", "decision", "store_url",
            ],
        )
        return self.get_run(run_id)

    def update_run(self, run_id, **fields):
        # ClickHouse doesn't love updates; use ALTER ... UPDATE (mutation) for demo.
        sets = ", ".join(f"{k} = %({k})s" for k in fields)
        params = {**fields, "run_id": run_id}
        self._client.command(
            f"ALTER TABLE launch_runs UPDATE {sets} WHERE run_id = %(run_id)s",
            parameters=params,
        )
        return self.get_run(run_id)

    def get_run(self, run_id):
        rows = self._client.query(
            "SELECT * FROM launch_runs WHERE run_id = %(run_id)s LIMIT 1",
            parameters={"run_id": run_id},
        ).named_results()
        return next(iter(rows), None)

    def list_runs(self, limit=50):
        return list(
            self._client.query(
                "SELECT * FROM launch_runs ORDER BY started_at DESC LIMIT %(limit)s",
                parameters={"limit": limit},
            ).named_results()
        )

    def write_event(self, run_id, agent_name, event_type, message="", payload=None, business_id=None, timestamp=None):
        self._client.insert(
            "agent_events",
            [[run_id, business_id, agent_name, event_type, message, json.dumps(payload or {})]],
            column_names=["run_id", "business_id", "agent_name", "event_type", "message", "payload"],
        )
        return {
            "run_id": run_id, "agent_name": agent_name, "event_type": event_type,
            "message": message, "payload": payload or {}, "business_id": business_id,
        }

    def get_events(self, run_id):
        return list(
            self._client.query(
                "SELECT * FROM agent_events WHERE run_id = %(run_id)s ORDER BY timestamp",
                parameters={"run_id": run_id},
            ).named_results()
        )

    def write_business(self, business):
        # Caller passes a complete row; we just insert.
        self._client.insert("businesses", [business])
        return business

    def list_businesses(self, status=None):
        if status is None:
            rows = self._client.query("SELECT * FROM businesses").named_results()
        else:
            statuses = [status] if isinstance(status, str) else list(status)
            rows = self._client.query(
                "SELECT * FROM businesses WHERE status IN %(s)s",
                parameters={"s": tuple(statuses)},
            ).named_results()
        return list(rows)

    def write_trend_signal(self, signal):
        self._client.insert("trend_signals", [signal])
        return signal

    def list_trend_signals(self, limit=50):
        return list(
            self._client.query(
                "SELECT * FROM trend_signals ORDER BY detected_at DESC LIMIT %(limit)s",
                parameters={"limit": limit},
            ).named_results()
        )

    def write_relationship(self, from_business_id, to_business_id, relationship_type, weight, reason=""):
        self._client.insert(
            "business_relationships",
            [[from_business_id, to_business_id, relationship_type, float(weight), reason]],
            column_names=["from_business_id", "to_business_id", "relationship_type", "weight", "reason"],
        )

    def list_relationships(self, from_business_id=None):
        if from_business_id is None:
            rows = self._client.query("SELECT * FROM business_relationships").named_results()
        else:
            rows = self._client.query(
                "SELECT * FROM business_relationships WHERE from_business_id = %(id)s",
                parameters={"id": from_business_id},
            ).named_results()
        return list(rows)


_client: Any = None


def get_client() -> Any:
    """Return the active data store. MemoryStore by default."""
    global _client
    if _client is None:
        _client = ClickHouseClient() if use_clickhouse() else get_memory_store()
    return _client


def reset_client_for_tests() -> None:
    """Reset the cached client so tests can swap between backends."""
    global _client
    _client = None
