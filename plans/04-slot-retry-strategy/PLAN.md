# Slot Retry Strategy: "Fill the 5 Slots, No Matter What"

**Status:** proposed
**Owner:** Ali
**Amends:** [02-autonomous-batch-businesses](../02-autonomous-batch-businesses/PLAN.md) — specifically the per-slot retry semantics in `backend/api/runs.py::_run_batch_slot`

---

## Context

Plan 02 shipped autonomous batch deploy with a per-slot retry policy of **5 attempts, each on a different product**. If 5 products all score below threshold, the slot fails. In practice this means a batch can land 0–5 live businesses; nothing guarantees the operator sees 5 stores after clicking "Deploy."

This was a reasonable starting point but it doesn't match the actual product goal: **a batch should always deliver 5 live businesses.** Otherwise the dashboard shows a half-empty grid and the operator has to click Deploy again to fill the gaps.

The retry policy also wastes pipeline runs by burning a slot on 5 distinct products one-shot each, even though LLM scoring is noisy enough that a borderline product (0.58–0.64) often clears threshold on a second pass.

---

## Goal

Change the per-slot retry policy so every batch reliably ends with 5 live businesses (assuming the trending pool is deep enough). Concretely:

- **Per-product retries: 2.** If a product scores below threshold on attempt 1, re-run the full pipeline on the *same* product once more. LLM nondeterminism gives borderline products a fair second chance.
- **After 2 fails on the same product, swap to a fresh product.** Pull the next candidate from the queue (or top up the queue from `discover_new_trending_products` if empty).
- **The slot keeps going until it lands a winner.** No fixed cap on distinct products tried — but a safety cap of **10 distinct products per slot** to prevent a stuck slot from running indefinitely if the trending pool collapses.
- **Batch is "done" only when all 5 slots have either landed a live business or hit the safety cap.** The dashboard's progress indicator reflects this.

---

## Behavioral diff vs today

| Aspect | Today (plan 02) | After this plan |
|---|---|---|
| Retries per product | 0 (each attempt = new product) | **2 attempts on same product** before swapping |
| Max attempts per slot | 5 total | **20 total** (10 products × 2 attempts) — but most slots land in 1–3 attempts |
| When slot stops | After 5 distinct products | When it lands a winner OR hits 10-product safety cap |
| Expected approved/batch | 0–5 (uncertain) | **5/5** (assuming healthy trending pool) |
| Expected pipeline cost / batch | 5 × 5 = 25 max runs | typical ~10–15 runs; worst case 100 |
| Operator experience | "Some batches land 3, some land 5" | "Click once, get 5 live stores" |

---

## Design

### Retry loop (new shape)

```
slot_index = 0..4
products_tried = 0
max_distinct_products = 10  # safety cap

while products_tried < max_distinct_products:
    product = pull_next_candidate()      # from queue, or top up from Trend Scout
    if product is None:
        break  # truly exhausted, give up gracefully

    for attempt in 1..2:                  # per-product attempt budget
        run = execute_pipeline(product)
        if run.passed:
            mark_business_live(run)
            return                        # slot landed, we're done

    # both attempts on this product failed → discard, try a new one
    products_tried += 1

# safety cap hit
mark_slot_failed(reason="exhausted_after_10_products")
```

### Why 2 attempts per product (not 3 or 5)

Empirical: LLM scoring on the same input has roughly ±0.05 variance. A product that scored 0.61 with threshold 0.65 has maybe a 30% chance of clearing on the second attempt; a product that scored 0.40 has near-zero chance regardless. Two attempts captures most of the recoverable variance; a third has steeply diminishing returns and just burns API budget on doomed products.

### Why a 10-product safety cap (not unbounded)

If the dedup window has emptied the trending pool, or if Nimble SERP is rate-limited, or if Anthropic is returning low scores across the board (degraded model), a slot could otherwise loop forever consuming API quota. 10 is generous — at ~15 seconds per attempt, that's a worst-case ~5 minutes per slot, which still completes inside the dashboard's usability window.

### Replenishing the candidate queue

