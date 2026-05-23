# Auto-Ecommerce Hackathon Plan

## Context

**Problem**: Launching and operating profitable e-commerce stores requires constant market research, vendor negotiation, legal compliance, customer service, and marketing — all simultaneously. Most people can't do this at scale.

**Solution**: An AI swarm that autonomously discovers trending products, spins up a storefront, sources suppliers, and operates the business — with a shared ClickHouse knowledge graph that gets smarter across every store it runs.

**Why it wins**: Three partner tools (Nimble for scraping, ClickHouse for intelligence compounding, Datadog for live observability) are each load-bearing — not decorative. The demo shows a real end-to-end business being launched live on stage.

---

## Core Demo Loop (What Judges See)

1. **Trend signal fires** — Nimble detects a trending product (e.g., viral TikTok item) with real search/social data
2. **CEO agent activates** — orchestrator spawns Research + Buyer agents
3. **Research agent** — pulls competitor pricing, demand signals, margin estimates; writes findings to ClickHouse
4. **Buyer agent** — sources 2-3 suppliers via API/scraping, picks best price/shipping combo
5. **Store goes live** — Next.js template auto-populates with product name, description, images, pricing; GoDaddy API provisions `ergokeyboard.fastaisolution.com` in real-time
6. **Knowledge graph node created** — ClickHouse records this business as a node (product category, margin, supplier, launch time)
7. **Datadog dashboard lights up** — shows agent activity timeline, store health, API call traces, order pipeline
8. **Bias mechanism surfaces** — system shows a "near-miss" from a previously failed category that's now worth retrying (knowledge compounding)
9. **Launch decision score appears** — dashboard shows trend score, margin score, supplier confidence, compliance risk, and final launch/no-launch decision
10. **Temporal workflow persists the run** — every long-running agent step is a Temporal activity under one `run_id`, visible in the dashboard, ClickHouse, and Datadog traces

Demo runtime: ~7 minutes. Everything is scripted to trigger live, with pre-warmed state as fallback.

---

## Architecture

```
[Demo Trigger / Nimble Trend Signal]
              |
              v
[FastAPI Run API: create run_id, start Temporal workflow]
              |
              v
[Temporal LaunchStoreWorkflow: retries, durable state, fallbacks]
              |
              v
[Research Activity] -> [Buyer Activity] -> [Legal Activity] -> [Advertising Activity] -> [Store Activity]
              |               |                 |                       |
              v               v                 v                       v
        [Launch Scoring + Supplier Confidence + Risk Flags]
              |
              v
     [ClickHouse Knowledge Graph + Datadog Observability]
```

**Backend**: Python + FastAPI  
**Frontend**: Next.js (React) — single template, AI populates content; subdomain-routed  
**Async orchestration**: Temporal — durable workflows, activity retries, worker execution  
**Agents**: Google ADK with Gemini for all agents  
**DB**: ClickHouse Cloud — columnar storage for business nodes, agent logs, performance metrics  
**Scraping**: Nimble API (primary trend detection) + Scrapling (supplemental)  
**Observability**: Datadog APM + custom dashboards  
**Domain**: `fastaisolution.com` via GoDaddy — each store gets `{product-slug}.fastaisolution.com`  
**Deployment**: Render for frontend, FastAPI backend, Temporal worker, and scheduled trend cron  

---

## Temporal Async Workflow Architecture

FastAPI should not hold a single HTTP request open while multiple agents call Gemini through ADK, Nimble, supplier sources, ClickHouse, and store creation. FastAPI creates a `run_id`, starts a Temporal workflow, and immediately returns the `run_id` to the dashboard.

### Workflow shape:

```text
LaunchStoreWorkflow(run_id, product_input)
        |
        v
ResearchActivity
        |
        v
BuyerActivity
        |
        v
LegalRiskActivity
        |
        v
AdvertisingActivity
        |
        v
ScoreLaunchActivity
        |
        v
CreateStoreActivity
```

### Why Temporal is load-bearing:

- Agent runs survive FastAPI restarts.
- Gemini/ADK, Nimble, and supplier calls get timeout and retry policies.
- Each agent step is visible as a workflow activity.
- The dashboard can follow progress by `run_id`.
- Demo fallback usage is recorded as a real workflow event.
- Scheduled trend monitoring and manual UI triggers use the same workflow path.

### Temporal rules:

