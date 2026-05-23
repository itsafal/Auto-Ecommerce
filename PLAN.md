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

Demo runtime: ~7 minutes. Everything is scripted to trigger live, with pre-warmed state as fallback.

---

## Architecture

```
[Nimble / Scrapling]
       |
       v
[Research Agent] --> [CEO Orchestrator Agent] --> [Buyer Agent]
                              |                        |
                      [Legal Agent]           [Supplier APIs]
                              |
                      [Advertising Agent]
                              |
                    [Next.js Store Template]
                              |
                       [FastAPI Backend]
                              |
                    [ClickHouse Cloud DB]
                              |
                    [Datadog Observability]
```

**Backend**: Python + FastAPI  
**Frontend**: Next.js (React) — single template, AI populates content; subdomain-routed  
**Agents**: Claude SDK (claude-opus-4-7 with adaptive thinking) + Gemini fallback  
**DB**: ClickHouse Cloud — columnar storage for business nodes, agent logs, performance metrics  
**Scraping**: Nimble API (primary trend detection) + Scrapling (supplemental)  
**Observability**: Datadog APM + custom dashboards  
**Domain**: `fastaisolution.com` via GoDaddy — each store gets `{product-slug}.fastaisolution.com`  

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
```

---

## Work Packages (4 hours, 4 people)

---

### Dipesh — Agent Orchestration & Backend Core
**Time**: Full 4 hours  
**Deliverable**: Working FastAPI server with CEO orchestrator + Research + Buyer agents

#### Tasks:
1. **(Hour 1)** Set up FastAPI project structure, define agent interfaces, wire Claude SDK
   - `POST /api/launch-store` — main endpoint that triggers the full loop
   - `GET /api/stores` — list all active businesses from ClickHouse
   - `GET /api/agents/status` — Datadog-instrumented agent health
2. **(Hour 1-2)** CEO Orchestrator agent — takes a product name, routes to sub-agents, assembles final store config
3. **(Hour 2-3)** Research Agent — calls Nimble API, parses trend data, writes to ClickHouse `trend_signals`
4. **(Hour 3-4)** Buyer Agent — queries 2-3 supplier sources (AliExpress via scraping, or mock supplier API), picks winner, writes to ClickHouse `businesses`
5. **(Hour 4)** Wire Datadog traces — `ddtrace` decorators on each agent call, custom metric for `agent.decisions` count

#### Key files:
```
backend/
  main.py              # FastAPI app
  agents/
    orchestrator.py    # CEO agent
    research.py        # Research agent (Nimble integration)
    buyer.py           # Buyer agent (supplier sourcing)
  db/
    clickhouse.py      # ClickHouse client + insert helpers
  observability/
    datadog.py         # ddtrace setup, custom metrics
```

#### Claude SDK pattern for agents:
```python
import anthropic
client = anthropic.Anthropic()

def run_research_agent(product_name: str) -> dict:
    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system="You are a market research agent...",
        messages=[{"role": "user", "content": f"Research: {product_name}"}]
    )
    return parse_research_output(response)
```

---

### Safal — Full-Stack Store Template + Infra + Deployment
**Time**: Full 4 hours  
**Deliverable**: Live Next.js store that spins up via API call; deployed and accessible by URL

#### Tasks:
1. **(Hour 1)** Next.js store template — single product landing page with slots for: product name, description, price, hero image, CTA button. Tailwind CSS.
2. **(Hour 1-2)** `POST /api/stores/create` endpoint — accepts store config JSON, calls GoDaddy API to provision `{slug}.fastaisolution.com`, returns live URL
   - Strategy: Wildcard DNS `*.fastaisolution.com` pre-set in GoDaddy (one-time, manual); API call is supplemental for clean records
   - Next.js middleware reads `host` header → routes to correct store template by slug
3. **(Hour 2-3)** ClickHouse integration — Python client setup, schema creation script, insert/query helpers
4. **(Hour 3)** Data pipeline: Nimble webhook or polling → normalize trend data → ClickHouse insert → trigger agent loop
5. **(Hour 4)** Deployment — Vercel for frontend, Railway/Render/Docker for FastAPI backend. Confirm live URLs work.

#### Key files:
```
frontend/
  app/
    store/[id]/
      page.tsx         # Dynamic store page pulling config
    dashboard/
      page.tsx         # Internal admin view (agent logs, stores)
  components/
    StoreTemplate.tsx  # The lockable storefront component
    AgentFeed.tsx      # Live agent activity stream

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
**Deliverable**: Legal Agent + Advertising Agent + product image sourcing; A2A message protocol

