# Autonomous Batch + Businesses Portfolio

## Context

The previous plan's four phases (bug fixes, dynamic theming, terminal dashboard, manual batch deploy) are shipped. This is the next chapter.

Three things to address now:

1. **Batch Deploy is not really autonomous.** It still asks the user for count + threshold, and — worse — its candidate queue is a fixed list, so when Trend Scout falls back to fixture all 5 slots end up attempting the same product ("Magnetic Phone Mount") and all get rejected with the same 0.615 score. The user wants this to be **fully autonomous**: one click, system discovers trending products on its own, tries each, deploys the ones that clear the score threshold. No human in the loop.

2. **Same products keep getting tried.** Each run already writes a `trend_signals` row (product_name, source, trend_score, detected_at) — so we already have the data; we just don't filter by it. The system should refuse to re-try a product it has recently attempted (within a configurable window). If a product later genuinely scores higher under different market conditions it can become eligible again, but for now: every batch slot prefers new ground.

3. **No portfolio view.** Once a store goes live, the operator has no place to see *which* businesses are running, how they're performing, which ones have been shut down. The user wants a Businesses tab with real lifecycle data (launched_at, days online, score) and revenue-style oversight metrics (views, revenue, top traffic sources). Real analytics aren't wired yet — we'll display deterministic mocked numbers per business so the UI looks rich and consistent across reloads, with clear labels marking them as "estimated/synthetic" until a real analytics pipeline lands.

**Also resolved along the way**: the dashboard header keeps showing `https://magneticmount.fastaisolution.com` even on a clean process because `frontend/lib/mock-data.ts::mockRun.store_url` hardcodes the prod domain. Real batches already produce correct `http://<slug>.localhost:3000` URLs because `build_store_url` already honors `BASE_DOMAIN=localhost:3000` and the Next.js subdomain middleware already rewrites localhost subdomains to `/store/[slug]`. Fix: stop showing fake mock URLs in the dashboard when no real run has populated state yet.

**Future direction this plan deliberately stages toward** (not in scope for this PR): an always-on autonomous loop that keeps the portfolio at a max-concurrent cap (e.g. 5 live stores), maintains a pre-scored backlog, and auto-shuts down underperforming stores after a grace window. This PR ships the data model and surfaces (status, backlog, manual shutdown) that the loop will plug into later.

---

## Phase A — Fully autonomous Batch Deploy

### Backend
- `backend/api/runs.py::trigger_batch`: when the request body omits `products` (which it will, in the new UI), build the candidate queue purely from Trend Scout + the dedup filter (Phase B). Continue accepting explicit `products` for testing/curl. `count` and `threshold` defaults already come from `backend.settings.get_settings()` — no change needed there.
- `backend/workflows/activities.py`: extract a new helper `discover_new_trending_products(limit, exclude=set())` that wraps the existing `discover_trending_products` and filters out names in `exclude`. The exclude set comes from the dedup query in Phase B.
- `_build_candidate_queue` in `backend/api/runs.py`: replace its current "ask Trend Scout for `count * (max_attempts+1)`" logic with "ask `discover_new_trending_products` for the same volume, passing the recently-tried product set as `exclude`". If Trend Scout returns too few new products, ask the LLM directly for more (via the existing `_llm_json` helper with a "give me N fresh dropshipping ideas, avoiding this list" prompt).

### Frontend
- `frontend/components/BatchPanel.tsx`: remove the **COUNT** input and **THRESHOLD** slider entirely. The card becomes a single "▶ DEPLOY AUTONOMOUS BATCH" button plus a one-line subtitle that reports the active defaults read from `/api/admin/llm` or a new `/api/admin/batch-config` echo. Card header stays; slot grid stays.
- Add a tiny "Last batch" pill in the header that links to `/api/batch/{id}` so the operator can re-poll if they tab away.

---

## Phase B — Product attempt dedup (no product twice, for now)

### Backend
- `backend/store.py::InMemoryRunStore`: new method `recently_tried_products(within: timedelta) -> set[str]`. Reads from `trend_signals`:
  - In-memory: walks `self._trend_signals` filtering by `detected_at`.
  - ClickHouse fallback: `SELECT DISTINCT product_name FROM trend_signals WHERE detected_at > now() - INTERVAL <N> SECOND`.
  - Returns a normalized set (lowercased, stripped) for case-insensitive matching.
- `backend/settings.py`: new env-overridable `dedup_window_days: int = 7`. The dedup query uses this window.
- Plumb `recently_tried_products()` into the new `discover_new_trending_products` helper from Phase A.
- Keep the door open for the "allow re-try if it later scores higher" rule: leave a TODO comment + a stub field on the helper signature, but don't implement it now.