- Workflow code only orchestrates. It must stay deterministic.
- Gemini/ADK agent calls, Nimble, ClickHouse, Datadog, supplier lookup, image generation, and store creation happen inside activities.
- Each activity writes `agent_events` rows before and after execution.
- Each activity emits Datadog tags for `run_id`, `agent`, `product_slug`, and `demo_mode`.
- Use Temporal Cloud for hackathon deployment if possible. Use local Temporal via Docker Compose for development.

---

## Dynamic Subdomain Architecture

**Domain**: `fastaisolution.com` (GoDaddy, registered through 2030)

### How it works:
1. **One-time setup** (before hackathon): Add a wildcard DNS A record `*.fastaisolution.com → server IP` in GoDaddy DNS settings. This routes ALL subdomains to the deployment instantly with no API call needed per store.
2. **Per-store provisioning**: When a new store is spun up, optionally call GoDaddy API to create a specific CNAME record (for clean DNS management), but the wildcard already makes it live immediately.
3. **Next.js middleware**: Reads the `host` header, extracts the subdomain slug, fetches that store's config from FastAPI/ClickHouse, renders the template.

### GoDaddy API call (Safal implements):
```python
import httpx

GODADDY_KEY = os.environ["GODADDY_API_KEY"]
GODADDY_SECRET = os.environ["GODADDY_API_SECRET"]
BASE_DOMAIN = "fastaisolution.com"

async def provision_subdomain(slug: str, target_ip: str):
    """Creates {slug}.fastaisolution.com → target_ip"""
    url = f"https://api.godaddy.com/v1/domains/{BASE_DOMAIN}/records/A/{slug}"
    headers = {"Authorization": f"sso-key {GODADDY_KEY}:{GODADDY_SECRET}"}
    payload = [{"data": target_ip, "ttl": 600}]
    async with httpx.AsyncClient() as client:
        resp = await client.put(url, json=payload, headers=headers)
        resp.raise_for_status()
    return f"https://{slug}.{BASE_DOMAIN}"
```

### Next.js subdomain middleware (`middleware.ts`):
```typescript
import { NextRequest, NextResponse } from 'next/server'

export function middleware(req: NextRequest) {
  const host = req.headers.get('host') || ''
  const slug = host.split('.')[0]  // "ergokeyboard" from "ergokeyboard.fastaisolution.com"
  
  if (slug && slug !== 'www' && slug !== 'fastaisolution') {
    // Rewrite to /store/[slug] without changing the URL the user sees
    return NextResponse.rewrite(new URL(`/store/${slug}`, req.url))
  }
}

export const config = { matcher: ['/((?!api|_next|favicon.ico).*)'] }
```

### Store URL pattern:
- `clothes.fastaisolution.com` → clothing store
- `ergokeyboard.fastaisolution.com` → ergo keyboard store  
- `magneticmount.fastaisolution.com` → phone mount store

**Pre-demo setup**: Set the wildcard DNS record manually in GoDaddy before the hackathon. The API call is for show — stores are live the moment the wildcard is set.

---

## ClickHouse Schema (Knowledge Graph)

```sql
-- Business nodes
CREATE TABLE businesses (
  id UUID,
  product_name String,
  category String,
  launch_time DateTime,
  store_url String,
  status Enum('active', 'failed', 'paused'),
  margin_estimate Float32,
  supplier_id String,
  trend_score Float32,
  bias_score Float32,
  created_at DateTime DEFAULT now()
) ENGINE = MergeTree() ORDER BY (category, launch_time);

-- Agent decision log
CREATE TABLE agent_decisions (
  id UUID,
  business_id UUID,
  agent_name String,
  action String,
  input_summary String,
  output_summary String,
  latency_ms UInt32,
  model_used String,
  timestamp DateTime DEFAULT now()
) ENGINE = MergeTree() ORDER BY (agent_name, timestamp);

-- Product signals from Nimble
CREATE TABLE trend_signals (
  id UUID,
  product_name String,
  source String,
  trend_score Float32,
  search_volume UInt32,
  social_mentions UInt32,
  detected_at DateTime DEFAULT now()
) ENGINE = MergeTree() ORDER BY detected_at;

-- One record per launch attempt/demo run
CREATE TABLE launch_runs (
  run_id UUID,
  temporal_workflow_id String,
  product_name String,
  slug String,
  status String,
  launch_score Float32,
  started_at DateTime DEFAULT now(),
  completed_at Nullable(DateTime),
  error Nullable(String)
) ENGINE = MergeTree() ORDER BY (started_at, run_id);

-- Timeline events shown in dashboard and correlated with Datadog traces
CREATE TABLE agent_events (
  run_id UUID,
  temporal_workflow_id Nullable(String),
  temporal_activity_name Nullable(String),
  business_id Nullable(UUID),
  agent_name String,
  event_type String,
  message String,
  payload String,
  timestamp DateTime DEFAULT now()
) ENGINE = MergeTree() ORDER BY (run_id, timestamp);

-- Edges that make the ClickHouse layer feel like a knowledge graph
CREATE TABLE business_relationships (
  from_business_id UUID,
  to_business_id UUID,
  relationship_type String,
  weight Float32,
  reason String,
  created_at DateTime DEFAULT now()
) ENGINE = MergeTree() ORDER BY (from_business_id, relationship_type);
```