Plan 02 pre-populates the candidate queue once at batch start. With the new policy, a slot can burn through more candidates than that initial pool. Two fixes:

1. **Bigger initial pool.** Change `_build_candidate_queue` to size the pool as `count * 4` instead of `count * (max_attempts + 1)`. With count=5, that's a 20-product pool — enough headroom for typical retries.
2. **Lazy top-up.** When a slot tries to pull from the queue and it's empty, the slot calls `discover_new_trending_products(limit=5, exclude=already_tried)` on demand. The exclude set is the union of (dedup window products) ∪ (products already tried in this batch). This guarantees forward progress as long as Trend Scout can find anything fresh.

### Race condition: two slots pulling the same product

The current queue is `asyncio.Queue` — `get_nowait()` is atomic so no two slots ever pull the same item simultaneously. The lazy top-up needs an `asyncio.Lock` around the "is queue empty? top it up" critical section so two slots don't both kick off a Trend Scout discovery and both push duplicates.

---

## Settings changes

In `backend/settings.py`:

```python
# Remove (or keep as deprecated for backwards compat):
batch_max_attempts_per_slot: int = 5  # superseded by the two below

# Add:
attempts_per_product: int = 2          # LLM-noise retries on the same product
max_products_per_slot: int = 10        # safety cap; slot fails after this many distinct products
candidate_pool_multiplier: int = 4     # initial pool = count * this
```

Old `BATCH_MAX_ATTEMPTS_PER_SLOT` env var keeps working but is ignored — log a deprecation warning at startup if set.

---

## Frontend changes

`frontend/components/BatchPanel.tsx`:

- **Slot card "attempt" counter** today reads `attempt 3/5`. After this change it should read something like `try 2 · product 3` so the operator can see both the per-product retry and the product swap count. Same data, clearer labels.
- **Subtitle** today reads `5 stores · score ≥ 0.65 · no humans · dedup window 7d`. Update to `5 stores · score ≥ 0.65 · 2 retries/product · slot keeps trying`.
- **Rejected status pill** today appears on the final attempt when a slot exhausts. After this change, only show "rejected" when the safety cap is hit (rare). Borderline failed attempts on the way to a successful product should *not* show as rejected — they should just be invisible/replaced by the next attempt. Suggestion: show a small inline "(prev: Product A, score 0.61)" footnote on the current attempt for operator visibility.

---

## Backend changes (file-by-file)

| File | Change |
|---|---|
| `backend/api/runs.py::_run_batch_slot` | Rewrite the retry loop per the design above. Outer loop = products, inner loop = 2 attempts on same product. |
| `backend/api/runs.py::_build_candidate_queue` | Switch pool size from `count * (max_attempts + 1)` to `count * candidate_pool_multiplier`. |
| `backend/api/runs.py` (new helper) | `_top_up_queue(queue, exclude, lock)` — async-safe lazy top-up. Called by `_run_batch_slot` when `queue.get_nowait()` raises `QueueEmpty`. |
| `backend/api/runs.py::trigger_batch` | Pass the shared `asyncio.Lock` into each spawned slot task. |
| `backend/settings.py` | Add `attempts_per_product`, `max_products_per_slot`, `candidate_pool_multiplier`. Deprecate `batch_max_attempts_per_slot` with a startup warning. |
| `backend/schemas.py::LaunchRun` | Add `product_attempt: int | None = None` (1 or 2 — which try on the current product this run is). `attempt_index` keeps meaning "Nth overall run in this slot." |
| `backend/db/schema.sql` | `ALTER TABLE launch_runs ADD COLUMN IF NOT EXISTS product_attempt UInt8 DEFAULT 0;` (user-approved migration on prod CH). |
| `backend/store.py` | Thread `product_attempt` through `_mirror_run` and `_row_to_launch_run`. |

---

## Critical files

| File | Why critical |
|---|---|
| `backend/api/runs.py` | Entire retry semantics live here. The `_run_batch_slot` rewrite is the heart of this plan. |
| `backend/settings.py` | New config knobs that future-Ali will want to tune in `.env` without code changes. |
| `frontend/components/BatchPanel.tsx` | Without label updates the dashboard misrepresents what the slots are doing. |

