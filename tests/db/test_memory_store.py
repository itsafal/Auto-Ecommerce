import os
import time
from datetime import datetime, timedelta, timezone

import pytest

from backend.db.memory_store import MemoryStore
from backend.observability import datadog as dd_module


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


def test_memory_store_writes_and_reads_run(store):
    run = store.write_run(
        run_id="r-1",
        product_name="Magnetic Phone Mount",
        slug="magneticmount",
        temporal_workflow_id="wf-1",
    )
    assert run["status"] == "started"
    assert run["temporal_workflow_id"] == "wf-1"

    fetched = store.get_run("r-1")
    assert fetched is not None
    assert fetched["product_name"] == "Magnetic Phone Mount"

    updated = store.update_run(
        "r-1",
        status="completed",
        launch_score=0.72,
        decision="launch",
        store_url="https://magneticmount.fastaisolution.com",
    )
    assert updated["status"] == "completed"
    assert updated["launch_score"] == 0.72
    assert updated["completed_at"] is not None


def test_memory_store_returns_events_ordered_by_timestamp(store):
    base = datetime(2026, 5, 23, 12, 0, 0, tzinfo=timezone.utc)
    # Insert out of order
    store.write_event("r-1", "buyer", "completed", "later", timestamp=base + timedelta(seconds=10))
    store.write_event("r-1", "research", "completed", "earliest", timestamp=base)
    store.write_event("r-1", "legal_risk", "completed", "middle", timestamp=base + timedelta(seconds=5))
    # Different run shouldn't leak in
    store.write_event("r-2", "research", "completed", "other run", timestamp=base)

    events = store.get_events("r-1")
    assert [e["message"] for e in events] == ["earliest", "middle", "later"]
    assert all(e["run_id"] == "r-1" for e in events)


def test_business_filtering_by_status(store):
    store.write_business({"id": "b1", "status": "active", "category": "x"})
    store.write_business({"id": "b2", "status": "failed", "category": "x"})
    store.write_business({"id": "b3", "status": "paused", "category": "y"})

    assert {b["id"] for b in store.list_businesses("active")} == {"b1"}
    assert {b["id"] for b in store.list_businesses(["failed", "paused"])} == {"b2", "b3"}
    assert {b["id"] for b in store.list_businesses()} == {"b1", "b2", "b3"}


def test_datadog_wrapper_no_ops_without_api_key(monkeypatch):
    monkeypatch.delenv("DATADOG_API_KEY", raising=False)
    # Force re-init so the env change takes effect
    monkeypatch.setattr(dd_module, "_initialized", False)
    monkeypatch.setattr(dd_module, "_statsd", None)
    monkeypatch.setattr(dd_module, "_tracer", None)

    # None of these should raise even though Datadog isn't configured
    dd_module.emit_count("test.metric", value=1, tags={"agent": "research"})
    dd_module.emit_histogram("test.latency", 12.5)
    dd_module.emit_gauge("test.gauge", 7)

    with dd_module.trace_activity("test.activity", tags={"agent": "buyer"}):
        time.sleep(0)

    # Confirm we never lazily initialized a real statsd client
    assert dd_module._statsd is None
    assert dd_module._tracer is None
