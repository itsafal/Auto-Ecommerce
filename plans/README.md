# Plans

Chronological record of design plans for Auto-Ecommerce. Each numbered folder is one chapter of work. Plans are kept after shipping so we can trace *why* a system looks the way it does.

| # | Plan | Status | Summary |
|---|---|---|---|
| 01 | [Hackathon Foundation](./01-hackathon-foundation/PLAN.md) | shipped | The original hackathon plan + per-person work distribution (Ali, Deepali, Deepesh, Safal) and the integration guide that stitched their pieces together. |
| 02 | [Autonomous Batch + Businesses Portfolio](./02-autonomous-batch-businesses/PLAN.md) | shipped | Made batch deploy fully autonomous (no human-in-the-loop), added 7-day product dedup, added the `/businesses` portfolio tab with lifecycle (live/shutdown/archived) and synthetic metrics. Includes the `business_status` / `launched_at` / `shutdown_at` schema migration. |
| 03 | [Knowledge Graph of Businesses](./03-knowledge-graph/PLAN.md) | proposed | Self-hosted Postgres + pgvector layer that models businesses, suppliers, categories, trend signals, traffic sources as entities with typed edges and embeddings. Enables similarity search, portfolio intelligence, and (eventually) cross-business customer linkage. Built in 6 months alongside the existing ClickHouse event store. |
| 04 | [Slot Retry Strategy](./04-slot-retry-strategy/PLAN.md) | proposed | Amends plan 02. Changes per-slot retry policy from "5 distinct products, one shot each" to "2 attempts per product, swap product on failure, keep going until winner (cap 10 products)." Goal: every batch reliably lands 5 live businesses. |

## Conventions

- **One folder per plan**, numbered `NN-short-slug`. Multi-file plans (schema, ADRs, migration scripts) live inside the folder.
- **Status** in the table above: `proposed` (not started) → `in-progress` → `shipped` → `superseded` (link the replacement plan).
- **Don't edit shipped plans in place.** If reality diverged, add an "Outcome" section at the bottom rather than rewriting the body — the value of an old plan is partly that you can see what was *believed* at the time.
- **Per-person work splits** (like `01-hackathon-foundation/work-distribution/`) belong inside the plan folder, not at repo root.
