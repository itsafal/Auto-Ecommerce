"""
Legal Agent — checks dropshipping compliance, trademark risk, import restrictions.
Called after Research + Buyer agents confirm a viable product.
"""

import json
import logging
import os
import time

import anthropic

from agents.schemas import AgentMessage, LegalPayload

logger = logging.getLogger(__name__)

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

DEMO_LEGAL_RESPONSE = {
    "cleared": True,
    "risk_level": "low",
    "flags": [],
    "recommendation": "Product is safe to sell via dropshipping. No known trademark conflicts.",
    "reasoning": "Generic consumer product with no identified trademark, regulatory, or platform policy risks.",
}

LEGAL_SYSTEM_PROMPT = """You are a legal compliance agent for an AI-powered e-commerce platform.

Your job: assess whether a product is safe to sell via dropshipping.

Check for:
1. **Trademark conflicts** — does the product name or description infringe on known brands?
   (e.g., "AirPods-style", "MagSafe compatible" claims, Nike-branded items)
2. **Dropshipping restrictions** — some brands explicitly prohibit resale (Apple, Dyson, etc.)
3. **Import/export regulations** — electronics, health products, weapons, chemicals have restrictions
4. **Platform policy risks** — items that PayPal/Stripe commonly freeze accounts for

Respond ONLY with a valid JSON object — no markdown, no explanation outside the JSON:
{
  "cleared": true/false,
  "risk_level": "low" | "medium" | "high",
  "flags": ["list of specific concerns, empty if none"],
  "recommendation": "One sentence action recommendation for the business operator",
  "reasoning": "2-3 sentences explaining your assessment"
}

Be pragmatic — most generic products are low risk. Only flag real, specific concerns.
If cleared=false, the pipeline will halt and not launch the store."""


def run_legal_agent(
    product_name: str,
    category: str,
    supplier_info: dict,
    business_id: str,
) -> AgentMessage:
    """
    Runs the legal compliance check via Claude.
    Returns an AgentMessage with action='legal_cleared' or 'legal_flagged'.
    """
    if DEMO_MODE or not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("[legal] DEMO_MODE or no ANTHROPIC_API_KEY — returning mock clearance")
        time.sleep(0.6)
        payload = LegalPayload(
            product_name=product_name,
            category=category,
            cleared=DEMO_LEGAL_RESPONSE["cleared"],
            flags=DEMO_LEGAL_RESPONSE["flags"],
            recommendation=DEMO_LEGAL_RESPONSE["recommendation"],
            risk_level=DEMO_LEGAL_RESPONSE["risk_level"],
        )
        return AgentMessage.success("legal", "ceo", "legal_cleared", payload.__dict__, business_id)

    client = anthropic.Anthropic()
    start = time.time()

    user_prompt = f"""
Product to assess:
- Name: {product_name}
- Category: {category}
- Supplier: {supplier_info.get('name', 'Unknown')} (sourced from {supplier_info.get('url', 'N/A')})
- Unit price: ${supplier_info.get('price', 0):.2f}

Assess this product for legal/compliance risk. Return JSON only.
""".strip()

    try:
        logger.info(f"[legal] Starting compliance check for: {product_name}")
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=[{"type": "text", "text": LEGAL_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = response.content[0].text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        latency_ms = int((time.time() - start) * 1000)

        payload = LegalPayload(
            product_name=product_name,
            category=category,
            cleared=result["cleared"],
            flags=result.get("flags", []),
            recommendation=result["recommendation"],
            risk_level=result["risk_level"],
        )

        action = "legal_cleared" if result["cleared"] else "legal_flagged"
        logger.info(f"[legal] {product_name}: {action} | risk={result['risk_level']} | {latency_ms}ms")

        # Log to Datadog if available
        _emit_metric(action, latency_ms, result["risk_level"])

        return AgentMessage.success(
            from_agent="legal",
            to_agent="ceo",
            action=action,
            payload=payload.__dict__,
            business_id=business_id,
        )

    except json.JSONDecodeError as e:
        logger.error(f"[legal] JSON parse failed: {e} | raw={raw[:200]}")
        return AgentMessage.failure(
            from_agent="legal",
            to_agent="ceo",
            action="legal_flagged",
            business_id=business_id,
            error=f"Could not parse compliance response: {e}",
        )
    except Exception as e:
        logger.error(f"[legal] Unexpected error: {e}")
        return AgentMessage.failure(
            from_agent="legal",
            to_agent="ceo",
            action="legal_flagged",
            business_id=business_id,
            error=str(e),
        )


def _emit_metric(action: str, latency_ms: int, risk_level: str):
    """Emit Datadog metrics — silently no-ops if datadog not installed."""
    try:
        from datadog import statsd
        statsd.increment("agent.decisions", tags=["agent:legal", f"action:{action}"])
        statsd.histogram("agent.latency_ms", latency_ms, tags=["agent:legal"])
        statsd.increment("legal.risk_level", tags=[f"level:{risk_level}"])
    except ImportError:
        pass
