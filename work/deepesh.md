# Deepesh Work Plan

## Mission

Own the backend run system: FastAPI endpoints, Temporal workflow skeleton, worker process, shared contracts, and local trigger path.

Your work should let anyone start a launch run without real API keys. The first version can use fake activities and fixtures, but it must expose the same API shape we will use during integration.

## Independent Boundary

You own:

- `backend/main.py`
- `backend/api/runs.py`
- `backend/workflows/launch_store.py`
- `backend/workflows/activities.py`
- `backend/workflows/worker.py`
- `backend/schemas.py`
- `backend/settings.py`
- `tests/backend/test_run_api.py`
- `tests/backend/test_launch_workflow.py`

Do not depend on Safal's UI, Ali's real ClickHouse client, or Deepali's final agents to finish your first pass. Use fake activity outputs that match the contracts in `work/integration-guide.md`.

## Build Tasks

1. Create the FastAPI app.
2. Create shared Pydantic schemas for:
   - `LaunchRequest`
   - `LaunchRun`
   - `AgentEvent`
   - `ResearchOutput`
   - `BuyerOutput`
   - `RiskOutput`
   - `AdvertisingOutput`
   - `StoreOutput`
3. Add `POST /api/demo/trigger`.
   - Input: optional product name.
   - Output: `run_id`, `status`, `temporal_workflow_id`.
4. Add `POST /api/launch-store`.
   - Same contract as demo trigger.
   - For now, use fixture-backed execution.
5. Add `GET /api/runs/{run_id}`.
   - Return current run state.
6. Add `GET /api/runs/{run_id}/events`.
   - Return ordered timeline events.
7. Add Temporal `LaunchStoreWorkflow`.
   - Calls activities in this order:
     - `research_activity`
     - `buyer_activity`
     - `legal_risk_activity`
     - `advertising_activity`
     - `score_launch_activity`
     - `create_store_activity`
8. Add Temporal worker entrypoint.
   - Task queue: `launch-store`.
9. Add a synchronous dev fallback.
   - If Temporal is disabled locally, the API should still produce a complete fake run.
   - Use env var: `USE_TEMPORAL=false`.

## Trigger Requirement

You must provide a backend trigger that works without API keys:

```bash
curl -X POST http://localhost:8000/api/demo/trigger \
  -H "Content-Type: application/json" \
  -d '{"product_name":"Magnetic Phone Mount"}'
```

Expected output:

```json
{
  "run_id": "uuid",
  "status": "started",
  "temporal_workflow_id": "launch-store-uuid"
}
```

## Tests

Add tests before integration:

- `test_demo_trigger_returns_run_id`
- `test_launch_store_returns_run_id`
- `test_get_run_returns_known_run`
- `test_get_events_returns_ordered_events`
- `test_workflow_calls_activities_in_expected_order`
- `test_sync_fallback_completes_run_without_temporal`

Use fixtures only. No API keys.

Suggested command:

```bash
uv run pytest tests/backend -v
```

## Done Criteria

- FastAPI starts locally.
- Demo trigger works without Temporal if `USE_TEMPORAL=false`.
- Temporal workflow code exists and can be wired when Temporal is available.
- Run/event contracts match `work/integration-guide.md`.
- Tests pass locally.