---

## Work Packages (4 hours, 4 people)

---

### Dipesh — Agent Orchestration & Backend Core
**Time**: Full 4 hours  
**Deliverable**: Working FastAPI server that starts Temporal workflows, plus Google ADK/Gemini agent activities

#### Tasks:
1. **(Hour 1)** Set up FastAPI project structure, define agent interfaces, wire Google ADK + Gemini, wire Temporal client
   - `POST /api/launch-store` — creates a `run_id`, starts `LaunchStoreWorkflow`, returns immediately
   - `POST /api/demo/trigger` — deterministic demo path that creates a `run_id` and starts the same Temporal workflow
   - `GET /api/runs/{run_id}` — current status, launch score, store URL, errors
   - `GET /api/runs/{run_id}/events` — agent timeline for dashboard + Datadog correlation
   - `GET /api/stores` — list all active businesses from ClickHouse
   - `GET /api/agents/status` — Datadog-instrumented agent health
2. **(Hour 1-2)** Temporal workflow + worker — `LaunchStoreWorkflow` coordinates Research → Buyer → Legal → Advertising → Score → Store
3. **(Hour 2-3)** Research Activity — calls Nimble API, parses trend data, writes to ClickHouse `trend_signals`
4. **(Hour 2-3)** Buyer Activity — queries 2-3 supplier sources (AliExpress via scraping, or mock supplier API), picks winner using supplier confidence
5. **(Hour 3-4)** Launch scoring + Store Activity — calculates score, writes `businesses`, creates store config
6. **(Hour 4)** Add fallback fixtures — trend, margin, supplier confidence, compliance risk; cached Nimble/supplier/agent outputs for `DEMO_MODE=true`
7. **(Hour 4)** Wire Datadog traces — `ddtrace` decorators on each activity, custom metric for `agent.decisions` count, tags for `run_id`, `agent`, `product_slug`, and `temporal_workflow_id`

#### Key files:
```
backend/
  main.py              # FastAPI app
  workflows/
    launch_store.py    # Temporal workflow definition
    worker.py          # Temporal worker process for Render background worker
    activities.py      # Temporal activities that call agents/tools
  agents/
    orchestrator.py    # ADK/Gemini CEO agent
    research.py        # ADK/Gemini Research agent (Nimble integration)
    buyer.py           # ADK/Gemini Buyer agent (supplier sourcing)
  db/
    clickhouse.py      # ClickHouse client + insert helpers
  observability/
    datadog.py         # ddtrace setup, custom metrics
  fixtures/
    demo_trend.json    # Cached Nimble response for fallback/demo mode
    suppliers.json     # Deterministic supplier responses
  schemas.py           # Pydantic contracts for all agent outputs
```

#### Temporal SDK pattern:
```python
from temporalio import workflow

@workflow.defn
class LaunchStoreWorkflow:
    @workflow.run
    async def run(self, run_id: str, product_input: dict) -> dict:
        research = await workflow.execute_activity(
            "research_activity",
            {"run_id": run_id, "product_input": product_input},
            start_to_close_timeout=timedelta(seconds=60),
        )
        buyer = await workflow.execute_activity(
            "buyer_activity",
            {"run_id": run_id, "research": research},
            start_to_close_timeout=timedelta(seconds=60),
        )
        risk = await workflow.execute_activity(
            "legal_risk_activity",
            {"run_id": run_id, "research": research},
            start_to_close_timeout=timedelta(seconds=60),
        )
        advertising = await workflow.execute_activity(
            "advertising_activity",
            {"run_id": run_id, "research": research, "buyer": buyer},
            start_to_close_timeout=timedelta(seconds=60),
        )
        return await workflow.execute_activity(
            "create_store_activity",
            {
                "run_id": run_id,
                "research": research,
                "buyer": buyer,
                "risk": risk,
                "advertising": advertising,
            },
            start_to_close_timeout=timedelta(seconds=60),
        )
```

