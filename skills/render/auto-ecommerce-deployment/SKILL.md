---
name: render-auto-ecommerce-deployment
description: Use when deploying Auto-Ecommerce services to Render, configuring FastAPI and Next.js web services, Temporal workers, cron jobs, environment variables, health checks, logs, demo-mode settings, and production-like hackathon deployment topology.
---

# Render Auto-Ecommerce Deployment

Use Render as the deployment platform for the hackathon build.

## Services

Create or maintain:

- `auto-ecommerce-api`: FastAPI web service
- `auto-ecommerce-web`: Next.js web service
- `auto-ecommerce-worker`: Temporal background worker
- `auto-ecommerce-trend-cron`: Render Cron Job for scheduled trend checks

## Environment

Required variables include:

- `GEMINI_API_KEY`
- `NIMBLE_API_KEY`
- `CLICKHOUSE_HOST`
- `CLICKHOUSE_USER`
- `CLICKHOUSE_PASSWORD`
- `CLICKHOUSE_DATABASE`
- `DATADOG_API_KEY`
- `DATADOG_SITE`
- `TEMPORAL_ADDRESS`
- `TEMPORAL_NAMESPACE`
- `TEMPORAL_API_KEY`
- `TEMPORAL_TASK_QUEUE`
- `BASE_DOMAIN`
- `DEMO_MODE`

## Rules

- Keep frontend and backend environment variables separate.
- Never expose server-only API keys to Next.js client code.
- Add health checks for API and worker readiness.
- Prefer `DEMO_MODE=true` for rehearsals with unstable external APIs.
- Confirm wildcard domain routing before the demo.
