# Knowledge Graph of Businesses

**Status:** proposed
**Owner:** Ali
**Target window:** 6 months (Month 1 → Month 6, starting from when this plan is approved)
**Depends on:** [02-autonomous-batch-businesses](../02-autonomous-batch-businesses/PLAN.md) (shipped)

---

## Context

Plan 02 shipped the `/businesses` portfolio view: a flat table of launched stores with synthetic metrics. That's enough to *see* the portfolio but not to *reason about* it. The next chapter is to make the portfolio a queryable graph — so the autonomous loop can answer questions like:

- "Which businesses are most similar to this new trend candidate? If we already tried something close and it flopped, deprioritize."
- "Which suppliers have a >70% success rate across their products?"
- "Two of our stores share the same customer email — are they cannibalizing each other?"
- "This category has 5 live stores and a 60% shutdown rate — stop launching here."

Today none of this is answerable because ClickHouse is a flat event store. We need an entity-relationship layer beside it.

**Scale assumption for the next 6 months:** 10–100 live stores, single small team. Customer data lands when we start running real products (likely month 4–6, not before).

**Hosting decision (explicit):** self-hosted Postgres + pgvector. The user chose this over managed Supabase. The architecture is identical either way — only the ops surface differs.

---

## Goals (and non-goals)

**Goals**
1. Stand up a self-hosted Postgres + pgvector store separate from ClickHouse.
2. Model the entities and edges that already exist implicitly in our pipeline (businesses, suppliers, categories, trend signals, traffic sources).
3. Add embeddings on businesses so we can do semantic similarity searches.
4. Wire the Trend Scout and Buyer agents to read from the graph for dedup, supplier reputation, and "is this too similar to what we already have" checks.
5. Ship a Portfolio Intelligence page that shows the graph: clusters, supplier network, similarity neighbors, predicted outcomes.

**Non-goals (for this plan)**
- Replacing ClickHouse. CH stays for time-series events (`agent_events`, `agent_decisions`, `trend_signals`).
- A general-purpose graph database (Neo4j, Dgraph). Postgres edge tables are sufficient at our scale.
- Real customer data integration. The schema reserves space for `Customer`, but we don't populate it until real products ship.
- ML-trained similarity ranker. We start with hybrid scoring (embedding + categorical + price-band) and revisit when we have ≥50 stores' worth of outcome data.

---

## Architecture

```
                    ┌──────────────────────────┐
                    │     FastAPI backend       │
                    └──────────┬───────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       ┌──────────┐    ┌──────────────┐   ┌──────────┐
       │ClickHouse│    │  Postgres +  │   │  Nimble  │
       │  Cloud   │    │   pgvector   │   │   SERP   │
       │          │    │ (self-hosted)│   │          │
       │ events   │    │  entities    │   │  live    │
       │ decisions│    │  edges       │   │  data    │
       │ signals  │    │  embeddings  │   │          │
       └──────────┘    └──────────────┘   └──────────┘
            │                  ▲
            │ nightly mirror   │
            └──────────────────┘
```

**Separation of concerns:**
- ClickHouse = append-only event log. Fast for "what happened across the fleet in the last 24h" queries.
- Postgres = entities, relationships, embeddings. Fast for "what is this thing and what is it related to" queries.
- Nightly job mirrors aggregated outcomes from CH → PG so the graph stays in sync without coupling the write paths.

---

## Self-hosted deployment

Three reasonable shapes, ranked by ops burden:

| Shape | Where | Cost | Burden | When right |
|---|---|---|---|---|
| **PG in Docker, same box as backend** | One VPS (Hetzner CX22 €4.50/mo, Render Basic $7/mo) | low | lowest | 0 → 100 stores, single team |
| **Dedicated PG VPS** | Separate VPS, backend talks over private network | medium | medium | when 2nd service starts sharing the DB |
| **PG on Kubernetes** | k8s cluster + an operator (CloudNativePG, Zalando) | high | high | only if k8s already exists for other reasons |

**Default for us:** shape #1. Move to #2 around 200 stores.

### Day-one setup