---

## Patterns to reuse

- `backend/api/runs.py::_enrich_run_with_batch` — every new pipeline run still needs batch fields stamped on. The pattern doesn't change.
- `backend/workflows/activities.py::discover_new_trending_products(limit, exclude)` — already supports an exclude set. Use it as-is for the lazy top-up; just pass the union of dedup-window products + already-tried-in-this-batch products.
- `asyncio.Lock` — standard pattern; no need for the heavier `asyncio.Semaphore` or external coordination.

---

## Verification

1. **Happy path: trending pool is deep.** Trigger one batch. All 5 slots land within ~2 minutes. Dashboard shows 5/5 approved.
2. **Borderline products recover on attempt 2.** Mock the scorer to return `0.62` on attempt 1, `0.67` on attempt 2 (above the 0.65 threshold) for a specific product. Verify the slot lands on attempt 2 without swapping product. Check ClickHouse `agent_decisions`: two pipeline runs for the same `product_name`, second one passes.
3. **Hopeless product gets swapped.** Mock the scorer to return `0.30` on both attempts for a specific product. Verify the slot tries product A twice (both fail), then pulls product B and continues. ClickHouse shows 2 runs for A, then ≥1 run for B.
4. **Queue top-up triggers.** Set `candidate_pool_multiplier=2` and mock the scorer to fail the first 8 products. Verify a 9th product appears in the slot's run history (proving lazy top-up fired) without manual intervention. ClickHouse `trend_signals` shows new entries appended mid-batch.
5. **Safety cap kicks in.** Mock the scorer to return `0.30` for everything. Verify each slot tries exactly 10 distinct products (20 total attempts) then marks itself failed with `error="exhausted_after_10_products"`. Total time: ~5 minutes per slot, slots run in parallel so batch completes in ~5 minutes total.
6. **Race condition: two slots, empty queue.** Force both slots to hit the empty queue simultaneously. Verify only one `discover_new_trending_products` call fires (count via log line) and neither slot pulls a duplicate product.
7. **Backwards compat: old env var.** Set `BATCH_MAX_ATTEMPTS_PER_SLOT=10` in `.env`. App starts with a deprecation warning in the logs; the value is ignored; new behavior applies.
8. **Frontend labels match.** Click Deploy, watch the slot cards through 1+ retry. The card should show `try 2 · product 1` mid-retry, then `try 1 · product 2` after a swap. No "rejected" pill until the safety cap hits.

---

## Out of scope (deferred)

- **Auto-promote from backlog when an existing business is shut down.** That's the "always-on lifecycle loop" from plan 02's Phase E and belongs in its own plan (likely plan 05).
- **Budget cap per batch.** A `max_total_runs_per_batch` setting that caps total API spend per batch deploy, regardless of per-slot caps. Reasonable to add later; for now the per-slot safety cap is sufficient.
- **Tunable retry policy per category.** Some categories might warrant 3 attempts per product, some only 1. Wait for real data before adding this knob.

---

## Open questions to resolve before starting

1. **Should the "rejected" status pill ever appear in the new UI?** Argument for: hitting the 10-product safety cap is a real failure the operator should see. Argument against: a slot card that says "running" forever and then suddenly "rejected" is confusing. Recommend: yes show it, but only on safety-cap-failure, with a tooltip explaining why.
2. **Should the safety cap be per-slot or shared across the batch?** If slot 1 burns 10 products and slot 2 also burns 10, that's 100 attempts. Argument for shared cap (e.g. 25 distinct products total across the batch): bounds total cost. Argument against: a single bad slot could starve the good ones. Recommend: per-slot for now, revisit if costs become an issue.
3. **Do we want a "fast-fail" rule?** If a product scores below e.g. 0.40 on attempt 1, skip the retry entirely — the second attempt is almost certainly hopeless. Saves API budget. Recommend: yes, add a `fast_fail_threshold = 0.40` setting and skip attempt 2 if attempt 1 was below it.
