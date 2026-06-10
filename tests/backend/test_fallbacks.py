"""Resilience tests for expired/dead third-party subscriptions.

Covers the two paid dependencies that can lapse without code changes:
  - ClickHouse Cloud → get_client() must fall back to the in-memory store
    instead of crashing (or hanging) the API.
  - Nimble SERP → an auth-rejected key must open the circuit breaker so
    research stops paying a doomed network round trip per query.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from backend.db import clickhouse
from backend.db.memory_store import MemoryStore
from backend.integrations import nimble


@pytest.fixture(autouse=True)
def _reset_singletons():
    clickhouse.reset_client_for_tests()
    nimble.reset_circuit_for_tests()
    yield
    clickhouse.reset_client_for_tests()
    nimble.reset_circuit_for_tests()


def test_get_client_falls_back_to_memory_when_clickhouse_unreachable(monkeypatch):
    monkeypatch.setenv("USE_CLICKHOUSE", "true")
    monkeypatch.setenv("CLICKHOUSE_HOST", "expired-subscription.invalid")
    monkeypatch.setenv("CLICKHOUSE_CONNECT_TIMEOUT", "1")

    client = clickhouse.get_client()

    assert isinstance(client, MemoryStore)
    assert clickhouse.clickhouse_fallback_reason() is not None
    # The fallback is cached — a second call must not retry the connection.
    assert clickhouse.get_client() is client


def test_get_client_reconnects_after_cooldown(monkeypatch):
    monkeypatch.setenv("USE_CLICKHOUSE", "true")
    monkeypatch.setenv("CLICKHOUSE_HOST", "expired-subscription.invalid")
    monkeypatch.setenv("CLICKHOUSE_CONNECT_TIMEOUT", "1")
    monkeypatch.setenv("CLICKHOUSE_RETRY_COOLDOWN", "0")

    assert isinstance(clickhouse.get_client(), MemoryStore)

    # The "instance woke up": the next construction attempt succeeds.
    class FakeClickHouseClient:
        pass

    monkeypatch.setattr(clickhouse, "ClickHouseClient", FakeClickHouseClient)

    client = clickhouse.get_client()
    assert isinstance(client, FakeClickHouseClient)
    assert clickhouse.clickhouse_fallback_reason() is None


def test_fallback_store_supports_auth_and_decisions(monkeypatch):
    monkeypatch.setenv("USE_CLICKHOUSE", "true")
    monkeypatch.setenv("CLICKHOUSE_HOST", "expired-subscription.invalid")
    monkeypatch.setenv("CLICKHOUSE_CONNECT_TIMEOUT", "1")

    store = clickhouse.get_client()

    user = store.create_user("ops@fastaisolution.com", "pbkdf2_sha256$1$a$b", "Ops")
    assert store.get_user_by_email("ops@fastaisolution.com")["id"] == user["id"]

    # ClickHouseClient-shaped kwargs call must work on the memory store too.
    record = store.write_agent_decision(
        run_id="11111111-1111-1111-1111-111111111111",
        agent_name="research",
        action="completed",
        latency_ms=42,
        model_used="fixture",
    )
    assert record["agent_name"] == "research"


def test_nimble_circuit_opens_on_auth_failure(monkeypatch):
    monkeypatch.setenv("NIMBLE_API_KEY", "expired-key")
    calls = {"count": 0}

    class FakeResponse:
        status_code = 401

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "401", request=httpx.Request("POST", nimble.DEFAULT_BASE_URL), response=self  # type: ignore[arg-type]
            )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            calls["count"] += 1
            return FakeResponse()

    monkeypatch.setattr(nimble.httpx, "AsyncClient", FakeClient)

    assert asyncio.run(nimble.fetch_serp_summary("magnetic phone mount")) is None
    assert nimble.nimble_disabled_reason() is not None

    # Circuit is open: the second query must not hit the network at all.
    assert asyncio.run(nimble.fetch_serp_summary("portable power station")) is None
    assert calls["count"] == 1