Add to the existing `docker-compose.yml`:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    restart: unless-stopped
    environment:
      POSTGRES_USER: auto_ecommerce
      POSTGRES_PASSWORD_FILE: /run/secrets/pg_password
      POSTGRES_DB: kg
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./backups:/backups
    ports:
      - "127.0.0.1:5432:5432"  # bind localhost only
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U auto_ecommerce"]
      interval: 10s
    secrets:
      - pg_password

  pg_backup:
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
      - ./backups:/backups
    entrypoint: >
      sh -c "while true; do
        pg_dump -h postgres -U auto_ecommerce -F c kg > /backups/kg-$(date +%Y%m%d-%H%M).dump
        find /backups -name 'kg-*.dump' -mtime +14 -delete
        sleep 86400
      done"
    depends_on: [postgres]

volumes:
  pg_data:

secrets:
  pg_password:
    file: ./secrets/pg_password.txt
```

The `pgvector/pgvector:pg16` image ships pgvector pre-installed — no extension dance.

### Ops cadence (what you're signing up for)

| Cadence | Task | Time |
|---|---|---|
| Nightly (automated) | `pg_dump` → local volume → push to off-box storage (Backblaze B2 ~$0.005/GB) | 0 |
| Weekly | `df -h`, scan `docker logs postgres --tail=200` for warnings | 5 min |
| Monthly | Verify backup restores (`pg_restore` to a throwaway container) | 15 min |
| Quarterly | Apply minor PG patches, redeploy container | 1 hr |
| Yearly | Major PG version upgrade (`pg_upgrade`, tests) | half a day |
| Incidents | Disk full / OOM / restart needed — usually 1–3/yr at small scale | 1–2 hr each |

**Don't skip the monthly restore test.** A backup you've never restored isn't a backup.

**Set up day one:**
- Off-box backup destination (B2, R2, or Dropbox)
- Health check on `pg_isready` via UptimeRobot
- A half-page `docs/postgres-recovery.md` runbook

---

## Schema

### Entity tables

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

-- Business: one row per launched store. Mirrors launch_runs but only the
-- stable, identity-carrying fields. Mutable lifecycle (shutdown, metrics)
-- stays in ClickHouse + the launch_runs table.
CREATE TABLE business (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id          UUID NOT NULL UNIQUE,            -- foreign key into ClickHouse launch_runs
  slug            TEXT NOT NULL UNIQUE,
  product_name    TEXT NOT NULL,
  category_id     UUID REFERENCES category(id),
  supplier_id     UUID REFERENCES supplier(id),
  launched_at     TIMESTAMPTZ NOT NULL,
  launch_score    NUMERIC(4,3),
  price_band      TEXT,                            -- 'budget' | 'mid' | 'premium' | 'luxury'
  embedding       vector(1536),                    -- OpenAI text-embedding-3-small or equiv
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX business_embedding_idx ON business USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX business_category_idx  ON business (category_id);
CREATE INDEX business_supplier_idx  ON business (supplier_id);

-- Category: hierarchical (electronics > phone-accessories > mounts).
CREATE TABLE category (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  parent_id   UUID REFERENCES category(id),
  embedding   vector(1536),
  UNIQUE (name, parent_id)
);

-- Supplier: one row per upstream supplier. Reputation accumulates over time.
CREATE TABLE supplier (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                TEXT NOT NULL UNIQUE,
  external_ids        JSONB DEFAULT '{}'::jsonb,   -- aliexpress_id, alibaba_id, etc
  reputation_score    NUMERIC(4,3),                -- rolling success rate of their products
  total_products      INT DEFAULT 0,
  successful_products INT DEFAULT 0,
  first_seen_at       TIMESTAMPTZ DEFAULT now()
);

-- TrendSignal: candidate products discovered by Trend Scout. May or may not
-- become a business. Mirrored from ClickHouse trend_signals nightly.
CREATE TABLE trend_signal (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_name    TEXT NOT NULL,
  category_id     UUID REFERENCES category(id),
  source          TEXT NOT NULL,                   -- 'nimble_serp' | 'gemini' | 'fixture'
  trend_score     NUMERIC(4,3),
  detected_at     TIMESTAMPTZ NOT NULL,
  embedding       vector(1536),
  became_business UUID REFERENCES business(id)     -- nullable; set when promoted
);

CREATE INDEX trend_signal_embedding_idx ON trend_signal USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX trend_signal_name_idx ON trend_signal (lower(product_name));

-- TrafficSource: where visitors come from. Edges from business → traffic_source
-- carry the share %.
CREATE TABLE traffic_source (
  id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name    TEXT NOT NULL UNIQUE  -- 'google', 'tiktok', 'instagram', 'reddit', 'direct', 'email'
);

-- Customer: placeholder. Empty until real products ship.
CREATE TABLE customer (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email_hash    TEXT NOT NULL UNIQUE,    -- sha256(lower(email)) — never store plaintext
  first_seen_at TIMESTAMPTZ DEFAULT now()
);
```

