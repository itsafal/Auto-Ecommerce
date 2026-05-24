"""Unified data-access layer.

Routes to the in-memory store when USE_CLICKHOUSE=false (default) and to a
real ClickHouse Cloud connection when USE_CLICKHOUSE=true. Same method names
either way so callers never branch on backend.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from backend.db.memory_store import MemoryStore, get_memory_store

BUSINESS_COLUMNS = [
    "id", "product_name", "slug", "category", "launch_time", "store_url",
    "status", "margin_estimate", "supplier_id", "supplier_name",
    "trend_score", "launch_score", "bias_score", "created_at",
]

TREND_SIGNAL_COLUMNS = [
    "id", "product_name", "category", "source",
    "trend_score", "search_volume", "social_mentions", "detected_at",
]


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.now(timezone.utc)


def _row_from_dict(record: dict, columns: list[str], defaults: dict | None = None) -> list:
    """Project a dict into an ordered row, filling missing keys from defaults."""
    defaults = defaults or {}
    row = []
    for col in columns:
        if col in record and record[col] is not None:
            row.append(record[col])
        elif col in defaults:
            row.append(defaults[col])
        else:
            row.append(None)
    return row

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

    def write_run(
        self,
        run_id,
        product_name,
        slug,
        status="started",
        temporal_workflow_id="",
        batch_id=None,
        batch_slot=None,
        attempt_index=1,
    ):
        rid = uuid.UUID(run_id) if isinstance(run_id, str) else run_id
        bid = uuid.UUID(batch_id) if isinstance(batch_id, str) and batch_id else batch_id
        self._client.insert(
            "launch_runs",
            [[rid, temporal_workflow_id, product_name, slug, status, 0.0, "", "",
              bid, batch_slot, int(attempt_index or 1)]],
            column_names=[
                "run_id", "temporal_workflow_id", "product_name", "slug",
                "status", "launch_score", "decision", "store_url",
                "batch_id", "batch_slot", "attempt_index",
            ],
        )
        return self.get_run(run_id)

    def list_runs_by_batch(self, batch_id):
        bid = str(batch_id)
        return list(
            self._client.query(
                "SELECT * FROM launch_runs WHERE batch_id = %(bid)s ORDER BY batch_slot, attempt_index",
                parameters={"bid": bid},
            ).named_results()
        )

    def recently_tried_products(self, window_days: int) -> set[str]:
        """Distinct lowercased product_name values researched in the last
        `window_days` days. Used to seed the batch dedup exclusion set."""
        rows = self._client.query(
            "SELECT DISTINCT lower(trim(product_name)) AS name FROM trend_signals "
            "WHERE detected_at > now() - INTERVAL %(d)s DAY",
            parameters={"d": int(window_days)},
        ).result_set
        return {str(r[0]) for r in rows if r and r[0]}

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
        rid = uuid.UUID(run_id) if isinstance(run_id, str) else run_id
        bid = uuid.UUID(business_id) if isinstance(business_id, str) else business_id
        self._client.insert(
            "agent_events",
            [[rid, bid, agent_name, event_type, message, json.dumps(payload or {})]],
            column_names=["run_id", "business_id", "agent_name", "event_type", "message", "payload"],
        )
        return {
            "run_id": run_id, "agent_name": agent_name, "event_type": event_type,
            "message": message, "payload": payload or {}, "business_id": business_id,
        }

    def write_agent_decision(
        self,
        run_id,
        agent_name: str,
        action: str,
        input_summary: str = "",
        output_summary: str = "",
        latency_ms: int = 0,
        model_used: str = "",
        business_id=None,
    ):
        rid = uuid.UUID(run_id) if isinstance(run_id, str) else run_id
        # business_id is non-null in the schema; use the zero-UUID when unknown.
        bid_raw = business_id if business_id is not None else "00000000-0000-0000-0000-000000000000"
        bid = uuid.UUID(bid_raw) if isinstance(bid_raw, str) else bid_raw
        self._client.insert(
            "agent_decisions",
            [[uuid.uuid4(), bid, rid, agent_name, action,
              input_summary[:500], output_summary[:500], int(latency_ms), model_used]],
            column_names=[
                "id", "business_id", "run_id", "agent_name", "action",
                "input_summary", "output_summary", "latency_ms", "model_used",
            ],
        )

    def get_events(self, run_id):
        return list(
            self._client.query(
                "SELECT * FROM agent_events WHERE run_id = %(run_id)s ORDER BY timestamp",
                parameters={"run_id": run_id},
            ).named_results()
        )

    def write_business(self, business):
        record = dict(business)
        record.setdefault("id", str(uuid.uuid4()))
        record.setdefault("slug", "")
        record.setdefault("category", "")
        record.setdefault("store_url", "")
        record.setdefault("supplier_id", "")
        record.setdefault("supplier_name", "")
        record.setdefault("status", "active")
        record.setdefault("margin_estimate", 0.0)
        record.setdefault("trend_score", 0.0)
        record.setdefault("launch_score", 0.0)
        record.setdefault("bias_score", 0.0)
        record["launch_time"] = _parse_dt(record.get("launch_time"))
        record["created_at"] = _parse_dt(record.get("created_at"))
        # Cast UUID strings to uuid.UUID objects ClickHouse expects.
        if isinstance(record["id"], str):
            record["id"] = uuid.UUID(record["id"])
        row = _row_from_dict(record, BUSINESS_COLUMNS)
        self._client.insert("businesses", [row], column_names=BUSINESS_COLUMNS)
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
        record = dict(signal)
        record.setdefault("id", str(uuid.uuid4()))
        record.setdefault("category", "")
        record.setdefault("source", "")
        record.setdefault("trend_score", 0.0)
        record.setdefault("search_volume", 0)
        record.setdefault("social_mentions", 0)
        record["detected_at"] = _parse_dt(record.get("detected_at"))
        if isinstance(record["id"], str):
            record["id"] = uuid.UUID(record["id"])
        row = _row_from_dict(record, TREND_SIGNAL_COLUMNS)
        self._client.insert("trend_signals", [row], column_names=TREND_SIGNAL_COLUMNS)
        return signal

    def list_trend_signals(self, limit=50):
        return list(
            self._client.query(
                "SELECT * FROM trend_signals ORDER BY detected_at DESC LIMIT %(limit)s",
                parameters={"limit": limit},
            ).named_results()
        )

    def write_relationship(self, from_business_id, to_business_id, relationship_type, weight, reason=""):
        f = uuid.UUID(from_business_id) if isinstance(from_business_id, str) else from_business_id
        t = uuid.UUID(to_business_id) if isinstance(to_business_id, str) else to_business_id
        self._client.insert(
            "business_relationships",
            [[f, t, relationship_type, float(weight), reason]],
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

    def create_user(self, email, password_hash, full_name=""):
        existing = self.get_user_by_email(email)
        if existing is not None:
            raise ValueError("email already registered")
        user_id = str(uuid.uuid4())
        normalized_email = email.strip().lower()
        self._client.insert(
            "users",
            [[user_id, normalized_email, password_hash, full_name.strip(), 1]],
            column_names=["id", "email", "password_hash", "full_name", "is_active"],
        )
        return self.get_user_by_email(normalized_email)

    def get_user_by_email(self, email):
        rows = self._client.query(
            """
            SELECT id, email, password_hash, full_name, created_at, last_login_at, is_active
            FROM users
            WHERE email = %(email)s AND is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            parameters={"email": email.strip().lower()},
        ).named_results()
        return next(iter(rows), None)

    def get_user_by_id(self, user_id):
        rows = self._client.query(
            """
            SELECT id, email, password_hash, full_name, created_at, last_login_at, is_active
            FROM users
            WHERE id = %(id)s AND is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            parameters={"id": user_id},
        ).named_results()
        return next(iter(rows), None)

    def update_user_login(self, user_id):
        self._client.command(
            "ALTER TABLE users UPDATE last_login_at = now() WHERE id = %(id)s",
            parameters={"id": user_id},
        )
        return self.get_user_by_id(user_id)


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
