---
name: fastapi-auto-ecommerce-backend
description: Use when building or modifying the Auto-Ecommerce FastAPI backend, including run trigger endpoints, run status APIs, store APIs, health checks, Temporal workflow starts, Pydantic request/response models, ClickHouse writes, Datadog instrumentation, and demo-mode fallbacks.
---

# FastAPI Auto-Ecommerce Backend

Build FastAPI as the API boundary for the launch platform. Keep long-running work in Temporal; FastAPI should start workflows and expose state.

## Required Endpoints

- `POST /api/demo/trigger`
- `POST /api/launch-store`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `GET /api/stores`
- `GET /api/agents/status`

## Workflow

1. Validate all request bodies with Pydantic.
2. Create or accept a `run_id`.
3. Start the Temporal `LaunchStoreWorkflow`.
4. Return immediately with `{ "run_id": "...", "status": "started" }`.
5. Read run status and timeline events from ClickHouse for dashboard endpoints.
6. Emit Datadog traces and metrics with `run_id`, `product_slug`, and `demo_mode`.

## Rules

- Do not hold HTTP requests open while agents run.
- Keep API handlers thin. Put workflow logic in Temporal activities and shared services.
- Keep secrets in environment variables.
- In `DEMO_MODE=true`, use deterministic fixtures and record fallback usage in the event timeline.
- Return predictable error shapes so the dashboard can render failed and fallback states.