#### Google ADK pattern for agents:
```python
from google.adk.agents import Agent

research_agent = Agent(
    name="research_agent",
    model="gemini-flash-latest",
    instruction=(
        "You are a market research agent for ecommerce product launches. "
        "Return validated JSON with trend_score, competitor_summary, "
        "price_range, demand_summary, and confidence."
    ),
    tools=[],
)
```

#### Buyer agent supplier confidence output:
```json
{
  "supplier_name": "AliExpress Seller #4821",
  "unit_cost": 8.40,
  "shipping_days": 6,
  "rating": 4.7,
  "estimated_margin": 0.61,
  "risk_flags": [],
  "confidence_score": 0.84
}
```

#### Launch scoring:
```python
launch_score = (
    trend_score * 0.30
    + margin_score * 0.25
    + supplier_confidence * 0.25
    - compliance_risk * 0.20
)
```

---

### Safal — Full-Stack Store Template + Infra + Deployment
**Time**: Full 4 hours  
**Deliverable**: Live Next.js store + dashboard, Render deployment, Temporal worker connected

#### Tasks:
1. **(Hour 1)** Next.js store template — single product landing page with slots for: product name, description, price, hero image, CTA button. Tailwind CSS.
2. **(Hour 1-2)** Dashboard control room — Trigger Agent Run button, product input, real-time agent timeline, launch score panel, final store URL
   - Trigger calls `POST /api/demo/trigger` or `POST /api/launch-store`
   - UI receives `run_id`
   - UI polls `GET /api/runs/{run_id}` and `GET /api/runs/{run_id}/events` every 1-2 seconds
3. **(Hour 2)** `POST /api/stores/create` activity helper — accepts store config JSON, returns live URL
   - Strategy: Wildcard DNS `*.fastaisolution.com` pre-set in GoDaddy (one-time, manual); API call is supplemental for clean records
   - Next.js middleware reads `host` header → routes to correct store template by slug
4. **(Hour 2-3)** ClickHouse integration — Python client setup, schema creation script, insert/query helpers
5. **(Hour 3)** Data pipeline: Nimble webhook or polling → normalize trend data → start Temporal `LaunchStoreWorkflow`
6. **(Hour 4)** Deployment — Render for Next.js frontend, FastAPI backend, Temporal worker, and cron job. Confirm live URLs work.

#### Key files:
```
frontend/
  app/
    store/[id]/
      page.tsx         # Dynamic store page pulling config
    dashboard/
      page.tsx         # Internal admin view (trigger, timeline, launch score, stores)
  components/
    StoreTemplate.tsx  # The lockable storefront component
    AgentFeed.tsx      # Live agent activity stream
    AgentTimeline.tsx  # Visual Research -> Buyer -> Legal -> Advertising -> Store pipeline
    LaunchScore.tsx    # Score breakdown and launch/no-launch decision

backend/
  db/
    schema.sql         # ClickHouse DDL
    clickhouse.py      # clickhouse-connect client
```

#### Store config JSON shape:
```json
{
  "store_id": "uuid",
  "slug": "magneticmount",
  "store_url": "https://magneticmount.fastaisolution.com",
  "product_name": "Magnetic Phone Mount",
  "description": "AI-generated compelling description...",
  "price": 29.99,
  "hero_image_url": "...",
  "supplier": "AliExpress Seller #4821",
  "cta_text": "Buy Now — Ships in 3 days"
}
```

---

### Deepali — Agent Design, A2A Pipelines & Multimodal
**Time**: Full 4 hours  
**Deliverable**: Legal Agent + Advertising Agent + product image sourcing; Temporal activity contracts

#### Tasks:
1. **(Hour 1)** Design and document the activity input/output contracts — how Temporal activities pass validated JSON between agent steps
2. **(Hour 1-2)** Legal Agent — given product name and category, returns ecommerce risk flags, not formal legal advice: trademark risk, regulated product risk, import/shipping restrictions, and ad claim risk. Uses Gemini through ADK with a risk-screening prompt.
3. **(Hour 2-3)** Advertising Agent — generates product name, tagline, short ad copy, and hero image prompt using Gemini through ADK. Optionally call image generation for a product image.
4. **(Hour 3)** Integrate multimodal: pass product images (from Nimble scraping) into Gemini vision to extract product features and generate richer descriptions
5. **(Hour 4)** Wire Legal + Advertising into Temporal activities — ensure workflow routes Legal → Advertising in sequence after Research + Buyer