### Verification
After running two batches back-to-back, neither batch's slots should retry a product from the first batch's attempts until 7 days pass (or until `DEDUP_WINDOW_DAYS=0` is set). Confirm via the live ClickHouse `agent_decisions` log — every slot's `research` step should reference a different `product_name` than the prior batch.

---

## Phase C — Localhost URLs everywhere

### Frontend
- `frontend/lib/mock-data.ts`: change `mockRun.store_url` and `mockStore.store_url` from `https://magneticmount.fastaisolution.com` to `http://magneticmount.localhost:3000`. The current values mislead the user into thinking the system is configured for prod.
- `frontend/app/dashboard/page.tsx`: tighten the header storeLink fallback so when there's no real run yet, it shows `store: pending` (the existing fallback path) rather than the mockRun URL. Specifically, gate `visibleRun.store_url` on `runId !== null` so the mock URL is never shown to the operator in the header bar.
- `frontend/app/dashboard/page.tsx::FINAL STORE URL` section in the secondary column: same gate — show "no store yet" when `runId === null`.

### Backend
- No backend change needed. `build_store_url` already handles localhost correctly (the Explore confirmed it returns `http://magneticmount.localhost:3000` with `BASE_DOMAIN=localhost:3000`). Subdomain middleware in `frontend/middleware.ts` already rewrites those to `/store/[slug]`.

---

## Phase D — Businesses portfolio tab

A new top-level route `/businesses` with a portfolio table, summary stats, and a backlog panel.

### Data model (lifecycle additions on `launch_runs`)

We don't need a new table — every "business" is already a successfully-launched run. We add four columns to `launch_runs` so the lifecycle can be observed and mutated.

- `backend/db/schema.sql` + ClickHouse Cloud (user-approved ALTER):
  ```sql
  ALTER TABLE launch_runs ADD COLUMN IF NOT EXISTS business_status LowCardinality(String) DEFAULT '';   -- '' | 'live' | 'shutdown' | 'archived'
  ALTER TABLE launch_runs ADD COLUMN IF NOT EXISTS launched_at Nullable(DateTime);
  ALTER TABLE launch_runs ADD COLUMN IF NOT EXISTS shutdown_at Nullable(DateTime);
  ALTER TABLE launch_runs ADD COLUMN IF NOT EXISTS shutdown_reason String DEFAULT '';
  ```
- `backend/schemas.py::LaunchRun`: add `business_status: str | None = None`, `launched_at: datetime | None = None`, `shutdown_at: datetime | None = None`, `shutdown_reason: str = ""`.
- `backend/store.py::InMemoryRunStore._mirror_run` + `_row_to_launch_run`: thread the new fields through writes and reads.
- When a slot's pipeline completes with `decision == launch` and `score >= threshold`, set `business_status='live'` and `launched_at=now()`. Done inside `_run_batch_slot`.

### Mocked oversight metrics (deterministic per business)

Real analytics aren't wired. To keep the dashboard rich without lying about the source of the data, expose **deterministic mocked metrics** computed from a hash of the business slug. Same slug → same numbers across reloads, so judges see consistent data.

- `backend/api/businesses.py` (new module): helper `_mock_metrics(slug)` that returns:
  - `views_total: int`  (e.g. `300 + hash(slug + 'views') % 12000`)
  - `views_24h: int`     (e.g. `30 + hash(slug + 'v24') % 800`)
  - `revenue_total: float`  (e.g. `25.0 + hash(slug + 'rev') % 3800`)
  - `revenue_24h: float`
  - `conversion_rate: float`  (0.5% – 4.5%)
  - `bounce_rate: float`      (15% – 70%)
  - `top_sources: list[{source, share}]` — top 3 from a fixed pool (`google`, `tiktok`, `instagram`, `reddit`, `direct`, `email`)
- All responses include a top-level `"data_source": "synthetic"` flag and the UI prints "⚠ synthetic metrics" in small text on the page.

### Endpoints

- `GET /api/businesses` — returns `{businesses: [Business], summary: {...}}`. A `Business` is one launched run with computed `days_live` and the mocked metrics merged in. Sorted by `launched_at DESC` by default; query params `?status=live|shutdown` and `?sort=score|revenue|views|days_live`.
- `POST /api/businesses/{slug}/shutdown` — sets `business_status='shutdown'`, `shutdown_at=now()`, `shutdown_reason="manual"`. Returns the updated business row.
- `GET /api/businesses/backlog` — returns top 10 distinct products from `trend_signals` ordered by `trend_score DESC` that have **never** appeared in a launched (`decision='launch'`) run. This is the future auto-launch queue surface.

### Frontend

