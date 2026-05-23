# Ali Work Plan

## Mission

Own the data, analytics, knowledge graph, fixtures, launch scoring, and observability wrappers.

Your work should make the system look intelligent and measurable even before real external APIs are connected.

## Independent Boundary

You own:

- `backend/db/schema.sql`
- `backend/db/clickhouse.py`
- `backend/db/memory_store.py`
- `backend/analytics/launch_score.py`
- `backend/analytics/bias.py`
- `backend/analytics/relationships.py`
- `backend/observability/datadog.py`
- `backend/fixtures/demo_trend.json`
- `backend/fixtures/suppliers.json`
- `backend/fixtures/seed_businesses.json`
- `scripts/seed_demo_data.py`
- `tests/analytics/test_launch_score.py`
- `tests/analytics/test_bias.py`
- `tests/analytics/test_relationships.py`
- `tests/db/test_memory_store.py`

Do not require real ClickHouse or Datadog for the first pass. Provide an in-memory fallback and no-op Datadog wrapper.

## Build Tasks

1. Write ClickHouse schema.
   - `businesses`
   - `trend_signals`
   - `agent_decisions`
   - `launch_runs`
   - `agent_events`
   - `business_relationships`
2. Build `memory_store.py`.
   - Same interface as ClickHouse client.
   - Stores runs, events, businesses, and trend signals in memory.
   - Used when `USE_CLICKHOUSE=false`.
3. Build launch scoring.
   - Formula:

```python
launch_score = (
    trend_score * 0.30
    + margin_score * 0.25
    + supplier_confidence * 0.25
    - compliance_risk * 0.20
)
```

4. Build bias mechanism.
   - Input: failed/paused businesses and current trend score.
   - Output: ranked near-miss products worth retrying.
5. Build relationship generator.
   - Connect businesses by:
     - shared category
     - shared supplier
     - similar margin range
6. Build Datadog wrapper.
   - `emit_count`
   - `emit_histogram`
   - `emit_gauge`
   - `trace_activity`
   - No-op if `DATADOG_API_KEY` is missing.
7. Build demo seed script.
   - Seeds 5-10 businesses.
   - Include at least:
     - 2 failed
     - 2 active
     - 1 paused

## Trigger Requirement

You must provide local data triggers without external services.

Seed demo data:

```bash
USE_CLICKHOUSE=false uv run python scripts/seed_demo_data.py
```

Calculate launch score:

```bash
uv run python -m backend.analytics.launch_score \
  --trend-score 0.86 \
  --margin-score 0.72 \
  --supplier-confidence 0.84 \
  --compliance-risk 0.12
```

Expected output:

```json
{
  "launch_score": 0.615,
  "decision": "launch"
}
```

## Tests

Add tests:

- `launch score matches formula`
- `low score returns no-launch decision`
- `high score returns launch decision`
- `bias ranks failed recent high-trend product first`
- `relationships connect businesses with same supplier`
- `memory store writes and reads run`
- `memory store returns events ordered by timestamp`
- `datadog wrapper no-ops without api key`

Suggested command:

```bash
USE_CLICKHOUSE=false uv run pytest tests/analytics tests/db -v
```

## Done Criteria

- Schema is written.
- Memory store works without ClickHouse.
- Launch score and bias logic work from fixtures.
- Demo seed data exists.
- Observability wrapper is safe without keys.
- Tests pass locally.
