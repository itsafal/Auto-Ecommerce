"""In-memory store used when USE_CLICKHOUSE=false.

Mirrors the public surface of the ClickHouse client so the rest of the
backend can call the same methods regardless of which backend is active.
Thread-safe enough for a hackathon demo; not for production.
"""

from __future__ import annotations

import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class MemoryStore:
    """Process-local store. One instance per process is the intended use."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._runs: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        self._businesses: dict[str, dict[str, Any]] = {}
        self._trend_signals: list[dict[str, Any]] = []
        self._relationships: list[dict[str, Any]] = []
        self._agent_decisions: list[dict[str, Any]] = []
        self._users: dict[str, dict[str, Any]] = {}

    # ----- runs -----

    def write_run(
        self,
        run_id: str,
        product_name: str,
        slug: str,
        status: str = "started",
        temporal_workflow_id: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            record = {
                "run_id": run_id,
                "temporal_workflow_id": temporal_workflow_id,
                "product_name": product_name,
                "slug": slug,
                "status": status,
                "launch_score": 0.0,
                "decision": "",
                "store_url": "",
                "started_at": _utcnow(),
                "completed_at": None,
                "error": None,
            }
            self._runs[run_id] = record
            return deepcopy(record)

    def update_run(self, run_id: str, **fields: Any) -> dict[str, Any]:
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"run_id {run_id} not found")
            self._runs[run_id].update(fields)
            if fields.get("status") in {"completed", "failed", "fallback_completed"}:
                self._runs[run_id].setdefault("completed_at", _utcnow())
                if self._runs[run_id]["completed_at"] is None:
                    self._runs[run_id]["completed_at"] = _utcnow()
            return deepcopy(self._runs[run_id])

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            run = self._runs.get(run_id)
            return deepcopy(run) if run else None

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            runs = sorted(
                self._runs.values(),
                key=lambda r: r["started_at"],
                reverse=True,
            )
            return [deepcopy(r) for r in runs[:limit]]

    # ----- events -----

    def write_event(
        self,
        run_id: str,
        agent_name: str,
        event_type: str,
        message: str = "",
        payload: dict[str, Any] | None = None,
        business_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            event = {
                "run_id": run_id,
                "business_id": business_id,
                "agent_name": agent_name,
                "event_type": event_type,
                "message": message,
                "payload": payload or {},
                "timestamp": timestamp or _utcnow(),
            }
            self._events.append(event)
            return deepcopy(event)

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            events = [e for e in self._events if e["run_id"] == run_id]
            events.sort(key=lambda e: e["timestamp"])
            return [deepcopy(e) for e in events]

    # ----- businesses -----

    def write_business(self, business: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            record = deepcopy(business)
            record.setdefault("id", _new_id())
            record.setdefault("created_at", _utcnow())
            record.setdefault("launch_time", _utcnow())
            record.setdefault("bias_score", 0.0)
            self._businesses[record["id"]] = record
            return deepcopy(record)

    def update_business(self, business_id: str, **fields: Any) -> dict[str, Any]:
        with self._lock:
            if business_id not in self._businesses:
                raise KeyError(f"business_id {business_id} not found")
            self._businesses[business_id].update(fields)
            return deepcopy(self._businesses[business_id])

    def list_businesses(
        self,
        status: str | list[str] | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            businesses = list(self._businesses.values())
            if status is not None:
                allowed = {status} if isinstance(status, str) else set(status)
                businesses = [b for b in businesses if b.get("status") in allowed]
            return [deepcopy(b) for b in businesses]

    # ----- trend signals -----

    def write_trend_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            record = deepcopy(signal)
            record.setdefault("id", _new_id())
            record.setdefault("detected_at", _utcnow())
            self._trend_signals.append(record)
            return deepcopy(record)

    def list_trend_signals(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            signals = sorted(
                self._trend_signals,
                key=lambda s: s["detected_at"],
                reverse=True,
            )
            return [deepcopy(s) for s in signals[:limit]]

    # ----- relationships -----

    def write_relationship(
        self,
        from_business_id: str,
        to_business_id: str,
        relationship_type: str,
        weight: float,
        reason: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            record = {
                "from_business_id": from_business_id,
                "to_business_id": to_business_id,
                "relationship_type": relationship_type,
                "weight": float(weight),
                "reason": reason,
                "created_at": _utcnow(),
            }
            self._relationships.append(record)
            return deepcopy(record)

    def list_relationships(
        self,
        from_business_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            rels = self._relationships
            if from_business_id is not None:
                rels = [r for r in rels if r["from_business_id"] == from_business_id]
            return [deepcopy(r) for r in rels]

    # ----- agent decisions (long-form) -----

    def write_agent_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            record = deepcopy(decision)
            record.setdefault("id", _new_id())
            record.setdefault("timestamp", _utcnow())
            self._agent_decisions.append(record)
            return deepcopy(record)

    def list_agent_decisions(self, agent_name: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            decisions = self._agent_decisions
            if agent_name is not None:
                decisions = [d for d in decisions if d.get("agent_name") == agent_name]
            return [deepcopy(d) for d in decisions]

    # ----- users / auth -----

    def create_user(self, email: str, password_hash: str, full_name: str = "") -> dict[str, Any]:
        with self._lock:
            key = email.strip().lower()
            if key in self._users:
                raise ValueError("email already registered")
            record = {
                "id": _new_id(),
                "email": key,
                "password_hash": password_hash,
                "full_name": full_name.strip(),
                "created_at": _utcnow(),
                "last_login_at": None,
                "is_active": True,
            }
            self._users[key] = record
            return deepcopy(record)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._lock:
            user = self._users.get(email.strip().lower())
            return deepcopy(user) if user else None

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            for user in self._users.values():
                if user["id"] == user_id:
                    return deepcopy(user)
            return None

    def update_user_login(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            for user in self._users.values():
                if user["id"] == user_id:
                    user["last_login_at"] = _utcnow()
                    return deepcopy(user)
            return None

    # ----- maintenance -----

    def reset(self) -> None:
        with self._lock:
            self._runs.clear()
            self._events.clear()
            self._businesses.clear()
            self._trend_signals.clear()
            self._relationships.clear()
            self._agent_decisions.clear()
            self._users.clear()


_singleton: MemoryStore | None = None
_singleton_lock = threading.Lock()


def get_memory_store() -> MemoryStore:
    """Return the process-wide MemoryStore instance."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = MemoryStore()
    return _singleton
