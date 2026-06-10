# Auto‑Ecommerce

> **Autonomous AI agents that discover trending products, score the opportunity, and spin up live single‑product storefronts — end‑to‑end, with no human in the loop.**

Auto‑Ecommerce is a multi‑agent commerce platform. One click deploys a batch of 5 storefronts in parallel: a Trend Scout discovers fresh products, a Research agent grounds them in real Google SERP data via Nimble, a Buyer agent sources suppliers, a Legal/Risk agent checks compliance, an Advertising agent writes the copy, a Theme Designer picks the palette, and a Store Creator provisions the site. Each storefront only goes live if its launch score clears a configurable threshold; otherwise the slot autonomously retries with a different product. Already‑attempted products are skipped for a configurable window so the swarm always explores new ground.

```
┌─────────────────────────────────────────────────────────────────┐
│  Operator clicks "Deploy autonomous batch" (1 click, no inputs) │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
            ┌──────────────────────────────┐
            │   Trend Scout (LLM + Nimble) │
            │   ↓ dedup vs trend_signals   │
            └──────────────┬───────────────┘
                           ▼
        ┌──────────────────────────────────────┐
        │   5 slots run in parallel (asyncio)   │
        │                                       │
        │   Research → Buyer → Legal → Ad →    │
        │   Theme → Score → Store              │
        │                                       │
        │   score ≥ 0.55 → live URL            │
        │   score <  0.55 → retry new product  │
        └──────────────────┬────────────────────┘
                           ▼
        ┌──────────────────────────────────────┐
        │  ClickHouse (runs, events, decisions, │
        │  trend_signals, business lifecycle)   │
        └──────────────────────────────────────┘
```

---

## Highlights

- **Fully autonomous batch deploy.** No product picker, no threshold slider — one button, 5 slots in parallel, retries until each slot lands a store that clears the threshold or exhausts its attempts.
- **Real market grounding.** Research agent calls Nimble's SERP API for live Google organic + shopping data, extracts real product images and price ranges, and grounds the LLM prompt in actual SERP signal — not hallucinated numbers.
- **Per‑store dynamic theming.** A Theme Designer agent picks a palette + typography per product (`primary`, `accent`, `bg`, `surface`, `text`, `text_muted`, `border`, plus one of three font pairs). The storefront template applies tokens via CSS variables; a curated 10‑palette fallback keeps every store visually distinct even when the agent's choice isn't persisted.
- **Provider‑agnostic LLM.** Swap between **Claude (Anthropic)**, **Gemini (Google direct)**, and **Portkey** (NYU Vertex AI gateway) live from the dashboard. Caching plus a 60s in‑memory dedup on the trending endpoint keeps spend low.
- **ClickHouse‑backed shared state.** Every batch slot's run + events + agent decisions land in ClickHouse, so teammates see each other's runs without restart. Falls back to an in‑memory mirror for offline dev.
- **Subdomain‑routed storefronts.** Each launched store gets `http://<slug>.localhost:3000` (or `https://<slug>.fastaisolution.com` in prod). Next.js middleware rewrites subdomain requests to `/store/<slug>` server‑side.
- **Businesses portfolio dashboard.** Track live vs shut‑down stores, days online, views, revenue, top traffic sources, hit rate. Manual shutdown action; backlog panel surfaces the top non‑launched products ranked by trend score.
- **Operator‑console aesthetic.** Terminal‑style dark UI (`AUTO‑ECOMMERCE ● ONLINE`), monospace data fields, 5‑column run strip with score + latency, live event feed reading like a log file.

---

## Tech stack

| Layer | Tech |
|---|---|
| Backend | Python 3.11 · FastAPI · Pydantic v2 · `uv` for env management |
| Frontend | Next.js 15 (App Router) · React 19 · TypeScript · CSS Modules |
| Agents / LLM | Anthropic Claude SDK · Google Gemini API · Portkey gateway (Vertex AI) |
| Market data | Nimble SERP API (Google organic + shopping) |
| Storage | ClickHouse Cloud (write‑through) + in‑memory mirror |
| Orchestration (optional) | Temporal (open‑source SDK; pluggable) |
| Auth | PBKDF2‑hashed passwords · HMAC‑signed bearer tokens · `@fastaisolution.com` email domain gate |
| Observability | Datadog statsd + ddtrace (no‑ops without `DATADOG_API_KEY`) |
| Deploy | Render Blueprint (`render.yaml`) |