#### Tasks:
1. **(Hour 1)** Design and document the A2A message protocol — how agents communicate (input/output schemas for each agent type)
2. **(Hour 1-2)** Legal Agent — given product name and category, checks: is this dropshippable? any trademark issues? returns a compliance clearance or flag. Uses Claude with a legal reasoning prompt.
3. **(Hour 2-3)** Advertising Agent — generates product name, tagline, short ad copy, and hero image prompt using Claude. Optionally call DALL-E/Stability AI to generate a product image.
4. **(Hour 3)** Integrate multimodal: pass product images (from Nimble scraping) into Claude vision to extract product features and generate richer descriptions
5. **(Hour 4)** Wire all agents into the orchestrator's pipeline — ensure CEO agent correctly routes to Legal → Advertising in sequence after Research + Buyer

#### A2A message schema:
```python
@dataclass
class AgentMessage:
    from_agent: str
    to_agent: str
    action: str        # "research_complete", "legal_cleared", etc.
    payload: dict
    timestamp: datetime
    business_id: str
```

#### Legal agent prompt pattern:
```python
LEGAL_SYSTEM = """You are a legal compliance agent for e-commerce.
Check: trademark conflicts, dropshipping restrictions, import regulations.
Output JSON: {"cleared": bool, "flags": [...], "recommendation": "..."}"""
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
3. **(Hour 2-3)** Datadog dashboards:
   - Agent activity timeline (one row per agent, gantt-style)
   - Store health metrics (active stores, orders, revenue estimate)
   - API call trace viewer (Nimble, ClickHouse, Claude API latencies)
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
  (trend_score * 0.6 + (1 - toRelativeHourNum(created_at) / 720.0) * 0.4) AS bias_score
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
| T+1h | FastAPI running locally, Claude agent returns valid JSON, ClickHouse schema created | Dipesh + Safal |
| T+2h | Research agent pulls real Nimble data, Buyer agent returns a supplier, Next.js template renders from API | Dipesh + Safal |
| T+3h | Full pipeline: Nimble → CEO → Research + Buyer + Legal + Advertising → store URL live | All |
| T+3.5h | Datadog dashboards showing real data, bias mechanism returning results | Ali |
| T+4h | Demo rehearsed, pre-warmed state loaded, fallback mode ready | All |

---

## Fallback / Demo Safety

- **If live Nimble call fails**: Pre-cache a response JSON for "magnetic phone mount" — hardcoded trigger
- **If Claude is slow**: Pre-generate agent outputs for the demo product, play them back with realistic delays
- **If store deployment fails**: Localhost with ngrok tunnel is acceptable for demo
- **If ClickHouse is down**: SQLite fallback for in-memory business node storage
- **Demo trigger**: Ali builds a `/demo/trigger` endpoint that runs the whole pipeline with fixed inputs — judges see live agent activity even in controlled mode

---

## Partner Tool Visibility (Judge-Facing)

| Tool | Where Visible in Demo |
|------|----------------------|
| **Nimble** | "Watch as Nimble detects this trending product in real-time..." — show the raw trend signal data |
| **ClickHouse** | "Every business becomes a node in our knowledge graph — here's the ClickHouse query showing our bias mechanism surfacing a near-miss..." |
| **Datadog** | Screen-share the live Datadog dashboard during the demo — agent timeline, latency traces, store health |

---

## Verification / Demo Script

### Pre-demo checklist:
- [ ] **Wildcard DNS set in GoDaddy**: `*.fastaisolution.com → server/Vercel IP` (do this first, takes ~10 min to propagate)
- [ ] FastAPI server running (local or deployed), `GODADDY_API_KEY` + `GODADDY_API_SECRET` in env
- [ ] Next.js frontend deployed on Vercel with `fastaisolution.com` + `*.fastaisolution.com` added as domains
- [ ] Test: `ping testslug.fastaisolution.com` resolves before demo
- [ ] ClickHouse Cloud connected with 5-10 pre-seeded businesses
- [ ] Datadog dashboard open in second browser tab
- [ ] Nimble API key confirmed working
- [ ] Demo trigger endpoint tested end-to-end (< 60 seconds total)
- [ ] Pre-warmed store at `demo.fastaisolution.com` as hardcoded fallback

### 7-minute demo script:
1. **(0:00-0:45)** Open the dashboard — show the knowledge graph with existing businesses, point out 2 failed ones
2. **(0:45-1:30)** "Let's detect a new trend." — trigger Nimble scan, show the raw data coming in
3. **(1:30-3:00)** "Our CEO agent activates." — show Datadog agent timeline lighting up: Research → Buyer → Legal → Advertising
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