- New route `frontend/app/businesses/page.tsx` — a client component matching the terminal aesthetic of the dashboard. Sections:
  1. **Summary stat cards** (top row, monospaced numerics):
     - `LIVE BUSINESSES` count
     - `TOTAL REVENUE` (synthetic)
     - `TOTAL VIEWS 24H` (synthetic)
     - `HIT RATE` — % of all batch attempts that cleared the threshold (computed from `launch_runs`)
     - `AVG TIME TO LAUNCH` — mean of `completed_at - started_at` over the last 20 launches
     - `BEST CATEGORY` — category with the highest mean launch_score across launched runs
  2. **Businesses table** — rows for each business:
     ```
     STATUS  PRODUCT             LAUNCHED   SCORE  DAYS  VIEWS24  REV24  TOP SRC  ATTEMPTS  ACTIONS
     ● live  Magnetic Phone …    2026-05-23  0.72  1     312      $48    google   1/5       [shutdown] [open ↗]
     ○ off   Posture Back Br…    2026-05-21  0.68  -     —        —      —        3/5       [archive]  [open ↗]
     ```
     Status pills reuse Phase 3's accent/danger/muted color tokens. URLs open the localhost subdomain. Sort by header click.
  3. **Backlog panel** (lower-left) — top 5 products with high trend_scores not yet launched, ordered by score. Each row shows product name + category + score + source. Future: "Promote" button to push to the next available slot.
  4. **Recent decisions feed** (lower-right) — rolling log over the last 12h: launches, rejects, shutdowns. Reads from `agent_events` + the new shutdown timestamps.

- Shared `frontend/components/AppNav.tsx`: a thin terminal-styled top nav with `[ DASHBOARD ]  [ BUSINESSES ]` tabs. Mounted at the top of `app/dashboard/page.tsx` and `app/businesses/page.tsx`. (Login/signup remain navless.)

- `frontend/lib/api.ts`: add `getBusinesses(params?)`, `shutdownBusiness(slug)`, `getBacklog()`. Mirror the patterns used by `triggerBatch`/`getBatch`. Use mock-mode shims for tests.

### Creative additions worth shipping

These are small additions that make the portfolio dashboard feel like a real ops surface without much new code:

- **Per-batch lineage**: each business shows `batch_id` and `attempt #/N` so the operator can trace "this is slot 3 from batch X, attempt 2".
- **Model used**: pull `model_used` from the latest `agent_decisions` row for this run, show it as a small chip next to the product name. Judges immediately see which Claude/Gemini model produced which store.
- **Latency breakdown**: small bar mini-viz showing the 6 agent latencies for this business. Reuses the data already in `agent_decisions`.
- **Cost estimate** (synthetic): `est_cost = sum(latency_ms) * model_rate` per business; surfaces "how much LLM spend per business" as an ops metric.

---

## Phase E — Lifecycle scaffolding (foundation only)

The full always-on loop (cron-driven research, auto-shutdown rules, auto-promote from backlog) is **not** in this PR. What we ship here is the surface the loop will hook into:

- `business_status` column + `live | shutdown | archived` states (Phase D infra).
- Manual `POST /api/businesses/{slug}/shutdown` (Phase D).
- `GET /api/businesses/backlog` (Phase D).
- A `backend/settings.py` setting `max_concurrent_live: int = 5` — read but not enforced yet. Surfaced in the Businesses page header as `5/5 SLOTS` / `3/5 SLOTS` so the cap is visible.
- A skeleton `backend/services/lifecycle.py` (empty stubs `def evaluate_shutdown_candidates()` and `def promote_top_of_backlog()`) wired to nothing, with docstrings describing what they'll do when the cron arrives. This keeps the intent visible without committing to behavior.

The reasoning: shipping the data model + manual controls first lets the operator (you) interact with the lifecycle as a human, while the autonomous loop is being designed.

---

## Critical files

| File | Phase | What changes |
|---|---|---|
| `backend/api/runs.py` | A, B | `trigger_batch` reads defaults from settings; `_build_candidate_queue` uses dedup-filtered Trend Scout pool |
| `backend/workflows/activities.py` | A, B | New `discover_new_trending_products(limit, exclude)` helper that wraps existing `discover_trending_products` |
| `backend/store.py` | B, D | New `recently_tried_products(within)` method; thread new `business_status`/`launched_at`/`shutdown_at` through `_mirror_run` + `_row_to_launch_run` |
| `backend/db/schema.sql` | D | Add nullable lifecycle columns to `launch_runs` (`business_status`, `launched_at`, `shutdown_at`, `shutdown_reason`) with idempotent `ALTER TABLE ADD COLUMN IF NOT EXISTS` migrations |
| `backend/schemas.py` | D | Extend `LaunchRun` with lifecycle fields; add `Business`, `BusinessSummary`, `BacklogItem` models |
| `backend/api/businesses.py` (new) | D | `GET /api/businesses`, `POST /api/businesses/{slug}/shutdown`, `GET /api/businesses/backlog`, `_mock_metrics` |
| `backend/main.py` | D | Register the new businesses router |
| `backend/settings.py` | B, E | `dedup_window_days: int = 7`, `max_concurrent_live: int = 5` |
| `backend/services/lifecycle.py` (new) | E | Skeleton stubs documenting the future loop |
| `frontend/components/BatchPanel.tsx` | A, C | Strip count/threshold inputs; single "DEPLOY AUTONOMOUS BATCH" button |
| `frontend/components/AppNav.tsx` + module CSS (new) | D | Shared `[DASHBOARD] [BUSINESSES]` nav |
| `frontend/app/dashboard/page.tsx` | C, D | Gate mock URLs; mount `AppNav` |
| `frontend/app/businesses/page.tsx` + module CSS (new) | D | Portfolio table, stat cards, backlog, recent decisions |
| `frontend/lib/api.ts` | D | `getBusinesses`, `shutdownBusiness`, `getBacklog`; mock shims |
| `frontend/lib/mock-data.ts` | C | Change `mockRun.store_url` + `mockStore.store_url` to `http://magneticmount.localhost:3000` |