### Edge table (single polymorphic table, typed by `relation`)

```sql
CREATE TABLE edge (
  id          BIGSERIAL PRIMARY KEY,
  src_type    TEXT NOT NULL,            -- 'business' | 'supplier' | 'category' | ...
  src_id      UUID NOT NULL,
  dst_type    TEXT NOT NULL,
  dst_id      UUID NOT NULL,
  relation    TEXT NOT NULL,            -- see registry below
  weight      NUMERIC(6,4),             -- for similarity/share edges; NULL otherwise
  props       JSONB DEFAULT '{}'::jsonb,
  created_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE (src_type, src_id, dst_type, dst_id, relation)
);

CREATE INDEX edge_src_idx ON edge (src_type, src_id, relation);
CREATE INDEX edge_dst_idx ON edge (dst_type, dst_id, relation);
```

### Edge type registry (start with 8)

| `relation` | Direction | Meaning | Weight semantic |
|---|---|---|---|
| `IN_CATEGORY` | business → category | This business sells a product in this category | n/a |
| `SOURCED_FROM` | business → supplier | This business buys from this supplier | n/a |
| `INSPIRED_BY` | business → trend_signal | This business was launched off this trend signal | n/a |
| `FORKED_FROM` | business → business | Variant of an earlier business (same supplier, tweaked positioning) | n/a |
| `SIMILAR_TO` | business → business | Computed similarity above threshold | cosine similarity score |
| `COMPETES_WITH` | business → business | Same category + overlapping traffic sources | overlap coefficient |
| `OUTPERFORMED_BY` | business → business | Same category, the other has materially better revenue/conversion | revenue ratio |
| `SHARES_CUSTOMER_WITH` | business → business | (future) Same `customer.id` has touched both | # of shared customers |

The polymorphic edge table looks ugly vs typed-per-relation tables, but at our scale Postgres handles it fine and adding a new edge type is one row in this registry rather than a schema migration.

---

## ClickHouse → Postgres mirror

A nightly cron in `backend/services/kg_mirror.py`:

1. **Read newly-launched businesses** from `launch_runs` where `launched_at > last_mirror_ts` AND `decision = 'launch'`. For each:
   - Upsert `business` row (compute `embedding` from `product_name + tagline + description` via OpenAI embeddings API or local `BAAI/bge-small-en` if we want zero LLM cost).
   - Resolve `category` (LLM classification with a fixed taxonomy + fuzzy match against existing categories).
   - Resolve `supplier` (exact match on supplier name, create if new).
   - Insert `IN_CATEGORY`, `SOURCED_FROM` edges.
