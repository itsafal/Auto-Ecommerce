# Tech Stack

## Final Direction

We are building one AI commerce platform that can launch many focused
micro-stores.

Example storefront URLs:

- `magneticmount.fastaisolution.com`
- `ergokeyboard.fastaisolution.com`
- `portableblender.fastaisolution.com`

These should look like separate one-product stores to users, but they should
all run on one shared platform.

## Core Architecture

```text
Nimble trend signal / demo trigger
        |
        v
FastAPI run orchestrator
        |
        v
Claude SDK agents
        |
        v
Launch score + store config
        |
        v
Next.js storefront + dashboard
        |
        v
ClickHouse + Datadog
```

## Frontend

**Choice:** Next.js, React, Tailwind CSS

Responsibilities:

- Render the public storefront for each product slug.
- Read the request host, extract the subdomain, and load the matching store.
- Render the internal dashboard for demo control, launch runs, agent timeline,
  launch score, and store status.
- Show the current agent run in real time with a clear visual timeline.
- Let an operator trigger a new agent run from the UI at any time.

Routing model:

- `magneticmount.fastaisolution.com` routes to the same Next.js app.
- Middleware extracts `magneticmount`.
- The app fetches the store config for that slug.
- The user sees a focused one-product store.

## Backend

**Choice:** Python + FastAPI

Responsibilities:

- Start launch runs.
- Own the `run_id`.
- Call agents in order.
- Calculate the launch score.
- Create store configs.
- Write run state, agent events, businesses, and signals to ClickHouse.
- Emit traces and metrics to Datadog.

Primary endpoints:

- `POST /api/demo/trigger`
- `POST /api/launch-store`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `GET /api/stores`
- `GET /api/agents/status`

## Agents

**Choice:** Claude SDK for all agents.

Use Claude as the primary agent runtime. Keep Gemini fallback out of the first
build unless there is extra time.

Agents:

1. CEO / Orchestrator Agent
   - Starts the run.
   - Calls the other agents.
   - Combines outputs.
   - Decides whether to launch.

2. Research Agent
   - Reads trend data.
   - Checks demand, competitors, pricing, and market signal.
   - Produces `trend_score` and research summary.

3. Buyer Agent
   - Checks supplier options.
   - Estimates unit cost, shipping time, supplier rating, margin, and confidence.
   - Produces `supplier_confidence` and `margin_score`.

4. Legal / Risk Agent
   - Performs a lightweight ecommerce risk screen.
   - Flags trademark risk, regulated product risk, import/shipping risk, and ad
     claim risk.
   - Produces `compliance_risk`.

5. Advertising Agent
   - Generates product name, tagline, description, CTA, and hero image prompt.
   - Produces the content needed by the storefront.

Non-agent services:

- Store creator
- ClickHouse client
- Datadog client
- Scheduler
- Demo fallback loader

## Trend Detection

**Choice:** Nimble primary, cached fixtures for demo fallback.

Runtime flow:

- A scheduled job checks trends periodically.
- Nimble provides the trend signal.
- The backend starts a launch run for promising products.

Demo flow:

- `POST /api/demo/trigger` starts the same pipeline immediately.
- `DEMO_MODE=true` can force cached trend data and deterministic outputs.

## Database

**Choice:** ClickHouse Cloud

Use ClickHouse as the shared memory and analytics layer.

Tables:

- `businesses`
- `trend_signals`
- `agent_decisions`
- `launch_runs`
- `agent_events`
- `business_relationships`

ClickHouse is not just storage in the demo. It should be visible as the place
where the system remembers every launch and learns across stores.

## Observability

**Choice:** Datadog

Use Datadog for:

- FastAPI traces
- agent latency
- agent decision counts
- run-level tags
- external API timing
- store health metrics
- demo dashboard panels

Every important trace should include:

- `run_id`
- `agent`
- `product_slug`
- `demo_mode`

## Dashboard Experience

The dashboard is the control room for the demo and the product.

Required UI:

- A **Trigger Agent Run** button that can start the pipeline at any time.
- A product input or dropdown for choosing what product to test.
- A real-time run timeline showing each agent step:
  - Research
  - Buyer
  - Legal / Risk
  - Advertising
  - Store Creator
