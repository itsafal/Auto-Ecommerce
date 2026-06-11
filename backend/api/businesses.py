"""Businesses portfolio API.

Reads from the existing `launch_runs` storage (in-memory + ClickHouse), merges
storefront analytics events when present, and falls back to deterministic
synthetic metrics for stores that have not received traffic yet. Responses
include a `data_source` value so the UI can label the numbers honestly.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.schemas import Decision, LaunchRun
from backend.settings import get_settings
from backend.store import run_store

router = APIRouter(prefix="/api/businesses", tags=["businesses"])


# ---------------------------------------------------------------------------
# Synthetic metrics — deterministic per business slug so reloads stay stable.
# ---------------------------------------------------------------------------

_SOURCE_POOL = ["google", "tiktok", "instagram", "reddit", "direct", "email"]


def _seed(slug: str, salt: str) -> int:
    h = hashlib.sha256(f"{slug}::{salt}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _mock_metrics(slug: str) -> dict[str, Any]:
    views_total = 300 + _seed(slug, "views") % 12000
    views_24h = 30 + _seed(slug, "v24") % min(800, views_total)
    revenue_total = round(25.0 + _seed(slug, "rev") % 3800, 2)
    revenue_24h = round(revenue_total * (0.04 + (_seed(slug, "r24") % 18) / 100.0), 2)
    conversion_rate = round((0.5 + (_seed(slug, "conv") % 40) / 10.0) / 100.0, 4)
    bounce_rate = round((15 + _seed(slug, "bnc") % 56) / 100.0, 4)

    # Pick top-3 sources with shares that sum to ~1.0.
    rotated = _SOURCE_POOL[_seed(slug, "src") % len(_SOURCE_POOL):] + _SOURCE_POOL
    picks = rotated[:3]
    shares = [0.45 + (_seed(slug, "s0") % 25) / 100.0,
              0.20 + (_seed(slug, "s1") % 25) / 100.0,
              0.10 + (_seed(slug, "s2") % 20) / 100.0]
    total_share = sum(shares)
    shares = [round(s / total_share, 3) for s in shares]
    top_sources = [{"source": picks[i], "share": shares[i]} for i in range(3)]

    return {
        "views_total": views_total,
        "views_24h": views_24h,
        "revenue_total": revenue_total,
        "revenue_24h": revenue_24h,
        "conversion_rate": conversion_rate,
        "bounce_rate": bounce_rate,
        "top_sources": top_sources,
        "funnel": _funnel(
            views=views_total,
            cta_clicks=max(1, int(views_total * (0.08 + (_seed(slug, "cta") % 12) / 100.0))),
            checkouts=max(1, int(views_total * conversion_rate * 1.8)),
            email_captures=max(1, int(views_total * conversion_rate * 1.2)),
            purchase_attempts=max(1, int(views_total * conversion_rate)),
        ),
    }


# ---------------------------------------------------------------------------
# Business projection — wrap a LaunchRun with computed lifecycle + mock fields.
# ---------------------------------------------------------------------------


def _business_from_run(run: LaunchRun) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    launched_at = run.launched_at
    shutdown_at = run.shutdown_at
    days_live = None
    if launched_at:
        end = shutdown_at or now
        # Defensive: ClickHouse may return naive datetimes.
        if launched_at.tzinfo is None:
            launched_at = launched_at.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        delta = end - launched_at
        days_live = round(delta.total_seconds() / 86400.0, 2)

    metrics = _metrics_for_run(run)

    return {
        "run_id": str(run.run_id),
        "batch_id": str(run.batch_id) if run.batch_id else None,
        "batch_slot": run.batch_slot,
        "attempt_index": run.attempt_index,
        "slug": run.slug,
        "product_name": run.product_name,
        "store_url": run.store_url,
        "launch_score": run.launch_score,
        "decision": _coerce_str(run.decision),
        "status": _coerce_str(run.status),
        "business_status": run.business_status or "",
        "launched_at": launched_at.isoformat() if launched_at else None,
        "shutdown_at": shutdown_at.isoformat() if shutdown_at else None,
        "shutdown_reason": run.shutdown_reason or "",
        "days_live": days_live,
        **metrics,
    }


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    return value.value if hasattr(value, "value") else str(value)


def _is_launched(run: LaunchRun) -> bool:
    """A run is a 'business' once it has a store_url AND its decision is launch."""
    return bool(run.store_url) and _coerce_str(run.decision) == Decision.launch.value


def _portfolio_runs() -> list[LaunchRun]:
    """All runs that became businesses (live, shutdown, or archived)."""
    # list_runs_with_stores already filters to runs with a store_url and falls
    # back to ClickHouse on local miss.
    runs = run_store.list_runs_with_stores()
    return [r for r in runs if _is_launched(r)]


def _event_metadata(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("metadata") or {}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return raw if isinstance(raw, dict) else {}


def _event_timestamp(event: dict[str, Any]) -> datetime:
    ts = event.get("timestamp")
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    if isinstance(ts, str) and ts:
        try:
            parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _source_for_event(event: dict[str, Any]) -> str:
    source = str(event.get("source") or "").strip()
    if source:
        return source[:80]
    metadata = _event_metadata(event)
    referrer = str(metadata.get("referrer") or "").lower()
    for candidate in _SOURCE_POOL:
        if candidate in referrer:
            return candidate
    return "direct"


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _funnel(
    *,
    views: int,
    cta_clicks: int,
    checkouts: int,
    email_captures: int,
    purchase_attempts: int,
) -> dict[str, Any]:
    return {
        "views": views,
        "cta_clicks": cta_clicks,
        "checkouts": checkouts,
        "email_captures": email_captures,
        "purchase_attempts": purchase_attempts,
        "cta_rate": _rate(cta_clicks, views),
        "checkout_rate": _rate(checkouts, views),
        "capture_rate": _rate(email_captures, views),
        "purchase_rate": _rate(purchase_attempts, views),
    }


def _event_metrics(run: LaunchRun) -> dict[str, Any] | None:
    events = run_store.list_storefront_events(slug=run.slug, limit=10000)
    if not events:
        return None

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    by_type = Counter(str(event.get("event_type") or "") for event in events)
    recent = [event for event in events if _event_timestamp(event) >= cutoff]
    recent_by_type = Counter(str(event.get("event_type") or "") for event in recent)

    views_total = int(by_type["view_product"])
    views_24h = int(recent_by_type["view_product"])
    cta_clicks = int(by_type["click_cta"])
    email_captures = int(by_type["email_capture"])
    purchase_events = [event for event in events if event.get("event_type") == "purchase_attempt"]
    recent_purchase_events = [
        event for event in recent if event.get("event_type") == "purchase_attempt"
    ]
    revenue_total = round(sum(float(event.get("value") or 0.0) for event in purchase_events), 2)
    revenue_24h = round(sum(float(event.get("value") or 0.0) for event in recent_purchase_events), 2)
    checkout_total = int(by_type["begin_checkout"])
    purchase_total = len(purchase_events)
    conversion_numerator = purchase_total if purchase_total else checkout_total
    conversion_rate = round(conversion_numerator / views_total, 4) if views_total else 0.0
    engaged = int(by_type["click_cta"]) + checkout_total + int(by_type["email_capture"]) + purchase_total
    bounce_rate = round(max(0.0, 1.0 - (engaged / views_total)), 4) if views_total else 0.0

    sources = Counter(_source_for_event(event) for event in events)
    total_sources = sum(sources.values()) or 1
    top_sources = [
        {"source": source, "share": round(count / total_sources, 3)}
        for source, count in sources.most_common(3)
    ]

    return {
        "views_total": views_total,
        "views_24h": views_24h,
        "revenue_total": revenue_total,
        "revenue_24h": revenue_24h,
        "conversion_rate": conversion_rate,
        "bounce_rate": bounce_rate,
        "top_sources": top_sources,
        "funnel": _funnel(
            views=views_total,
            cta_clicks=cta_clicks,
            checkouts=checkout_total,
            email_captures=email_captures,
            purchase_attempts=purchase_total,
        ),
        "metric_source": "events",
    }


def _metrics_for_run(run: LaunchRun) -> dict[str, Any]:
    real = _event_metrics(run)
    if real is not None:
        return real
    metrics = _mock_metrics(run.slug or str(run.run_id))
    return {**metrics, "metric_source": "synthetic"}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_businesses(status: str | None = None, sort: str = "launched_at") -> dict[str, Any]:
    runs = _portfolio_runs()
    businesses = [_business_from_run(r) for r in runs]

    if status:
        status = status.strip().lower()
        # 'live' filters strictly; 'shutdown'/'archived' filter on business_status;
        # 'all' (default-none) returns everything.
        if status != "all":
            businesses = [b for b in businesses if b["business_status"] == status]

    reverse = True
    key_fn = {
        "launched_at": lambda b: b["launched_at"] or "",
        "score": lambda b: b["launch_score"] or 0.0,
        "revenue": lambda b: b["revenue_total"],
        "views": lambda b: b["views_total"],
        "days_live": lambda b: b["days_live"] or 0,
    }.get(sort, lambda b: b["launched_at"] or "")
    businesses.sort(key=key_fn, reverse=reverse)

    metric_sources = {b["metric_source"] for b in businesses}
    if not businesses or metric_sources == {"synthetic"}:
        data_source = "synthetic"
    elif metric_sources == {"events"}:
        data_source = "events"
    else:
        data_source = "mixed"

    summary = _summary(_portfolio_runs())
    return {
        "data_source": data_source,
        "summary": summary,
        "businesses": businesses,
    }


@router.post("/{slug}/shutdown")
async def shutdown_business(slug: str) -> dict[str, Any]:
    # A slug can map to several runs (the same product launched more than
    # once); shut down every one that isn't already, so the storefront URL
    # the operator clicked actually goes dark.
    targets = [r for r in _portfolio_runs() if r.slug == slug]
    if not targets:
        raise HTTPException(status_code=404, detail=f"No live business for slug {slug!r}")

    updated: LaunchRun | None = None
    for target in targets:
        if target.business_status == "shutdown":
            continue
        target.business_status = "shutdown"
        target.shutdown_at = datetime.now(timezone.utc)
        target.shutdown_reason = "manual"
        run_store.upsert_run(target)
        updated = target
    return _business_from_run(updated or targets[0])


@router.get("/backlog")
async def get_backlog(limit: int = 10) -> dict[str, Any]:
    return build_backlog(limit=limit)


def build_backlog(limit: int = 10) -> dict[str, Any]:
    """Top scoring products from trend_signals that have NOT yet been launched.

    The backlog is the future autonomous-loop queue: when a slot opens (a
    business gets shut down), the top of this list is what would be promoted.
    """
    launched_names = {
        (r.product_name or "").strip().lower()
        for r in _portfolio_runs()
    }
    # Pull recent signals (last 30 days), dedupe to highest score per product.
    signals = run_store.list_trend_signals(limit=200) if hasattr(run_store, "list_trend_signals") else []
    if not signals:
        # In-memory fallback — go through ClickHouse helper if available.
        from backend.db.clickhouse import get_client, use_clickhouse

        if use_clickhouse():
            try:
                client = get_client()
                if hasattr(client, "list_trend_signals"):
                    signals = client.list_trend_signals(limit=200)
            except Exception:
                signals = []

    best_by_name: dict[str, dict[str, Any]] = {}
    for s in signals:
        name = (s.get("product_name") or "").strip()
        if not name or name.lower() in launched_names:
            continue
        existing = best_by_name.get(name.lower())
        score = float(s.get("trend_score") or 0.0)
        if existing is None or score > existing["trend_score"]:
            best_by_name[name.lower()] = {
                "product_name": name,
                "category": s.get("category") or "",
                "source": s.get("source") or "",
                "trend_score": score,
                "detected_at": (
                    s.get("detected_at").isoformat()
                    if hasattr(s.get("detected_at"), "isoformat")
                    else str(s.get("detected_at") or "")
                ),
            }

    ranked = sorted(best_by_name.values(), key=lambda b: b["trend_score"], reverse=True)
    settings = get_settings()
    live_count = sum(1 for r in _portfolio_runs() if r.business_status == "live")
    return {
        "items": ranked[: max(1, min(limit, 50))],
        "live_count": live_count,
        "max_concurrent_live": settings.max_concurrent_live,
    }


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------


def _summary(runs: list[LaunchRun]) -> dict[str, Any]:
    live = [r for r in runs if r.business_status == "live"]
    settings = get_settings()
    live_metrics = [_metrics_for_run(r) for r in live]
    live_revenue = sum(float(m["revenue_total"]) for m in live_metrics)
    live_views_24h = sum(int(m["views_24h"]) for m in live_metrics)

    # Hit rate: across ALL runs (incl. rejected/non-launched), how many cleared.
    all_runs = run_store.list_runs_with_stores() or runs
    total_attempts = len(all_runs)
    approved = sum(1 for r in all_runs if _is_launched(r))
    hit_rate = round(approved / total_attempts, 3) if total_attempts else 0.0

    return {
        "live_count": len(live),
        "max_concurrent_live": settings.max_concurrent_live,
        "total_launched": len(runs),
        "total_revenue": round(live_revenue, 2),
        "total_views_24h": live_views_24h,
        "hit_rate": hit_rate,
        "threshold": settings.launch_score_threshold,
    }