2. **Read new trend signals** from `trend_signals`, upsert into PG `trend_signal`.
3. **Recompute `SIMILAR_TO` edges** for the new businesses: for each new business, find top-5 nearest neighbors by `embedding <-> embedding` cosine distance + categorical/price-band filter, write edges above threshold (e.g. cosine > 0.75).
4. **Update supplier reputation:** `reputation_score = successful_products / total_products` (a "successful" business is one that's been live ≥ 14 days without manual shutdown).
5. **Bump `last_mirror_ts`** in a small `mirror_state` table.

The mirror is intentionally one-way (CH → PG, never the reverse). PG is a derived view of the truth in CH.

---

## Agent integration

The graph only matters if the autonomous loop reads from it. Three concrete touch points:

### Trend Scout dedup (month 2)
Currently the dedup is a string match on `product_name` over the last 7 days. After the KG is live, the dedup widens to "semantically similar in any category":
- Embed the candidate product name.
- Query `SELECT * FROM business WHERE embedding <-> $1 < 0.25 LIMIT 1` (cosine distance).
- If a match exists AND it was launched in the last 30 days, skip the candidate.

This catches "Wireless Earbuds Pro" being a near-duplicate of "Bluetooth Earbuds Premium" — string match misses it; embedding catches it.

### Buyer agent supplier reputation (month 3)
When the Buyer picks a supplier, it currently picks based on the SERP result. Add: weight the choice by `supplier.reputation_score` from the KG. A supplier with 0.8 success rate across 5 prior products outranks an unknown supplier with one good SERP result.

### Score Launch competitor check (month 3)
Before approving a launch, query the KG for `COMPETES_WITH` candidates already in the portfolio. If we already have 3 live stores in this category with overlapping traffic sources, downweight the launch score — we'd be cannibalizing ourselves.

---

## Portfolio Intelligence page (month 4–5)

A new tab `/intelligence` next to `/dashboard` and `/businesses`. Three views:

1. **Similarity map** — 2D UMAP/t-SNE projection of all business embeddings, colored by category. Hover any node to see its 5 nearest neighbors as edges. Lets you spot clusters and gaps visually.
2. **Supplier network** — bipartite graph: suppliers on the left, businesses on the right, edges sized by `reputation_score`. Lets you see "this supplier carries 40% of our portfolio, what's our risk if they bail?"
3. **Category leaderboard** — table grouped by category: # live, # shutdown, hit rate, mean launch score, top supplier. The "should we keep launching in this category" view.

All three read directly from PG with no LLM calls — fast page loads.

---

## 6-month build order

| Month | Deliverable | Effort | Done when |
|---|---|---|---|
| **1** | Stand up self-hosted PG + pgvector in Docker Compose. Create schema. Write `backend/kg/` module (connection, basic CRUD). Manual one-time backfill of all existing `launch_runs` into `business` table with rule-based category/supplier resolution (no LLM yet). | ~1 week | `/api/kg/businesses` returns the same set as `/api/businesses` |
| **2** | Add `embedding` column. Write a backfill that embeds existing businesses + trend signals. Add `discover_new_trending_products` integration: dedup widens from string match to semantic match. | ~1 week | A candidate that's semantically near an existing business gets skipped automatically |
| **3** | Compute `SIMILAR_TO`, `IN_CATEGORY`, `SOURCED_FROM`, `COMPETES_WITH` edges in the nightly mirror. Wire Buyer to use `supplier.reputation_score`. Wire Score Launch to check `COMPETES_WITH`. | ~2 weeks | Two batches of launches: the second batch's agent_decisions log shows it considered the first batch's businesses in its scoring |
| **4** | Build the similarity map view of the Intelligence page (UMAP + nearest-neighbor edges). | ~1 week | Operator can visually inspect the portfolio's coverage |
| **5** | Supplier network view + Category leaderboard. Add `OUTPERFORMED_BY` edge once we have ≥10 businesses with ≥14 days of metrics. | ~1 week | Both views render with real graph data |
| **6** | `customer` entity + `SHARES_CUSTOMER_WITH` edge. Only if real products are live by then; otherwise defer to plan 04. | ~1 week | First cross-business customer linkage is detectable |

Total: ~7 weeks of focused work spread across 6 calendar months, leaving slack for the agent work that's happening in parallel.

---

## Critical files (when work begins)

| File | Phase | What it does |
|---|---|---|
| `docker-compose.yml` | Month 1 | Adds `postgres` and `pg_backup` services |
| `backend/kg/__init__.py` (new) | Month 1 | Module marker |
| `backend/kg/connection.py` (new) | Month 1 | `get_pg_pool()` — asyncpg pool, lazy init, settings-driven URL |
| `backend/kg/schema.sql` (new) | Month 1 | All `CREATE TABLE` / `CREATE INDEX` statements above |
| `backend/kg/entities.py` (new) | Month 1 | Pydantic models: `Business`, `Category`, `Supplier`, `TrendSignal`, `Edge` |
| `backend/kg/edges.py` (new) | Month 1 | Edge type registry as an `enum`; `insert_edge()`, `query_edges()` helpers |
| `backend/services/kg_mirror.py` (new) | Month 1 | Nightly CH → PG mirror job. Idempotent. Cron-triggered. |
| `backend/kg/embeddings.py` (new) | Month 2 | Wraps OpenAI embeddings API + a local-model fallback (`BAAI/bge-small-en` via `sentence-transformers`) |
| `backend/workflows/activities.py` | Month 2 | `discover_new_trending_products` switches its dedup from string match to semantic |
| `backend/api/kg.py` (new) | Month 4 | Endpoints for the Intelligence page: `GET /api/kg/similarity-map`, `GET /api/kg/supplier-network`, `GET /api/kg/category-leaderboard` |
| `frontend/app/intelligence/page.tsx` (new) | Month 4 | The three intelligence views |
| `frontend/components/AppNav.tsx` | Month 4 | Add `[INTELLIGENCE]` tab |
| `backend/settings.py` | Month 1 | `kg_database_url`, `embedding_provider`, `embedding_model`, `kg_mirror_interval_hours` |
| `docs/postgres-recovery.md` (new) | Month 1 | Half-page runbook: restore from `pg_dump` backup |

---

## Patterns to reuse

- `backend/store.py` — local-first → ClickHouse fallback pattern. The `backend/kg/` module should follow the same shape so tests can run without a real Postgres.
- `backend/workflows/activities.py::_llm_json` — use for the LLM-assisted category classifier in the mirror job. Don't reinvent JSON-mode prompting.
- `backend/api/businesses.py::_mock_metrics` — same deterministic-from-slug pattern for any synthetic graph data we need during dev (e.g. seed embeddings before the real model is wired).

---

## Verification (per phase)

**Month 1**: `docker compose up postgres` → `psql -h localhost -U auto_ecommerce kg -c '\dt'` lists all entity + edge tables. `pytest tests/kg/` passes against an ephemeral Postgres started by a fixture. `GET /api/kg/businesses` returns the same count as `GET /api/businesses`.

**Month 2**: Trigger two autonomous batches with similar product framings ("Magnetic Phone Mount" then "MagSafe Car Holder"). The second batch's research log explicitly skips the second product with reason `semantic_dedup_match` referencing the first business's UUID.

**Month 3**: After 2 batches, query `SELECT relation, count(*) FROM edge GROUP BY relation` — should show non-zero counts for `IN_CATEGORY`, `SOURCED_FROM`, `SIMILAR_TO`. Buyer's choice for the next batch references a supplier with `reputation_score > 0.5` over an unknown supplier with a higher SERP rank.

**Month 4–5**: Intelligence page loads in <500ms with ≥20 businesses in the graph. Similarity map clusters visually match category labels. Supplier network shows the actual fanout (no orphan suppliers, no impossible edges).

**Month 6**: First real customer shows up across two businesses → `SHARES_CUSTOMER_WITH` edge appears. Cross-portfolio "this customer bought from us before" notification surfaces in the storefront.

---

## Open questions to resolve before starting

1. **Embedding provider:** OpenAI `text-embedding-3-small` ($0.02 / 1M tokens, 1536 dims) vs local `BAAI/bge-small-en` (free, 384 dims, runs on CPU). Recommend OpenAI for month 2 — cheap at our scale, no GPU op surface. Revisit at month 6.
2. **Category taxonomy:** fixed list (Amazon's top-level ~30 categories) vs LLM-suggested with manual curation. Recommend fixed list at first — easier to reason about, easier to compare hit rates by category.
3. **`SIMILAR_TO` threshold:** start at cosine > 0.75 (loose), tighten after seeing real data.
4. **Backup destination:** Backblaze B2 vs Cloudflare R2 vs S3. Recommend B2 — cheapest egress, no per-request fees at our scale.
5. **Where does PG actually run?** Same box as backend (current Render service) or a dedicated VPS? Recommend same box at first; revisit when CPU contention shows up.

---

## What this plan deliberately does NOT do

- Build a generic graph traversal API. Every read path is a specific business question with a hand-tuned query.
- Replace ClickHouse. CH stays for events; PG is for entities.
- Pre-compute every possible edge. Edges are computed lazily by the nightly mirror, not on every write.
- Try to be schema-future-proof beyond the 8 edge types listed. New edges = new rows in the registry, not a redesign.

When this plan is done, the autonomous loop has memory and judgment about its own portfolio — not just the ability to launch.