- Visual status for each step:
  - pending
  - running
  - completed
  - failed
  - fallback used
- A launch score panel showing:
  - trend score
  - margin score
  - supplier confidence
  - compliance risk
  - final launch/no-launch decision
- A live event feed for agent messages and decisions.
- A final store URL when launch succeeds.

Recommended visualization:

- Use a horizontal or vertical pipeline view for the main agent sequence.
- Use animated active states while an agent is running.
- Use compact event cards below the pipeline for detailed logs.
- Keep the newest run visible by default.
- Allow viewing older runs by `run_id`.

Runtime behavior:

- Clicking **Trigger Agent Run** calls `POST /api/demo/trigger` or
  `POST /api/launch-store`.
- The UI receives the returned `run_id`.
- The UI polls `GET /api/runs/{run_id}` and `GET /api/runs/{run_id}/events`
  every 1-2 seconds, or uses Server-Sent Events if there is time.
- The UI updates the visualization as each agent event arrives.

## Domain and Subdomains

**Choice:** GoDaddy DNS for `fastaisolution.com`

Use wildcard DNS:

```text
*.fastaisolution.com -> deployed frontend
```

Important decision:

- Do not deploy a new website for every product.
- Do not depend on live DNS creation during the demo.
- Set wildcard DNS before the demo.
- Each new store is a database row plus a subdomain route.

GoDaddy API can be used later for clean DNS management, but it should not be on
the critical demo path.

## Deployment

**Choice:** Render for everything.

Deploy on Render:

1. Render Web Service: FastAPI backend
2. Render Web Service: Next.js frontend
3. Render Cron Job: scheduled trend monitor

Recommended services:

- `auto-ecommerce-api`
- `auto-ecommerce-web`
- `auto-ecommerce-trend-cron`

Environment variables:

- `ANTHROPIC_API_KEY`
- `NIMBLE_API_KEY`
- `CLICKHOUSE_HOST`
- `CLICKHOUSE_USER`
- `CLICKHOUSE_PASSWORD`
- `CLICKHOUSE_DATABASE`
- `DATADOG_API_KEY`
- `DATADOG_SITE`
- `BASE_DOMAIN=fastaisolution.com`
- `DEMO_MODE=false`

For demo fallback:

- Set `DEMO_MODE=true` if external APIs are unstable.
- Use cached Nimble response.
- Use cached supplier response.
- Use deterministic Claude-like fixture outputs if needed.

## Scheduler

**Choice:** Render Cron Job

The cron job runs the trend monitor.

Suggested demo-safe schedule:

```text
*/30 * * * *  python -m backend.jobs.trend_monitor
```

For the live demo, do not wait for cron. Use:

```text
POST /api/demo/trigger
```

## Launch Decision

Use a simple launch score:

```python
launch_score = (
    trend_score * 0.30
    + margin_score * 0.25
    + supplier_confidence * 0.25
    - compliance_risk * 0.20
)
```

Decision:

- Launch if score is high enough.
- Pause or reject if score is low.
- Always show the score and component values in the dashboard.

## Hackathon Build Priority

Build in this order:

1. FastAPI `/api/demo/trigger`
2. Claude SDK agent wrappers with validated JSON outputs
3. ClickHouse schema and inserts
4. Next.js micro-store template
5. Dashboard run timeline
6. Render deployment
7. Datadog traces and metrics
8. Render cron trend monitor
9. Optional live Nimble path
10. Optional GoDaddy API cleanup

## Final Stack Summary

| Layer | Final Choice |
| --- | --- |
| Frontend | Next.js + React + Tailwind CSS |
| Backend | Python + FastAPI |
| Agents | Claude SDK |
| Trend data | Nimble |
| Demo fallback | Cached fixtures with `DEMO_MODE=true` |
| Database | ClickHouse Cloud |
| Observability | Datadog |
| Domain | GoDaddy wildcard DNS |
| Deployment | Render |
| Scheduler | Render Cron Job |
| Store model | Many subdomains, one shared platform |
