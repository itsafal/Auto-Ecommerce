"""Nimble SERP API helper.

Calls https://api.webit.live/api/v1/realtime/serp with the bearer token in
NIMBLE_API_KEY and returns a compact summary suitable for grounding the
research agent. Falls back to None on any failure so the caller can
gracefully degrade to a Gemini-only path.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from backend.settings import get_settings

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.webit.live/api/v1/realtime/serp"


def _coerce_price(value: Any) -> float | None:
    """'$53.82' or 'Usually $120' or 53.82 -> 53.82 (None if it can't be parsed)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"(\d+(?:\.\d{1,2})?)", value.replace(",", ""))
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
    return None


def summarize_serp(parsed: dict[str, Any], query: str) -> dict[str, Any]:
    """Turn Nimble's raw parsed entities into a compact dict for the research prompt."""
    entities = parsed.get("entities") or {}
    organic = entities.get("OrganicResult") or []
    shopping = entities.get("ShoppingResult") or []
    related = entities.get("RelatedSearch") or []

    prices: list[float] = []
    for item in shopping:
        price = _coerce_price(item.get("price"))
        if price and 0 < price < 100000:
            prices.append(price)

    top_organic = []
    for item in organic[:5]:
        top_organic.append(
            {
                "title": (item.get("title") or "")[:140],
                "domain": item.get("cleaned_domain") or item.get("displayed_url"),
                "snippet": (item.get("snippet") or "")[:200],
            }
        )

    related_queries = []
    for item in related[:8]:
        text = item.get("EntityText") or item.get("title") or item.get("query")
        if text:
            related_queries.append(str(text)[:80])

    return {
        "query": query,
        "organic_count": len(organic),
        "shopping_count": len(shopping),
        "related_count": len(related),
        "price_low": min(prices) if prices else None,
        "price_high": max(prices) if prices else None,
        "price_samples": prices[:6],
        "top_organic": top_organic,
        "related_queries": related_queries,
    }


async def fetch_serp_summary(query: str, *, timeout: float = 12.0) -> dict[str, Any] | None:
    """Hit Nimble SERP and return a summarized dict, or None on failure.

    Best-effort: any exception/non-200 returns None so the caller can fall
    back to the LLM-only path.
    """
    settings = get_settings()
    if not settings.nimble_api_key:
        return None

    base_url = (settings.nimble_api_url or DEFAULT_BASE_URL).rstrip("/")
    payload = {
        "query": query,
        "search_engine": "google_search",
        "parse": True,
        "render": False,
        "country": "US",
    }
    headers = {
        "Authorization": f"Bearer {settings.nimble_api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning("[nimble] SERP fetch failed for %r: %s", query, exc)
        return None

    parsed = data.get("parsing") or {}
    if not parsed:
        logger.warning("[nimble] response missing parsing block for %r", query)
        return None

    return summarize_serp(parsed, query)