#### Temporal activity message schema:
```python
@dataclass
class ActivityMessage:
    run_id: str
    activity_name: str
    action: str        # "research_complete", "legal_risk_complete", etc.
    payload: dict
    timestamp: datetime
    business_id: str
```

#### Legal agent prompt pattern:
```python
LEGAL_SYSTEM = """You are a legal compliance agent for e-commerce.
Check ecommerce launch risk, not formal legal advice.
Flag: trademark conflicts, dropshipping restrictions, import regulations, regulated product risk, and risky ad claims.
Output JSON: {"cleared": bool, "risk_score": float, "flags": [...], "recommendation": "..."}"""
```

#### Advertising agent output:
```python
{
  "product_name": "MagSnap Pro — Magnetic Car Mount",
  "tagline": "Never fumble your phone again.",
  "ad_copy": "...",
  "hero_image_prompt": "product photo of sleek magnetic phone mount...",
  "hero_image_url": "..."  # from image generation API
}
```

---

### Ali — Analytics Layer, Knowledge Graph, Datadog Dashboards & Demo Prep
**Time**: Full 4 hours  
**Deliverable**: Bias mechanism, ClickHouse analytics queries, Datadog dashboards, demo script

#### Tasks:
1. **(Hour 1)** Bias mechanism algorithm — query ClickHouse for failed/paused businesses, compute `bias_score = (1 - success_rate) * recency_penalty * trend_delta`. High bias_score = surface for retry.
2. **(Hour 1-2)** ClickHouse analytics queries:
   - Top performing categories by margin
   - Agent decision latency by type
   - Trend signal to store launch time distribution
   - Knowledge graph: businesses linked by shared supplier/category
   - Temporal workflow run status by product/category
3. **(Hour 2-3)** Datadog dashboards:
   - Agent activity timeline (one row per agent, gantt-style)
   - Store health metrics (active stores, orders, revenue estimate)
   - API call trace viewer (Nimble, ClickHouse, Gemini/ADK latencies)
   - Temporal workflow/activity latency and retry panel
   - Bias surface panel (showing "near-misses being reconsidered")
4. **(Hour 3-4)** Demo prep:
   - Pre-warm ClickHouse with 5-10 synthetic past businesses (2 failed, 3 successful)
   - Write the 7-minute demo script with trigger points
   - Create a "demo trigger" button on the dashboard that fires the full pipeline with a pre-selected trending product
   - Rehearse and time the demo loop

#### Bias score query:
```sql
SELECT
  id,
  product_name,
  category,
  status,
  trend_score,
  dateDiff('hour', created_at, now()) AS age_hours,
  trend_score * 0.6
    + greatest(0, 1 - dateDiff('hour', created_at, now()) / 720.0) * 0.4
    AS bias_score
FROM businesses
WHERE status IN ('failed', 'paused')
ORDER BY bias_score DESC
LIMIT 10;
```

#### Datadog custom metrics to emit:
```python
from datadog import statsd

statsd.increment('agent.decisions', tags=['agent:research'])
statsd.histogram('agent.latency_ms', latency, tags=['agent:buyer'])
statsd.gauge('stores.active_count', count)
statsd.increment('trend.signals_detected', tags=['source:nimble'])
```

---

## Integration Milestones (Hourly Checkpoints)

| Time | Checkpoint | Owner(s) |
|------|-----------|---------|
| T+1h | FastAPI running locally, Temporal worker connected, ADK/Gemini agent returns valid JSON, ClickHouse schema created | Dipesh + Safal |
| T+2h | `POST /api/demo/trigger` starts Temporal workflow, Research activity pulls/caches Nimble data, Buyer activity returns a supplier, Next.js template renders from API | Dipesh + Safal |
| T+3h | Full pipeline: Nimble/demo trigger → FastAPI → Temporal → Research + Buyer + Legal + Advertising → Store URL live | All |
| T+3.5h | Datadog dashboards showing real data, bias mechanism returning results | Ali |
| T+4h | Demo rehearsed, pre-warmed state loaded, fallback mode ready | All |

---

## Fallback / Demo Safety

