# Integration Guide

## Goal

This guide explains how to merge the four independent workstreams into one working demo.

For now, nobody needs real API keys. Every component must support fixture/mock mode. During integration, we will replace fixture mode with real Gemini/ADK, Nimble, ClickHouse, Datadog, Temporal Cloud, and Render configuration.

## Ownership Map

| Owner | Area | Primary Output |
| --- | --- | --- |
| Deepesh | FastAPI + Temporal | Triggerable backend workflow |
| Safal | Next.js UI | Dashboard + storefront + visual agent run |
| Deepali | ADK/Gemini agents | Independently triggerable agents |
| Ali | Data + analytics + observability | Schema, memory store, scoring, bias, metrics |

## Shared Rule

Each person must finish their slice with:

- local trigger path
- fixture/mock mode
- tests
- no required API keys
- documented commands
- outputs matching this file

## End-to-End Flow

1. User opens dashboard.
2. User enters product.
3. User clicks `Trigger Agent Run`.
4. Frontend calls `POST /api/demo/trigger`.
5. FastAPI creates `run_id`.
6. FastAPI starts Temporal `LaunchStoreWorkflow`.
7. Temporal runs activities:
   - Research
   - Buyer
   - Legal / Risk
   - Advertising
   - Score Launch
   - Create Store
8. Each activity writes `agent_events`.
9. Dashboard polls run state and events.
10. Store URL appears when launch succeeds.

## Shared API Contracts

### POST `/api/demo/trigger`

Request:

```json
{
  "product_name": "Magnetic Phone Mount"
}
```

Response:

```json
{
  "run_id": "7c0b5571-2f44-40ef-8c3f-3efca9b7e11f",
  "status": "started",
  "temporal_workflow_id": "launch-store-7c0b5571-2f44-40ef-8c3f-3efca9b7e11f"
}
```

### GET `/api/runs/{run_id}`

Response:

```json
{
  "run_id": "7c0b5571-2f44-40ef-8c3f-3efca9b7e11f",
  "temporal_workflow_id": "launch-store-7c0b5571-2f44-40ef-8c3f-3efca9b7e11f",
  "product_name": "Magnetic Phone Mount",
  "slug": "magneticmount",
  "status": "completed",
  "launch_score": 0.615,
  "decision": "launch",
  "store_url": "https://magneticmount.fastaisolution.com",
  "error": null
}
```

Allowed run statuses:

- `started`
- `running`
- `completed`
- `failed`
- `fallback_completed`

### GET `/api/runs/{run_id}/events`

Response:

```json
{
  "run_id": "7c0b5571-2f44-40ef-8c3f-3efca9b7e11f",
  "events": [
    {
      "agent_name": "research",
      "event_type": "completed",
      "message": "Research completed with trend score 0.86",
      "timestamp": "2026-05-23T17:30:00Z",
      "payload": {
        "trend_score": 0.86,
        "confidence": 0.82
      }
    }
  ]
}
```

Allowed event types:

- `pending`
- `running`
- `completed`
- `failed`
- `fallback_used`

Allowed agent names:

- `research`
- `buyer`
- `legal_risk`
- `advertising`
- `score_launch`
- `store_creator`

## Shared Agent Output Contracts

### Research Output

```json
{
  "product_name": "Magnetic Phone Mount",
  "category": "phone_accessories",
  "trend_score": 0.86,
  "search_volume": 42000,
  "social_mentions": 18000,
  "competitor_summary": "Several compact car-mount brands are trending with prices from $24 to $39.",
  "price_range": {
    "low": 24.0,
    "high": 39.0
  },
  "confidence": 0.82
}
```

### Buyer Output

```json
{
  "supplier_name": "Demo Supplier 4821",
  "unit_cost": 8.4,
  "shipping_days": 6,
  "rating": 4.7,
  "estimated_margin": 0.61,
  "margin_score": 0.72,
  "confidence_score": 0.84,
  "risk_flags": []
}
```

### Legal / Risk Output

```json
{
  "cleared": true,
  "risk_score": 0.12,
  "flags": [],
  "recommendation": "Safe for demo launch. Avoid claims about crash prevention or guaranteed safety."
}
```

### Advertising Output

```json
{
  "product_name": "MagSnap Pro",
  "tagline": "Mount your phone in one clean snap.",
  "description": "A compact magnetic phone mount built for fast one-handed docking and a cleaner dashboard.",
  "cta_text": "Buy Now - Ships in 3 days",
  "hero_image_prompt": "Clean studio product photo of a compact magnetic phone mount on a car dashboard",
  "hero_image_url": "/demo/magnetic-phone-mount.png"
}
```

### Store Output

```json
{
  "store_id": "14ddc76c-e9cc-42d3-a280-79d6f5a73b49",
  "slug": "magneticmount",
  "store_url": "https://magneticmount.fastaisolution.com",
  "product_name": "MagSnap Pro",
  "description": "A compact magnetic phone mount built for fast one-handed docking and a cleaner dashboard.",
  "price": 29.99,
  "hero_image_url": "/demo/magnetic-phone-mount.png",
  "supplier": "Demo Supplier 4821",
  "cta_text": "Buy Now - Ships in 3 days"
}
```

## Integration Order

1. Merge Ali's schemas, fixtures, memory store, and scoring.
2. Merge Deepali's fixture-backed ADK agent modules.
3. Merge Deepesh's FastAPI + Temporal workflow.
4. Connect Deepesh activities to Deepali agent runners.
5. Connect Deepesh run/event storage to Ali memory store first.
6. Merge Safal's frontend.
7. Point frontend API client at FastAPI.
8. Run fixture-mode end-to-end demo.
9. Replace memory store with ClickHouse.
10. Enable Temporal Cloud.
11. Enable real Gemini/ADK credentials.
12. Enable Nimble.
13. Enable Datadog.
14. Deploy all services on Render.

## Integration Test Checklist

Run these before adding real API keys:

```bash
USE_CLICKHOUSE=false USE_AGENT_FIXTURES=true USE_TEMPORAL=false uv run pytest tests -v
```

Then run the backend:

```bash
USE_CLICKHOUSE=false USE_AGENT_FIXTURES=true USE_TEMPORAL=false uv run uvicorn backend.main:app --reload
```

Then run the frontend:

```bash
NEXT_PUBLIC_USE_MOCKS=false pnpm dev
```

Manual acceptance:

1. Open `/dashboard`.
2. Trigger `Magnetic Phone Mount`.
3. Confirm `run_id` appears.
4. Confirm timeline updates through all agents.
5. Confirm launch score appears.
6. Confirm store URL appears.
7. Open `http://localhost:3000/store/magneticmount`.
8. Confirm storefront renders the generated product.

## Later Real-Service Switches

Only after fixture-mode integration works:

- Set Google/Gemini credentials for ADK.
- Set Nimble API key.
- Set ClickHouse credentials.
- Set Datadog API key.
- Set Temporal Cloud address, namespace, and API key.
- Configure Render services.
- Configure wildcard DNS for `*.fastaisolution.com`.

## Conflict Avoidance

- Deepesh owns workflow and API routing.
- Safal owns frontend files only.
- Deepali owns `backend/agents`.
- Ali owns `backend/db`, `backend/analytics`, fixtures, observability.
- Shared schema changes must be reflected in this guide before merging.
- No one should require real API keys in their branch.
