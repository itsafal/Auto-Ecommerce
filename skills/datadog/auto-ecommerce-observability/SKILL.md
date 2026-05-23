---
name: datadog-auto-ecommerce-observability
description: Use when instrumenting Auto-Ecommerce with Datadog, including FastAPI traces, Temporal activity spans, ADK/Gemini agent latency, external API timing, ClickHouse insert metrics, store health metrics, dashboard panels, and run-level trace correlation.
---

# Datadog Auto-Ecommerce Observability

Make the launch pipeline visible during the demo and useful during debugging.

## Required Tags

Every trace, span, log, or metric tied to a run should include:

- `run_id`
- `agent`
- `product_slug`
- `demo_mode`

## Metrics

Emit:

- `agent.decisions`
- `agent.latency_ms`
- `launch.score`
- `stores.active_count`
- `trend.signals_detected`
- `fallback.used`
- `external_api.latency_ms`

## Dashboard Panels

Include:

- Agent activity timeline
- Launch score by run
- External API latency
- Fallback usage count
- Store health
- Error count by step

## Rules

- Record fallback paths as visible events, not hidden implementation details.
- Correlate FastAPI request traces with Temporal activity traces using `run_id`.
- Keep dashboard panels judge-facing and easy to explain.