## Patterns to reuse (don't reinvent)

- `backend/workflows/activities.py::_timed_decision` — wrap any new agent calls (none in this PR, but the lifecycle stubs should follow it).
- `backend/store.py::run_store.list_runs_by_batch` — the same pattern (local-first → ClickHouse fallback) for the new `list_businesses()` and `recently_tried_products()` methods.
- `backend/api/runs.py::_run_batch_slot` — `_enrich_run_with_batch` already stamps batch metadata onto the final LaunchRun; add `business_status='live'` + `launched_at=now()` in the same place when the slot passes the threshold.
- `frontend/components/ModelPicker.tsx` + `BatchPanel.tsx` — the visual + interaction pattern for the new BusinessesTable, BacklogPanel, and any in-dashboard action buttons.
- `frontend/middleware.ts::extractSubdomainSlug` — already handles localhost subdomains; nothing to change for the URL fix.

## Verification

Run all of these before merging:

**Phase A** (autonomous batch)
- Click "DEPLOY AUTONOMOUS BATCH" on the dashboard with no inputs. Watch all 5 slots progress in parallel with **distinct** product names. None should be "Magnetic Phone Mount" five times.
- `curl -X POST http://127.0.0.1:8000/api/batch/launch -H "Content-Type: application/json" -d '{}'` returns a `batch_id` + 5 distinct slot product names.
- Backend tests: `USE_CLICKHOUSE=false uv run pytest tests -q` — should be ≥41 pass.

**Phase B** (dedup)
- Trigger batch #1, wait for completion, trigger batch #2. Inspect ClickHouse: `SELECT product_name, count() FROM trend_signals WHERE detected_at > now() - INTERVAL 1 HOUR GROUP BY product_name ORDER BY count() DESC` — every product name should appear exactly once across the two batches.
- Set `DEDUP_WINDOW_DAYS=0` in `.env`, restart, trigger two more batches: the dedup is off and repeats are now allowed.

**Phase C** (localhost URLs)
- Hard-refresh the dashboard on a fresh process (no runs in memory). The header should show `store: pending` — **not** `magneticmount.fastaisolution.com`. The FINAL STORE URL section should show "no store yet".
- Trigger a single run. Once `runId` is set, header + final URL section show the real `http://<slug>.localhost:3000` URL. Click it — Next.js middleware rewrites to `/store/<slug>` and the storefront renders.
- `pnpm --dir frontend test` — 11 frontend tests still pass.

**Phase D** (Businesses tab)
- Apply the `ALTER TABLE launch_runs ADD COLUMN IF NOT EXISTS ...` migrations (user-approved, same pattern as the earlier batch_id migration).
- Run one autonomous batch. Open `/businesses`. The 1–5 launched stores appear in the table. Click "shutdown" on one — row's status transitions to `shutdown`, the live count in the summary drops by 1.
- Stat cards show non-zero values. Backlog panel shows ≥1 product that scored well but wasn't launched (i.e. a rejected slot's research). Click a store URL — opens the themed storefront from Phase 2.
- `curl http://127.0.0.1:8000/api/businesses` returns the expected JSON shape with `data_source: "synthetic"` flag and both real lifecycle fields + mocked metric fields.

**Phase E** (lifecycle scaffolding)
- `backend/services/lifecycle.py` exists with documented stubs; nothing actually runs. No test required; this is design surface for the next PR.

End-to-end demo readiness: with `LLM_PROVIDER=anthropic`, `USE_AGENT_FIXTURES=false`, NIMBLE + Anthropic keys set — one click on the dashboard discovers 5+ trending products, runs 5 pipelines in parallel, lands 3–5 unique live stores at `http://<slug>.localhost:3000`. Navigate to `/businesses` to see the portfolio, click any URL to see the themed storefront, click "shutdown" on one to see the lifecycle transition. Total elapsed: under 3 minutes for the demo loop.
