"""Autonomous portfolio lifecycle — DESIGN STUBS for the future always-on loop.

This module is intentionally not wired to anything yet. It documents the shape
the autonomous loop will take when the cron / scheduler arrives in a later PR.

The intended runtime:

    every N minutes (e.g. 15):
        1. evaluate_shutdown_candidates()
            For each business with business_status='live':
              - check days_live, conversion_rate, revenue_24h vs targets
              - if combined metrics fall below threshold for K consecutive
                checks, call shutdown_business(slug, reason='underperforming')
        2. promote_top_of_backlog()
            If live_count < settings.max_concurrent_live:
              - read GET /api/businesses/backlog
              - take the top item
              - trigger a single-slot batch deploy seeded with that product
                (which writes a launch_runs row + flips business_status=live
                on approval)
        3. If live_count < max_concurrent_live AND backlog is too short:
              - kick off a Trend Scout refresh + research mini-batch to top up
                the backlog with fresh candidates

These stubs exist so the surface (settings.max_concurrent_live, the
businesses portfolio table, the backlog endpoint, the manual shutdown action)
have a clear next-step target.
"""

from __future__ import annotations


def evaluate_shutdown_candidates() -> list[str]:
    """Inspect live businesses; return slugs that should be shut down.

    Not implemented yet. Future: read live businesses + their metrics (real,
    once analytics is wired), apply a configurable rule like:
        days_live >= grace_window AND (revenue_24h < min OR conversion_rate < min)
    Return list of slugs to call POST /api/businesses/{slug}/shutdown on.
    """
    return []


def promote_top_of_backlog() -> str | None:
    """If we're under the live cap, return the slug of the next backlog product
    to deploy. Not implemented yet."""
    return None
