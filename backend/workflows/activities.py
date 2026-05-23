from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import Awaitable, Callable
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

# Last seen failure reason from either LLM path. Surfaced in /api/agents/trending-products
# so the dashboard can show *why* a refresh fell back to fixture instead of silently lying.
_last_llm_error: str | None = None

from backend.schemas import (
    AdvertisingOutput,
    AgentEvent,
    AgentName,
    BuyerOutput,
    Decision,
    EventType,
    FAQItem,
    LaunchRun,
    LaunchScoreOutput,
    ProductVariant,
    ResearchOutput,
    Review,
    RiskOutput,
    RunStatus,
    StoreOutput,
    WorkflowInput,
    WorkflowResult,
)
from backend.settings import get_settings

try:
    from temporalio import activity
except ImportError:

    class _ActivityCompat:
        @staticmethod
        def defn(fn):
            return fn

    activity = _ActivityCompat()


def slugify_product(product_name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", "", product_name.lower()).strip()
    words = cleaned.split()
    # Keep up to first 3 words, cap at 30 chars for sane subdomains.
    short = "".join(words[:3])[:30]
    if not short:
        short = "store"
    return short


def build_store_url(slug: str, base_domain: str | None = None) -> str:
    domain = (base_domain or get_settings().base_domain).strip().lower()
    host = domain.split(":")[0]
    scheme = "http" if host in {"localhost", "127.0.0.1"} or host.endswith(".localhost") else "https"
    return f"{scheme}://{slug}.{domain}"


def _product_profile(product_name: str) -> dict:
    name = product_name.lower()
    if "phone" in name and "mount" in name:
        return {
            "category": "phone_accessories",
            "trend_score": 0.86,
            "search_volume": 42000,
            "social_mentions": 18000,
            "summary": "Compact car-mount brands are trending with prices from $24 to $39.",
            "low": 24.0,
            "high": 39.0,
            "unit_cost": 8.4,
            "shipping_days": 6,
            "brand": "MagSnap Pro",
            "tagline": "Mount your phone in one clean snap.",
            "description": "A compact magnetic phone mount built for fast one-handed docking and a cleaner dashboard.",
            "hero": "/demo/magnetic-phone-mount.png",
        }
    if "power station" in name:
        return {
            "category": "portable_power",
            "trend_score": 0.82,
            "search_volume": 61000,
            "social_mentions": 23000,
            "summary": "Portable backup batteries are seeing strong demand from campers, creators, and outage-prep buyers.",
            "low": 129.0,
            "high": 249.0,
            "unit_cost": 74.0,
            "shipping_days": 8,
            "brand": "VoltPack Reserve",
            "tagline": "Backup power that travels.",
            "description": "A compact power station for phones, laptops, lights, and weekend backup needs.",
            "hero": "/demo/portable-power-station.png",
        }
    if "red light" in name or "therapy" in name:
        return {
            "category": "wellness_devices",
            "trend_score": 0.79,
            "search_volume": 54000,
            "social_mentions": 31000,
            "summary": "At-home beauty devices continue to trend, with buyers comparing comfort, fit, and routine consistency.",
            "low": 69.0,
            "high": 159.0,
            "unit_cost": 38.0,
            "shipping_days": 7,
            "brand": "GlowFrame Mask",
            "tagline": "A calmer nightly skincare ritual.",
            "description": "A lightweight LED face mask designed for comfortable, repeatable at-home skincare routines.",
            "hero": "/demo/red-light-therapy-mask.png",
        }
    if "projector" in name:
        return {
            "category": "home_entertainment",
            "trend_score": 0.77,
            "search_volume": 49000,
            "social_mentions": 21000,
            "summary": "Mini projectors are popular for dorm rooms, backyard movie nights, and small apartment setups.",
            "low": 59.0,
            "high": 139.0,
            "unit_cost": 31.0,
            "shipping_days": 6,
            "brand": "PocketBeam",
            "tagline": "Movie night, almost anywhere.",
            "description": "A travel-friendly mini projector built for quick setup, casual streaming, and compact spaces.",
            "hero": "/demo/mini-projector.png",
        }
    if "smart ring" in name or "fitness tracker" in name:
        return {
            "category": "wearable_tech",
            "trend_score": 0.84,
            "search_volume": 67000,
            "social_mentions": 28000,
            "summary": "Low-profile health wearables are trending as buyers look beyond watches for sleep and recovery tracking.",
            "low": 49.0,
            "high": 129.0,
            "unit_cost": 24.0,
            "shipping_days": 9,
            "brand": "PulseLoop Ring",
            "tagline": "Wellness tracking without the watch.",
            "description": "A slim smart ring concept for everyday wellness signals, sleep routines, and minimalist tracking.",
            "hero": "/demo/smart-ring.png",
        }
    if "ice bath" in name:
        return {
            "category": "fitness_recovery",
            "trend_score": 0.75,
            "search_volume": 36000,
            "social_mentions": 26000,
            "summary": "Cold plunge products remain popular with recovery-focused fitness buyers and home gym owners.",
            "low": 79.0,
            "high": 189.0,
            "unit_cost": 42.0,
            "shipping_days": 10,
            "brand": "ChillPod Recovery",
            "tagline": "Cold recovery, small footprint.",
            "description": "A portable ice bath pod for athletes and home recovery routines without a permanent tub.",
            "hero": "/demo/ice-bath-pod.png",
        }
    if "lamp" in name:
        return {
            "category": "workspace_accessories",
            "trend_score": 0.71,
            "search_volume": 33000,
            "social_mentions": 12000,
            "summary": "Desk lighting products sell well when they combine clean design, dimming, and work-from-home utility.",
            "low": 29.0,
            "high": 79.0,
            "unit_cost": 15.0,
            "shipping_days": 5,
            "brand": "FocusBeam Desk",
            "tagline": "Cleaner light for deep work.",
            "description": "A smart LED desk lamp with adjustable brightness for focused work and evening wind-downs.",
            "hero": "/demo/smart-desk-lamp.png",
        }
    title = product_name.title()
    return {
        "category": "general_merchandise",
        "trend_score": 0.68,
        "search_volume": 24000,
        "social_mentions": 9000,
        "summary": f"{title} has moderate demand signals and room for a focused single-product offer.",
        "low": 24.0,
        "high": 69.0,
        "unit_cost": 14.0,
        "shipping_days": 7,
        "brand": f"{title.replace(' ', '')} Co",
        "tagline": f"A sharper way to buy {product_name}.",
        "description": f"A focused, benefit-led storefront for {product_name} with clear pricing and fast purchase flow.",
        "hero": f"/demo/{slugify_product(product_name)}.png",
    }


def _parse_json_text(text: str) -> dict | None:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def _portkey_json(prompt: str) -> dict | None:
    global _last_llm_error
    settings = get_settings()
    if not settings.portkey_api_key:
        return None

    base_url = settings.portkey_base_url.rstrip("/")
    payload = {
        "model": settings.portkey_model,
        "messages": [
            {"role": "system", "content": "Return only valid JSON. Do not include markdown or commentary."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 900,
    }
    headers = {
        "Authorization": f"Bearer {settings.portkey_api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        msg = f"portkey {exc.response.status_code}: {exc.response.text[:200]}"
        logger.warning("[llm] %s", msg)
        _last_llm_error = msg
        return None
    except Exception as exc:
        msg = f"portkey {type(exc).__name__}: {exc}"
        logger.warning("[llm] %s", msg)
        _last_llm_error = msg
        return None
    return _parse_json_text(text)


async def _google_gemini_json(prompt: str) -> dict | None:
    global _last_llm_error
    settings = get_settings()
    if not settings.google_api_key:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, params={"key": settings.google_api_key}, json=payload)
            response.raise_for_status()
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except httpx.HTTPStatusError as exc:
        msg = f"google {exc.response.status_code}: {exc.response.text[:200]}"
        logger.warning("[llm] %s", msg)
        _last_llm_error = msg
        return None
    except Exception as exc:
        msg = f"google {type(exc).__name__}: {exc}"
        logger.warning("[llm] %s", msg)
        _last_llm_error = msg
        return None

    return _parse_json_text(text)


async def _gemini_json(prompt: str, *, ignore_fixture_flag: bool = False) -> dict | None:
    settings = get_settings()
    if settings.use_agent_fixtures and not ignore_fixture_flag:
        return None

    portkey_result = await _portkey_json(prompt)
    if portkey_result is not None:
        return portkey_result
    return await _google_gemini_json(prompt)


_FALLBACK_TRENDING = [
    "Magnetic Phone Mount",
    "Portable Power Station",
    "Red Light Therapy Mask",
    "Mini Portable Projector",
    "Smart Ring Fitness Tracker",
    "Portable Ice Bath",
    "Smart Desk Lamp",
    "Ergo Keyboard",
    "Portable Blender",
]


_TRENDING_CACHE: dict | None = None
_TRENDING_CACHE_AT: float = 0.0
_TRENDING_CACHE_TTL_SECONDS = 60.0


async def discover_trending_products(limit: int = 8) -> dict:
    """Trend Scout agent: returns a list of currently trending DTC product names.

    Uses Gemini when configured; otherwise falls back to a curated rotating list.
    Cached for ~60s so a dashboard that mounts multiple times doesn't burn through
    free-tier LLM quota on repeated identical calls.
    """
    global _TRENDING_CACHE, _TRENDING_CACHE_AT, _last_llm_error

    now = time.monotonic()
    if _TRENDING_CACHE is not None and (now - _TRENDING_CACHE_AT) < _TRENDING_CACHE_TTL_SECONDS:
        cached = dict(_TRENDING_CACHE)
        cached["products"] = cached["products"][:limit]
        cached["cached"] = True
        return cached

    prompt = (
        f"List {limit} currently trending single-product dropshipping ideas that would "
        "work as a focused one-product store. Mix tech, wellness, home, fitness, lifestyle. "
        "Return ONLY JSON: {\"products\": [\"...\", ...]}. No commentary."
    )
    _last_llm_error = None
    result = await _gemini_json(prompt, ignore_fixture_flag=True)
    products: list[str] = []
    if isinstance(result, dict):
        raw = result.get("products") or result.get("items") or []
        if isinstance(raw, list):
            products = [str(item).strip() for item in raw if str(item).strip()]

    if not products:
        import random

        pool = list(_FALLBACK_TRENDING)
        random.shuffle(pool)
        products = pool[:limit]

    response = {
        "products": products[:limit],
        "source": "gemini" if result else "fixture",
        "cached": False,
    }
    if not result and _last_llm_error:
        response["llm_error"] = _last_llm_error

    _TRENDING_CACHE = response
    _TRENDING_CACHE_AT = now
    return dict(response)


def make_event(
    agent_name: AgentName,
    event_type: EventType,
    message: str,
    payload: dict | None = None,
    timestamp: datetime | None = None,
) -> AgentEvent:
    return AgentEvent(
        agent_name=agent_name,
        event_type=event_type,
        message=message,
        payload=payload or {},
        **({"timestamp": timestamp} if timestamp is not None else {}),
    )


@activity.defn
async def research_activity(product_name: str) -> ResearchOutput:
    # 1. Real market data from Nimble SERP (organic + shopping listings).
    from backend.integrations.nimble import fetch_serp_summary

    nimble = await fetch_serp_summary(product_name)

    if nimble:
        # 2. Ground Gemini in the actual SERP data instead of letting it hallucinate.
        prompt = f"""
You are analyzing real Google SERP data for an e-commerce product.

Product: {product_name}
SERP data (from Nimble, US, today):
- organic_count: {nimble['organic_count']}
- shopping_count: {nimble['shopping_count']}
- related_count: {nimble['related_count']}
- price_range observed: low=${nimble['price_low']}, high=${nimble['price_high']}
- sample prices: {nimble['price_samples']}
- top organic results: {nimble['top_organic']}
- related searches: {nimble['related_queries']}

Return JSON only (numbers must reflect the SERP data above, not hallucinated):
{{
  "category": "short_snake_case",
  "trend_score": 0.0,                  // 0-1, derive from shopping_count + organic_count + related_count
  "search_volume": 0,                  // estimate from organic_count (e.g. organic_count * 1500 as a proxy)
  "social_mentions": 0,                // estimate from related_count (e.g. related_count * 800 as a proxy)
  "competitor_summary": "one sentence grounded in the top_organic titles/snippets",
  "price_range": {{"low": 0.0, "high": 0.0}},
  "confidence": 0.0                    // higher when there's more SERP data
}}
""".strip()
        generated = await _gemini_json(prompt, ignore_fixture_flag=True)
        if generated:
            # Force the real Nimble price range into the response if Gemini drifted.
            if nimble["price_low"] and nimble["price_high"]:
                generated["price_range"] = {
                    "low": nimble["price_low"],
                    "high": nimble["price_high"],
                }
            try:
                return ResearchOutput(product_name=product_name, **generated)
            except Exception:
                pass

    # 3. No Nimble (off VPN / no key / API down). Fall back to LLM-only.
    prompt = f"""
Return JSON only for ecommerce product research:
{{
  "category": "short_snake_case",
  "trend_score": 0.0,
  "search_volume": 0,
  "social_mentions": 0,
  "competitor_summary": "one sentence",
  "price_range": {{"low": 0.0, "high": 0.0}},
  "confidence": 0.0
}}
Product: {product_name}
""".strip()
    generated = await _gemini_json(prompt)
    if generated:
        try:
            return ResearchOutput(product_name=product_name, **generated)
        except Exception:
            pass

    # 4. Last resort: curated fixture profile.
    profile = _product_profile(product_name)
    return ResearchOutput(
        product_name=product_name,
        category=profile["category"],
        trend_score=profile["trend_score"],
        search_volume=profile["search_volume"],
        social_mentions=profile["social_mentions"],
        competitor_summary=profile["summary"],
        price_range={"low": profile["low"], "high": profile["high"]},
        confidence=0.82,
    )


@activity.defn
async def buyer_activity(research: ResearchOutput) -> BuyerOutput:
    profile = _product_profile(research.product_name)
    unit_cost = profile["unit_cost"]
    retail_price = round(max(research.price_range.high * 0.82, unit_cost * 2.8), 2)
    margin = round((retail_price - unit_cost) / retail_price, 2)
    if research.category == "phone_accessories":
        margin_score = 0.72
        confidence_score = 0.84
        estimated_margin = 0.61
    else:
        margin_score = max(0.45, min(0.9, round(margin + 0.08, 2)))
        confidence_score = 0.78 if profile["shipping_days"] > 8 else 0.84
        estimated_margin = margin
    supplier_id = sum(ord(ch) for ch in research.category) % 9000 + 1000
    return BuyerOutput(
        supplier_name=f"Demo Supplier {supplier_id}",
        unit_cost=unit_cost,
        shipping_days=profile["shipping_days"],
        rating=4.5 if profile["shipping_days"] > 8 else 4.7,
        estimated_margin=estimated_margin,
        margin_score=margin_score,
        confidence_score=confidence_score,
        risk_flags=[],
    )


@activity.defn
async def legal_risk_activity(research: ResearchOutput, buyer: BuyerOutput) -> RiskOutput:
    risk_score = 0.18
    flags: list[str] = []
    recommendation = "Safe for demo launch. Avoid regulated or guaranteed-performance claims."
    if research.category in {"wellness_devices", "fitness_recovery"}:
        risk_score = 0.28
        flags = ["Avoid medical, treatment, or guaranteed recovery claims."]
        recommendation = "Launchable with conservative wellness positioning and clear claim limits."
    elif research.category == "phone_accessories":
        risk_score = 0.12
        recommendation = "Safe for demo launch. Avoid claims about crash prevention or guaranteed safety."
    return RiskOutput(
        cleared=True,
        risk_score=risk_score,
        flags=flags,
        recommendation=recommendation,
    )


def _fallback_storefront_assets(
    product_name: str, profile: dict, buyer: BuyerOutput, risk: RiskOutput
) -> dict:
    base_price = round(max(buyer.unit_cost / max(0.2, 1 - buyer.estimated_margin), 19.99), 2)
    title = product_name.title()
    features = [
        f"Engineered for everyday {profile['category'].replace('_', ' ')} use",
        "Premium materials with a clean, modern finish",
        f"Ships in {buyer.shipping_days} days with tracked delivery",
        "30-day satisfaction guarantee and easy returns",
        "Trusted by early adopters and reviewers",
    ]
    specs = {
        "Category": profile["category"].replace("_", " ").title(),
        "Shipping": f"{buyer.shipping_days} days, tracked",
        "Warranty": "1 year limited",
        "Returns": "30 days, no questions",
    }
    variants = [
        {
            "name": f"{profile['brand']} Standard",
            "price": base_price,
            "blurb": "The everyday pick. Clean look, full feature set.",
            "badge": "Most popular",
            "accent": "#0f766e",
        },
        {
            "name": f"{profile['brand']} Pro",
            "price": round(base_price * 1.35, 2),
            "blurb": "Upgraded build, longer battery, premium finish.",
            "badge": "Best value",
            "accent": "#1d4ed8",
        },
        {
            "name": f"{profile['brand']} Mini",
            "price": round(base_price * 0.75, 2),
            "blurb": "Compact size for travel and tight spaces.",
            "badge": "Travel",
            "accent": "#9333ea",
        },
        {
            "name": f"{profile['brand']} Bundle",
            "price": round(base_price * 1.85, 2),
            "blurb": "Two units + accessories. Save 18% vs single.",
            "badge": "Save 18%",
            "accent": "#b45309",
        },
    ]
    faq = [
        {"question": f"How long does shipping take?", "answer": f"Orders ship in {buyer.shipping_days} days with full tracking."},
        {"question": "What is the return policy?", "answer": "30-day no-questions returns. We cover return shipping."},
        {"question": f"Is the {title} covered by warranty?", "answer": "Yes, a 1 year limited warranty on parts and workmanship."},
        {"question": "Do you ship internationally?", "answer": "We ship to the US, CA, UK, AU, and EU member countries."},
    ]
    reviews = [
        {"name": "Avery K.", "rating": 5.0, "text": f"The {title.lower()} replaced two products I had cluttering my space. Worth it."},
        {"name": "Jordan M.", "rating": 4.5, "text": "Build quality is way better than I expected at this price. Recommend."},
        {"name": "Priya S.", "rating": 5.0, "text": "Arrived fast, set up in minutes, working great two weeks in."},
    ]
    shipping_note = f"Ships in {buyer.shipping_days} days · Tracked delivery"
    return {
        "features": features,
        "specs": specs,
        "variants": variants,
        "faq": faq,
        "reviews": reviews,
        "shipping_note": shipping_note,
    }


@activity.defn
async def advertising_activity(research: ResearchOutput, buyer: BuyerOutput, risk: RiskOutput) -> AdvertisingOutput:
    profile = _product_profile(research.product_name)
    fallback_assets = _fallback_storefront_assets(research.product_name, profile, buyer, risk)
    prompt = f"""
Return JSON only for an ecommerce storefront:
{{
  "product_name": "brandable product name (2-3 words)",
  "tagline": "under 9 words",
  "description": "two benefit-focused sentences",
  "cta_text": "short CTA",
  "hero_image_prompt": "specific product photo prompt",
  "hero_image_url": "/demo/example.png",
  "features": ["4-5 short benefit bullets, each under 12 words"],
  "specs": {{"Material": "...", "Dimensions": "...", "Weight": "...", "Battery": "..."}},
  "variants": [
    {{"name": "...", "price": 29.99, "blurb": "1 line", "badge": "Most popular", "accent": "#0f766e"}}
  ],
  "faq": [{{"question": "...", "answer": "..."}}],
  "reviews": [{{"name": "First L.", "rating": 4.8, "text": "1-2 sentence review"}}],
  "shipping_note": "Ships in N days · Tracked delivery"
}}
Provide 4 distinct variants (Standard, Pro, Mini, Bundle) with prices spanning ~0.7x-1.9x base.
Base price target: {round(max(buyer.unit_cost / max(0.2, 1 - buyer.estimated_margin), 19.99), 2)}
Product: {research.product_name}
Category: {research.category}
Research: {research.competitor_summary}
Supplier cost: {buyer.unit_cost}
Shipping days: {buyer.shipping_days}
Risk note: {risk.recommendation}
""".strip()
    generated = await _gemini_json(prompt, ignore_fixture_flag=True)
    if generated:
        # Merge: prefer Gemini fields, fall back per-field for anything missing.
        merged = {
            "product_name": generated.get("product_name") or profile["brand"],
            "tagline": generated.get("tagline") or profile["tagline"],
            "description": generated.get("description") or profile["description"],
            "cta_text": generated.get("cta_text") or f"Buy Now - Ships in {buyer.shipping_days} days",
            "hero_image_prompt": generated.get("hero_image_prompt")
            or f"Clean studio product photo of {research.product_name}, commercial lighting, crisp shadows",
            "hero_image_url": generated.get("hero_image_url") or profile["hero"],
            "features": generated.get("features") or fallback_assets["features"],
            "specs": generated.get("specs") or fallback_assets["specs"],
            "variants": generated.get("variants") or fallback_assets["variants"],
            "faq": generated.get("faq") or fallback_assets["faq"],
            "reviews": generated.get("reviews") or fallback_assets["reviews"],
            "shipping_note": generated.get("shipping_note") or fallback_assets["shipping_note"],
        }
        try:
            return AdvertisingOutput(**merged)
        except Exception:
            pass

    return AdvertisingOutput(
        product_name=profile["brand"],
        tagline=profile["tagline"],
        description=profile["description"],
        cta_text=f"Buy Now - Ships in {buyer.shipping_days} days",
        hero_image_prompt=f"Clean studio product photo of {research.product_name}, commercial lighting, crisp shadows",
        hero_image_url=profile["hero"],
        features=fallback_assets["features"],
        specs=fallback_assets["specs"],
        variants=[ProductVariant(**v) for v in fallback_assets["variants"]],
        faq=[FAQItem(**f) for f in fallback_assets["faq"]],
        reviews=[Review(**r) for r in fallback_assets["reviews"]],
        shipping_note=fallback_assets["shipping_note"],
    )


@activity.defn
async def score_launch_activity(research: ResearchOutput, buyer: BuyerOutput, risk: RiskOutput) -> LaunchScoreOutput:
    launch_score = (
        research.trend_score * 0.30
        + buyer.margin_score * 0.25
        + buyer.confidence_score * 0.25
        - risk.risk_score * 0.20
    )
    decision = Decision.launch if launch_score >= 0.5 and risk.cleared else Decision.pause
    return LaunchScoreOutput(launch_score=round(launch_score, 3), decision=decision)


@activity.defn
async def create_store_activity(
    workflow_input: WorkflowInput,
    advertising: AdvertisingOutput,
    buyer: BuyerOutput,
) -> StoreOutput:
    slug = slugify_product(workflow_input.product_name)
    retail_price = round(max(buyer.unit_cost / max(0.2, 1 - buyer.estimated_margin), 19.99), 2)
    return StoreOutput(
        store_id=uuid4(),
        slug=slug,
        store_url=build_store_url(slug),
        product_name=advertising.product_name,
        tagline=advertising.tagline,
        description=advertising.description,
        price=retail_price,
        hero_image_url=advertising.hero_image_url,
        supplier=buyer.supplier_name,
        cta_text=advertising.cta_text,
        features=advertising.features,
        specs=advertising.specs,
        variants=advertising.variants,
        faq=advertising.faq,
        reviews=advertising.reviews,
        shipping_note=advertising.shipping_note or f"Ships in {buyer.shipping_days} days",
    )


def build_launch_result(
    workflow_input: WorkflowInput,
    research: ResearchOutput,
    buyer: BuyerOutput,
    risk: RiskOutput,
    advertising: AdvertisingOutput,
    score: LaunchScoreOutput,
    store: StoreOutput,
    status: RunStatus,
    timestamp: datetime | None = None,
) -> WorkflowResult:
    events = [
        make_event(
            AgentName.research,
            EventType.completed,
            f"Research completed with trend score {research.trend_score}",
            {"trend_score": research.trend_score, "confidence": research.confidence},
            timestamp=timestamp,
        ),
        make_event(
            AgentName.buyer,
            EventType.completed,
            f"Buyer selected {buyer.supplier_name} with confidence {buyer.confidence_score}",
            {"supplier_confidence": buyer.confidence_score, "margin_score": buyer.margin_score},
            timestamp=timestamp,
        ),
        make_event(
            AgentName.legal_risk,
            EventType.completed,
            f"Legal risk completed with risk score {risk.risk_score}",
            {"cleared": risk.cleared, "risk_score": risk.risk_score},
            timestamp=timestamp,
        ),
        make_event(
            AgentName.advertising,
            EventType.completed,
            f"Advertising generated storefront copy for {advertising.product_name}",
            {"product_name": advertising.product_name, "tagline": advertising.tagline},
            timestamp=timestamp,
        ),
        make_event(
            AgentName.score_launch,
            EventType.completed,
            f"Launch score is {score.launch_score} with decision {score.decision}",
            {"launch_score": score.launch_score, "decision": score.decision},
            timestamp=timestamp,
        ),
        make_event(
            AgentName.store_creator,
            EventType.completed,
            f"Store created at {store.store_url}",
            {"store_url": store.store_url, "slug": store.slug},
            timestamp=timestamp,
        ),
    ]

    run = LaunchRun(
        run_id=workflow_input.run_id,
        temporal_workflow_id=workflow_input.temporal_workflow_id,
        product_name=workflow_input.product_name,
        slug=store.slug,
        status=status,
        launch_score=score.launch_score,
        decision=score.decision,
        store_url=store.store_url,
        error=None,
    )
    return WorkflowResult(run=run, events=events, store=store)


def _model_label() -> str:
    """Best-effort label of which LLM the agents would have used."""
    s = get_settings()
    if s.portkey_api_key:
        return s.portkey_model
    if s.google_api_key:
        return s.gemini_model
    return "fixture"


def _summarize(value) -> str:
    """Compact string of an output for the agent_decisions log."""
    try:
        if hasattr(value, "model_dump"):
            return json.dumps(value.model_dump(mode="json"), default=str)[:480]
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str)[:480]
        return str(value)[:480]
    except Exception:
        return str(value)[:480]


async def _timed_decision(
    run_id,
    agent_name: AgentName,
    action: str,
    runner: Callable[[], Awaitable],
    *,
    input_summary: str = "",
):
    """Run an activity and persist a row to agent_decisions with latency."""
    # Local import to avoid a circular dependency at module load time.
    from backend.store import run_store

    started = time.monotonic()
    try:
        result = await runner()
        latency_ms = int((time.monotonic() - started) * 1000)
        run_store.record_decision(
            run_id=run_id,
            agent_name=agent_name.value if hasattr(agent_name, "value") else str(agent_name),
            action=action,
            input_summary=input_summary,
            output_summary=_summarize(result),
            latency_ms=latency_ms,
            model_used=_model_label(),
        )
        return result
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        run_store.record_decision(
            run_id=run_id,
            agent_name=agent_name.value if hasattr(agent_name, "value") else str(agent_name),
            action=f"{action}_failed",
            input_summary=input_summary,
            output_summary=f"{type(exc).__name__}: {exc}",
            latency_ms=latency_ms,
            model_used=_model_label(),
        )
        raise


async def execute_fixture_launch(workflow_input: WorkflowInput) -> WorkflowResult:
    research = await _timed_decision(
        workflow_input.run_id, AgentName.research, "research_product",
        lambda: research_activity(workflow_input.product_name),
        input_summary=workflow_input.product_name,
    )
    buyer = await _timed_decision(
        workflow_input.run_id, AgentName.buyer, "select_supplier",
        lambda: buyer_activity(research),
        input_summary=f"product={workflow_input.product_name} category={getattr(research, 'category', '')}",
    )
    risk = await _timed_decision(
        workflow_input.run_id, AgentName.legal_risk, "assess_risk",
        lambda: legal_risk_activity(research, buyer),
        input_summary=workflow_input.product_name,
    )
    advertising = await _timed_decision(
        workflow_input.run_id, AgentName.advertising, "generate_copy",
        lambda: advertising_activity(research, buyer, risk),
        input_summary=workflow_input.product_name,
    )
    score = await _timed_decision(
        workflow_input.run_id, AgentName.score_launch, "score_launch",
        lambda: score_launch_activity(research, buyer, risk),
        input_summary=f"trend={research.trend_score} margin={buyer.margin_score}",
    )
    store = await _timed_decision(
        workflow_input.run_id, AgentName.store_creator, "create_store",
        lambda: create_store_activity(workflow_input, advertising, buyer),
        input_summary=workflow_input.product_name,
    )

    return build_launch_result(
        workflow_input=workflow_input,
        research=research,
        buyer=buyer,
        risk=risk,
        advertising=advertising,
        score=score,
        store=store,
        status=RunStatus.fallback_completed,
    )


EventSink = Callable[[AgentEvent], Awaitable[None] | None]
ProgressSink = Callable[[LaunchRun], Awaitable[None] | None]
StoreSink = Callable[[StoreOutput], Awaitable[None] | None]


async def _emit(sink: EventSink | None, event: AgentEvent) -> None:
    if sink is None:
        return
    result = sink(event)
    if asyncio.iscoroutine(result):
        await result


async def _progress(sink: ProgressSink | None, run: LaunchRun) -> None:
    if sink is None:
        return
    result = sink(run)
    if asyncio.iscoroutine(result):
        await result


async def _store_sink(sink: StoreSink | None, store: StoreOutput) -> None:
    if sink is None:
        return
    result = sink(store)
    if asyncio.iscoroutine(result):
        await result


_RUNNING_MESSAGES: dict[AgentName, str] = {
    AgentName.research: "Scanning trend signals and competitor pricing...",
    AgentName.buyer: "Negotiating with suppliers and checking margins...",
    AgentName.legal_risk: "Reviewing compliance and risk exposure...",
    AgentName.advertising: "Drafting storefront copy and hero creative...",
    AgentName.score_launch: "Calculating final launch score...",
    AgentName.store_creator: "Provisioning storefront and DNS...",
}


async def execute_streaming_launch(
    workflow_input: WorkflowInput,
    *,
    delay_ms: int,
    on_event: EventSink | None = None,
    on_progress: ProgressSink | None = None,
    on_store: StoreSink | None = None,
) -> WorkflowResult:
    """Run the fixture pipeline emitting `running` + `completed` events per agent.

    Used by the API in real-time mode so the dashboard can render progress as it
    happens. The terminal `WorkflowResult` is also returned for callers that want
    a single snapshot at the end (e.g. Temporal persistence).
    """

    delay = max(delay_ms, 0) / 1000.0
    base_run = LaunchRun(
        run_id=workflow_input.run_id,
        temporal_workflow_id=workflow_input.temporal_workflow_id,
        product_name=workflow_input.product_name,
        slug=slugify_product(workflow_input.product_name),
        status=RunStatus.running,
    )
    await _progress(on_progress, base_run)

    async def _step(agent: AgentName, runner, *, action: str, input_summary: str = ""):
        await _emit(
            on_event,
            make_event(agent, EventType.running, _RUNNING_MESSAGES[agent]),
        )
        if delay:
            await asyncio.sleep(delay)
        return await _timed_decision(
            workflow_input.run_id, agent, action, runner, input_summary=input_summary
        )

    research = await _step(
        AgentName.research,
        lambda: research_activity(workflow_input.product_name),
        action="research_product",
        input_summary=workflow_input.product_name,
    )
    await _emit(
        on_event,
        make_event(
            AgentName.research,
            EventType.completed,
            f"Research completed with trend score {research.trend_score}",
            {"trend_score": research.trend_score, "confidence": research.confidence},
        ),
    )

    buyer = await _step(
        AgentName.buyer,
        lambda: buyer_activity(research),
        action="select_supplier",
        input_summary=f"product={workflow_input.product_name} category={getattr(research, 'category', '')}",
    )
    await _emit(
        on_event,
        make_event(
            AgentName.buyer,
            EventType.completed,
            f"Buyer selected {buyer.supplier_name} with confidence {buyer.confidence_score}",
            {"supplier_confidence": buyer.confidence_score, "margin_score": buyer.margin_score},
        ),
    )

    risk = await _step(
        AgentName.legal_risk,
        lambda: legal_risk_activity(research, buyer),
        action="assess_risk",
        input_summary=workflow_input.product_name,
    )
    await _emit(
        on_event,
        make_event(
            AgentName.legal_risk,
            EventType.completed,
            f"Legal risk completed with risk score {risk.risk_score}",
            {"cleared": risk.cleared, "risk_score": risk.risk_score},
        ),
    )

    advertising = await _step(
        AgentName.advertising,
        lambda: advertising_activity(research, buyer, risk),
        action="generate_copy",
        input_summary=workflow_input.product_name,
    )
    await _emit(
        on_event,
        make_event(
            AgentName.advertising,
            EventType.completed,
            f"Advertising generated storefront copy for {advertising.product_name}",
            {"product_name": advertising.product_name, "tagline": advertising.tagline},
        ),
    )

    score = await _step(
        AgentName.score_launch,
        lambda: score_launch_activity(research, buyer, risk),
        action="score_launch",
        input_summary=f"trend={research.trend_score} margin={buyer.margin_score}",
    )
    await _emit(
        on_event,
        make_event(
            AgentName.score_launch,
            EventType.completed,
            f"Launch score is {score.launch_score} with decision {score.decision}",
            {"launch_score": score.launch_score, "decision": score.decision},
        ),
    )

    store = await _step(
        AgentName.store_creator,
        lambda: create_store_activity(workflow_input, advertising, buyer),
        action="create_store",
        input_summary=workflow_input.product_name,
    )
    await _store_sink(on_store, store)
    await _emit(
        on_event,
        make_event(
            AgentName.store_creator,
            EventType.completed,
            f"Store created at {store.store_url}",
            {"store_url": store.store_url, "slug": store.slug, "variants": len(store.variants)},
        ),
    )

    result = build_launch_result(
        workflow_input=workflow_input,
        research=research,
        buyer=buyer,
        risk=risk,
        advertising=advertising,
        score=score,
        store=store,
        status=RunStatus.fallback_completed,
    )
    await _progress(on_progress, result.run)
    return result
