"""Seed demo data into whichever store backend is active.

Defaults to the in-memory store (USE_CLICKHOUSE=false). Loads
`backend/fixtures/seed_businesses.json` and `demo_trend.json`, writes
the businesses, trend signals, and a starter set of relationships,
then prints a summary so judges can see what's loaded.

Usage:
    USE_CLICKHOUSE=false uv run python scripts/seed_demo_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running as `uv run python scripts/seed_demo_data.py` from project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.analytics.bias import rank_near_misses
from backend.analytics.relationships import build_relationships
from backend.db.clickhouse import get_client, use_clickhouse

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "backend" / "fixtures"
BUSINESSES_FILE = FIXTURES_DIR / "seed_businesses.json"
TREND_FILE = FIXTURES_DIR / "demo_trend.json"


def _load_json(path: Path) -> dict:
    with path.open() as handle:
        return json.load(handle)


def seed() -> dict:
    client = get_client()
    businesses_payload = _load_json(BUSINESSES_FILE)
    trend_payload = _load_json(TREND_FILE)

    written_businesses = []
    for business in businesses_payload["businesses"]:
        written_businesses.append(client.write_business(business))

    written_signals = []
    for signal in trend_payload["signals"]:
        written_signals.append(client.write_trend_signal(signal))

    edges = build_relationships(written_businesses)
    for edge in edges:
        client.write_relationship(
            from_business_id=edge.from_business_id,
            to_business_id=edge.to_business_id,
            relationship_type=edge.relationship_type,
            weight=edge.weight,
            reason=edge.reason,
        )

    near_misses = rank_near_misses(
        businesses=written_businesses,
        current_trend_scores=businesses_payload.get("current_trend_scores", {}),
        limit=5,
    )

    summary = {
        "backend": "clickhouse" if use_clickhouse() else "memory",
        "businesses_seeded": len(written_businesses),
        "trend_signals_seeded": len(written_signals),
        "relationships_seeded": len(edges),
        "near_misses_preview": [c.to_dict() for c in near_misses[:3]],
    }
    return summary


def main() -> None:
    summary = seed()
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