---

## Quick start

### Prerequisites

- Python 3.11+ (we test on 3.12)
- [`uv`](https://docs.astral.sh/uv/) for the backend
- Node.js 20+
- pnpm (`corepack enable && corepack prepare pnpm@11.2.2 --activate`)
- Optional: `just` (`brew install just`) — wraps the run/test commands

### 1. Configure

```bash
cp .env.example .env
```

Fill in at least the keys you have. None are required for a fixture‑mode boot, but the autonomous pipeline gets dramatically better with real keys:

```env
# Pick whichever LLM you want — set ONE provider key
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6
LLM_PROVIDER=auto                    # auto | anthropic | portkey | gemini

# Real market data (recommended; falls back to a curated fixture list otherwise)
NIMBLE_API_KEY=...

# Shared state across team / persistence (recommended)
USE_CLICKHOUSE=true
CLICKHOUSE_HOST=...us-west-2.aws.clickhouse.cloud
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=...
CLICKHOUSE_DATABASE=default

# Dashboard URL the frontend talks to
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Generate a strong auth secret:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
```

### 2. Install

```bash
uv sync                              # backend
cd frontend && pnpm install          # frontend
```

### 3. Run

The fastest path (if you have `just`):

```bash
just up                              # backend + frontend together; ctrl-C stops both
```

Or two terminals:

```bash
# Terminal 1 — backend (auto-loads .env)
uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — frontend
cd frontend
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 pnpm dev
```

### 4. Open

| URL | What |
|---|---|
| `http://127.0.0.1:3000/dashboard` | Operator dashboard · model picker · autonomous batch deploy |
| `http://127.0.0.1:3000/businesses` | Portfolio table · stat cards · backlog · shutdown action |
| `http://127.0.0.1:3000/signup` · `/login` | `@fastaisolution.com` account creation (domain‑gated) |
| `http://<slug>.localhost:3000` | Any deployed store · themed per product |
| `http://127.0.0.1:8000/docs` | Swagger UI for the API |

Click **▶ Deploy autonomous batch** on the dashboard. Watch 5 slots progress in parallel; click any approved URL to see its themed storefront.

---

## How the autonomous batch works

```python
# backend/api/runs.py
POST /api/batch/launch  {}      # no body needed; defaults from settings.py

# For each of N=5 slots, in parallel:
for attempt in 1..5:
    product = next from Trend Scout queue (filtered to skip recently-tried)
    run = LaunchRun(batch_id, slot, attempt)
    pipeline = research → buyer → legal_risk → advertising → theme_design → score_launch → create_store
    if score >= 0.55 and risk.cleared:
        business_status = 'live'
        return                  # slot done
    else:
        decision = 'reject'
        continue                # try a different product
```

**Configurable defaults** (`backend/settings.py`, env‑overridable):

| Setting | Default | Env var |
|---|---|---|
| `batch_target_count` | 5 | `BATCH_TARGET_COUNT` |
| `launch_score_threshold` | 0.55 | `LAUNCH_SCORE_THRESHOLD` |
| `batch_max_attempts_per_slot` | 5 | `BATCH_MAX_ATTEMPTS_PER_SLOT` |
| `dedup_window_days` | 7 | `DEDUP_WINDOW_DAYS` |
| `max_concurrent_live` | 5 | `MAX_CONCURRENT_LIVE` |

---

## LLM provider switching (live)

Pick the model from the dashboard's **AGENT MODEL** card. The next agent run (single or batch) uses the new provider — no restart.

Available providers:

| Provider | Models | When to pick |
|---|---|---|
| **Claude (Anthropic)** | `claude-haiku-4-5`, `claude-sonnet-4-6`, `claude-opus-4-7` | Best quality; Haiku for speed/cost, Opus for hardest reasoning |
| **Gemini (Google direct)** | `gemini-2.5-flash-lite`, `gemini-2.5-flash`, `gemini-2.5-pro` | Free tier available; Flash‑lite has 1000 req/day |
| **Portkey (NYU Vertex AI)** | `@vertexai/gemini-3.5-flash` | Requires NYU VPN |
| **Auto** | Portkey → Anthropic → Gemini | Tries each in order based on which keys are set |

Set defaults in `.env`:

```env
LLM_PROVIDER=anthropic               # or portkey | gemini | auto
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6
```

The current selection and which provider answered every run is recorded in the `agent_decisions` ClickHouse table for analytics.

---

## Key API endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/batch/launch` | Kick off an autonomous batch (returns `batch_id` immediately) |
| `GET` | `/api/batch/{batch_id}` | Poll batch progress; all slots + attempts |
| `POST` | `/api/demo/trigger` | Single‑product run (used by tests + curl) |
| `GET` | `/api/runs/{run_id}` · `/api/runs/{run_id}/events` | Per‑run detail + agent event feed |
| `GET` | `/api/stores` · `/api/stores/{slug}` | List + fetch a storefront's full config |
| `GET` | `/api/businesses` | Portfolio: live + shutdown + lifecycle metrics |
| `POST` | `/api/businesses/{slug}/shutdown` | Manual shutdown of a live business |
| `GET` | `/api/businesses/backlog` | Top‑scoring products not yet launched |
| `GET` · `POST` | `/api/admin/llm` | Inspect / swap the active LLM provider + model |
| `GET` | `/api/agents/trending-products` | Trend Scout cached output (60s TTL) |
| `POST` | `/api/auth/signup` · `/api/auth/login` | Account creation + JWT bearer issuance |

Full schema at `http://127.0.0.1:8000/docs`.

---

## Project layout

```
backend/
  api/                    # HTTP layer — runs, businesses, admin, auth
    runs.py               #   single + batch deploy; subdomain URL building
    businesses.py         #   portfolio table, shutdown, backlog
    admin.py              #   live LLM provider/model swap
  workflows/
    activities.py         #   the 7 agents + parallel pipeline orchestration
  integrations/
    nimble.py             #   Google SERP via Nimble (organic + shopping + thumbnails)
  services/
    lifecycle.py          #   future autonomous shutdown / promotion loop (stubs)
  db/
    clickhouse.py         #   real ClickHouse client (dual-write)
    memory_store.py       #   in-memory mirror (offline dev)
    schema.sql            #   businesses, launch_runs, agent_events, trend_signals…
  analytics/
    bias.py               #   re-attempt scoring for proven product categories
  observability/
    datadog.py            #   statsd + ddtrace (no-op without DATADOG_API_KEY)
  store.py                #   unified read/write surface bridging memory ↔ ClickHouse
  schemas.py              #   all Pydantic models — LaunchRun, StoreOutput, StoreTheme…
  settings.py             #   typed config; env-overridable defaults
  main.py                 #   FastAPI app factory + CORS

frontend/
  app/
    dashboard/            #   terminal-style operator console; live agent panels
    businesses/           #   portfolio table + summary + backlog + shutdown
    store/[slug]/         #   per-product themed storefront (subdomain-rewritten)
    login/ · signup/      #   @fastaisolution.com-gated auth
  components/
    BatchPanel.tsx        #   autonomous "deploy 5" + live slot grid
    AgentTimeline.tsx     #   horizontal 6-step pipeline status
    AgentFeed.tsx         #   monospace rolling event log
    LaunchScore.tsx       #   breakdown panel (trend, margin, supplier, risk)
    ModelPicker.tsx       #   live provider/model selector
    StoreTemplate.tsx     #   themable single-product storefront
    AppNav.tsx            #   [DASHBOARD] [BUSINESSES] terminal tabs
  middleware.ts           #   subdomain → /store/[slug] rewrite
  lib/api.ts              #   typed API client + mock-mode shims
```

---

## Testing

```bash
# Backend (41 tests)
USE_CLICKHOUSE=false uv run pytest tests -q

# Frontend (11 tests)
cd frontend && pnpm test

# Production frontend build
cd frontend && pnpm build
```

---

## ClickHouse schema notes

The schema is applied via `backend/db/schema.sql`. All migrations use `ADD COLUMN IF NOT EXISTS` so re‑applying is safe.

To apply on a fresh ClickHouse Cloud instance:

```bash
uv run python -c "from backend.db.clickhouse import ClickHouseClient; ClickHouseClient().ensure_schema()"
```

Core tables:

| Table | Rows |
|---|---|
| `launch_runs` | Every pipeline attempt; includes `batch_id`, `batch_slot`, `attempt_index`, lifecycle (`business_status`, `launched_at`, `shutdown_at`) |
| `agent_events` | Live timeline events (research started, buyer completed, etc.) |
| `agent_decisions` | Analytics‑grade log: per‑agent latency, input/output summary, `model_used` |
| `trend_signals` | One row per research call — the dedup source |
| `businesses` (derived) | Live + shutdown stores, projected from `launch_runs WHERE decision='launch'` |
| `users` | PBKDF2‑hashed accounts (email gated to `@fastaisolution.com`) |

---

## Deploy to Render

`render.yaml` defines two services: `auto-ecommerce-backend` (Python) and `auto-ecommerce-frontend` (Node). After Render creates the services, set the frontend env var:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR-BACKEND-SERVICE.onrender.com
```

(Render can't interpolate one service's URL into another's build‑time env, so this is a one‑time manual step.)

For a fixture‑mode demo on Render:

```env
USE_CLICKHOUSE=false
USE_TEMPORAL=false
USE_AGENT_FIXTURES=true
NEXT_PUBLIC_USE_MOCKS=false
REQUIRE_AUTH_FOR_RUNS=true
```

For real ClickHouse persistence, flip `USE_CLICKHOUSE=true` and fill in the `CLICKHOUSE_*` secrets in the Render dashboard. Don't commit secrets to `render.yaml` or `.env.example`.

---

## Optional: local Temporal

The default `asyncio.create_task` orchestration is fine for the hackathon demo. If you want durable workflows with retries, install the optional Temporal SDK:

```bash
uv sync --extra temporal
temporal server start-dev --ip 127.0.0.1 --port 7233    # in its own terminal
USE_TEMPORAL=true TEMPORAL_ADDRESS=127.0.0.1:7233 uv run python -m backend.workflows.worker
USE_TEMPORAL=true TEMPORAL_ADDRESS=127.0.0.1:7233 uv run uvicorn backend.main:app --reload
```

The workflow lives at `backend/workflows/launch_store.py` and the activities at `backend/workflows/activities.py`.

---

## Roadmap

The lifecycle/portfolio surfaces are in place; the autonomous loop that consumes them is the next chapter.

- [ ] **Cron‑driven autonomous loop.** Every 15 min: shut down underperforming live businesses (low conversion + days_live > grace_window), promote top backlog item when under the `max_concurrent_live` cap, top up backlog via Trend Scout when it's running low.
- [ ] **Real analytics.** Replace the deterministic synthetic metrics on the Businesses tab (`views_24h`, `revenue_24h`, `top_sources`) with a server‑side counter on storefront load, or wire in Plausible / Umami / Datadog RUM.
- [ ] **Re‑attempt promoted products.** Currently dedup is absolute for 7 days. Allow re‑attempt when a product later shows materially higher `trend_score` (the bias mechanism in `backend/analytics/bias.py` is wired but not exposed yet).
- [ ] **Wildcard DNS + TLS for fastaisolution.com.** Today stores live at `http://<slug>.localhost:3000`. The middleware already handles `*.fastaisolution.com`; only the DNS + cert is missing.
- [ ] **Customer service agent + payment integration.** The pipeline ends at "store live". The original vision adds a CS agent (auto‑reply, refund handling) and a real payment integration so the synthetic revenue becomes real.

---

## Contributing

- Don't commit `.env` or any API keys. `.env.example` ships with placeholders; the gitignore catches the rest.
- Run both test suites before pushing.
- Schema changes go in `backend/db/schema.sql` as `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` so they're idempotent.

---

## License

Hackathon project — no license attached yet.
