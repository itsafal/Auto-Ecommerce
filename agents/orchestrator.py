"""
CEO Orchestrator Agent — routes between all sub-agents and assembles the final store config.
Pipeline: Research → Buyer → Legal → Advertising → Store Launch

Dipesh owns research.py and buyer.py.
Deepali owns legal.py, advertising.py, and this wiring.
"""

import logging
import time
from uuid import uuid4

from agents.schemas import AgentMessage, StorePayload

logger = logging.getLogger(__name__)


def run_pipeline(
    product_name: str,
    nimble_data: dict | None = None,
) -> dict:
    """
    Full agent pipeline. Returns the final store config dict or raises on failure.
    
    Args:
        product_name: The trending product to launch a store for.
        nimble_data: Pre-fetched Nimble trend data (optional; Research agent fetches if None).
    
    Returns:
        store_config dict matching the StorePayload shape + all agent outputs.
    """
    business_id = str(uuid4())
    pipeline_start = time.time()

    logger.info(f"[ceo] 🚀 Pipeline start | product={product_name} | business_id={business_id}")
    _log_decision(business_id, "ceo", "launch_initiated", {"product_name": product_name})

    # ── Step 1: Research Agent ────────────────────────────────────────────────
    logger.info("[ceo] → Research Agent")
    from agents.research import run_research_agent  # Dipesh's module
    research_msg = run_research_agent(product_name, business_id, nimble_data=nimble_data)

    if research_msg.action == "research_failed":
        return _fail(business_id, "research", research_msg.error)

    research = research_msg.payload
    logger.info(f"[ceo] ✓ Research complete | trend_score={research['trend_score']:.2f} | margin={research['estimated_margin']:.0%}")

    # ── Step 2: Buyer Agent ───────────────────────────────────────────────────
    logger.info("[ceo] → Buyer Agent")
    from agents.buyer import run_buyer_agent  # Dipesh's module
    buyer_msg = run_buyer_agent(product_name, research, business_id)

    if buyer_msg.action == "buyer_failed":
        return _fail(business_id, "buyer", buyer_msg.error)

    buyer = buyer_msg.payload
    logger.info(f"[ceo] ✓ Buyer complete | supplier={buyer['selected_supplier']['name']} | margin={buyer['projected_margin']:.0%}")

    # ── Step 3: Legal Agent (Deepali) ─────────────────────────────────────────
    logger.info("[ceo] → Legal Agent")
    from agents.legal import run_legal_agent
    legal_msg = run_legal_agent(
        product_name=product_name,
        category=research["category"],
        supplier_info=buyer["selected_supplier"],
        business_id=business_id,
    )

    _log_decision(business_id, "legal", legal_msg.action, legal_msg.payload)

    if legal_msg.action == "legal_flagged":
        legal = legal_msg.payload
        flags = ", ".join(legal.get("flags", [])) or legal_msg.error
        logger.warning(f"[ceo] ⛔ Legal halt | flags: {flags}")
        return _fail(business_id, "legal", f"Legal flagged: {flags}")

    legal = legal_msg.payload
    logger.info(f"[ceo] ✓ Legal cleared | risk={legal['risk_level']}")

    # ── Step 4: Advertising Agent (Deepali) ───────────────────────────────────
    logger.info("[ceo] → Advertising Agent")
    from agents.advertising import run_advertising_agent

    # Use scraped image from Nimble data if available
    product_image_url = (nimble_data or {}).get("image_url")

    ads_msg = run_advertising_agent(
        product_name=product_name,
        category=research["category"],
        research_data=research,
        buyer_data=buyer,
        business_id=business_id,
        product_image_url=product_image_url,
        generate_image=False,  # Set True to call Stability/DALL-E
    )

    _log_decision(business_id, "advertising", ads_msg.action, ads_msg.payload)

    if ads_msg.action == "ads_failed":
        return _fail(business_id, "advertising", ads_msg.error)

    ads = ads_msg.payload
    logger.info(f"[ceo] ✓ Ads complete | name='{ads['product_name']}' | tagline='{ads['tagline']}'")

    # ── Step 5: Assemble Store Config ─────────────────────────────────────────
    slug = _slugify(ads["product_name"])

    store_config = {
        "store_id": business_id,
        "slug": slug,
        "store_url": f"https://{slug}.fastaisolution.com",
        "product_name": ads["product_name"],
        "description": ads["ad_copy"],
        "price": buyer["suggested_retail_price"],
        "hero_image_url": ads["hero_image_url"],
        "supplier": buyer["selected_supplier"]["name"],
        "cta_text": f"Buy Now — Ships in {buyer['selected_supplier'].get('shipping_days', 5)} days",
        # Extended fields for ClickHouse
        "category": research["category"],
        "trend_score": research["trend_score"],
        "margin_estimate": buyer["projected_margin"],
        "supplier_id": buyer["selected_supplier"].get("url", ""),
        "tagline": ads["tagline"],
        "seo_keywords": ads["seo_keywords"],
        "legal_risk_level": legal["risk_level"],
        # Full agent outputs for debugging/logging
        "_research": research,
        "_buyer": buyer,
        "_legal": legal,
        "_ads": ads,
    }

    elapsed = int((time.time() - pipeline_start) * 1000)
    logger.info(f"[ceo] 🏁 Pipeline complete | store={store_config['store_url']} | {elapsed}ms")

    _emit_store_metric(store_config)
    return store_config


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """Convert 'MagSnap Pro' → 'magsnap-pro'"""
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:40]  # DNS label limit


def _fail(business_id: str, stage: str, error: str) -> dict:
    logger.error(f"[ceo] ❌ Pipeline failed at {stage}: {error}")
    _log_decision(business_id, "ceo", "pipeline_failed", {"stage": stage, "error": error})
    return {"error": error, "stage": stage, "business_id": business_id}


def _log_decision(business_id: str, agent: str, action: str, payload: dict):
    """Write to ClickHouse agent_decisions table. No-ops if DB unavailable."""
    try:
        from db.clickhouse import insert_agent_decision
        insert_agent_decision(
            business_id=business_id,
            agent_name=agent,
            action=action,
            input_summary="",
            output_summary=str(payload)[:500],
            latency_ms=0,
            model_used="claude-opus-4-5",
        )
    except Exception:
        pass  # Don't let DB errors crash the pipeline


def _emit_store_metric(config: dict):
    try:
        from datadog import statsd
        statsd.gauge("stores.active_count", 1)
        statsd.increment("pipeline.completed", tags=[f"category:{config.get('category', 'unknown')}"])
    except ImportError:
        pass