- **If live Nimble call fails**: Pre-cache a response JSON for "magnetic phone mount" — hardcoded trigger
- **If Gemini/ADK is slow**: Pre-generate agent outputs for the demo product, play them back with realistic delays
- **If Temporal Cloud is unavailable**: Use local Temporal dev server for the demo, or run `DEMO_MODE=true` with a synchronous fallback path that still writes run events
- **If a Temporal activity fails**: Let Temporal retry transient failures; after retries, use validated fallback JSON and mark the event as fallback in the run timeline
- **If store deployment fails**: Localhost with ngrok tunnel is acceptable for demo
- **If ClickHouse is down**: SQLite fallback for in-memory business node storage
- **Demo mode**: `DEMO_MODE=true` forces cached trend data, supplier data, agent outputs, and realistic delays
- **If deployment fails late**: Route the slug to a pre-rendered store config through the wildcard subdomain
- **Demo trigger**: Ali builds a `/demo/trigger` endpoint that starts the Temporal workflow with fixed inputs — judges see live agent activity even in controlled mode

---

## Partner Tool Visibility (Judge-Facing)

| Tool | Where Visible in Demo |
|------|----------------------|
| **Nimble** | "Watch as Nimble detects this trending product in real-time..." — show the raw trend signal data |
| **ClickHouse** | "Every business becomes a node in our knowledge graph — here's the ClickHouse query showing our bias mechanism surfacing a near-miss..." |
| **Datadog** | Screen-share the live Datadog dashboard during the demo — agent timeline, latency traces, store health |
| **Temporal** | Show the durable workflow run: activities, retries/fallbacks, and current run state for the same `run_id` |

---

## Verification / Demo Script

### Pre-demo checklist:
- [ ] **Wildcard DNS set in GoDaddy**: `*.fastaisolution.com → Render frontend target` (do this first, takes ~10 min to propagate)
- [ ] FastAPI server running on Render, `GODADDY_API_KEY` + `GODADDY_API_SECRET` in env if using optional DNS cleanup
- [ ] Next.js frontend deployed on Render with `fastaisolution.com` + `*.fastaisolution.com` routed to it
- [ ] Temporal Cloud namespace configured, or local Temporal dev server running for demo fallback
- [ ] Render Temporal worker is connected to the `launch-store` task queue
- [ ] Test: `ping testslug.fastaisolution.com` resolves before demo
- [ ] ClickHouse Cloud connected with 5-10 pre-seeded businesses
- [ ] Datadog dashboard open in second browser tab
- [ ] Nimble API key confirmed working
- [ ] Demo trigger endpoint tested end-to-end (< 60 seconds total)
- [ ] Pre-warmed store at `demo.fastaisolution.com` as hardcoded fallback
- [ ] `POST /api/demo/trigger` creates a `run_id` and starts a Temporal workflow
- [ ] Dashboard shows live agent event timeline for that `run_id`
- [ ] Launch score is visible before store creation
- [ ] Fallback mode tested with external APIs disabled
- [ ] At least one simulated order event appears after store launch

### 7-minute demo script:
1. **(0:00-0:45)** Open the dashboard — show the knowledge graph with existing businesses, point out 2 failed ones
2. **(0:45-1:30)** "Let's detect a new trend." — trigger Nimble scan, show the raw data coming in
3. **(1:30-3:00)** "Our workflow activates." — show Temporal/Datadog timeline lighting up: Research → Buyer → Legal → Advertising
4. **(3:00-4:00)** "The store is live." — navigate to `ergokeyboard.fastaisolution.com` in a browser (new tab, live URL), show the AI-generated content rendering on a real domain
5. **(4:00-5:00)** "It's already in the knowledge graph." — run the ClickHouse query live, show the new node
6. **(5:00-6:00)** "The bias mechanism surfaces a near-miss." — show the bias score query returning a failed category that's worth retrying, trigger a retry
7. **(6:00-7:00)** "This is how every store makes every future store smarter." — close on the ClickHouse knowledge graph growing, Datadog showing system health

---

## File Structure

```
Auto-Ecommerce/
  backend/
    main.py
    workflows/
      launch_store.py
      worker.py
      activities.py
    agents/
      orchestrator.py
      research.py
      buyer.py
      legal.py
      advertising.py
    db/
      clickhouse.py
      schema.sql
    observability/
      datadog.py
    requirements.txt
  frontend/
    app/
      store/[id]/page.tsx
      dashboard/page.tsx
    components/
      StoreTemplate.tsx
      AgentFeed.tsx
      KnowledgeGraph.tsx
    package.json
  scripts/
    seed_clickhouse.py
    demo_trigger.py
  .env.example
  docker-compose.yml
```
