---
name: nimble-trend-integration
description: Use when integrating Nimble into Auto-Ecommerce for trend detection, product signal fetching, competitor scraping, cached demo fixtures, normalized trend signals, launch triggers, and fallback behavior when live scraping or external APIs are unavailable.
---

# Nimble Trend Integration

Use Nimble as the primary trend signal source, with cached fixtures for demo reliability.

## Workflow

1. Fetch or receive a trend signal.
2. Normalize it into a `TrendSignal` Pydantic model.
3. Store the raw and normalized signal in ClickHouse.
4. Trigger a Temporal launch workflow when the signal passes minimum thresholds.
5. In demo mode, load cached Nimble fixture data and emit a fallback event.

## Signal Fields

Track:

- `product_name`
- `source`
- `trend_score`
- `search_volume`
- `social_mentions`
- `competitor_count`
- `sample_urls`
- `detected_at`

## Rules

- Never let live Nimble failure block the demo.
- Keep raw responses available for judge-facing visibility when possible.
- Normalize all scores before launch scoring.
- Keep fixture data realistic and tied to the demo product.
