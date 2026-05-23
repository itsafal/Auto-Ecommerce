"""
Advertising Agent — generates product name, tagline, ad copy, image prompt.
Also does multimodal feature extraction from product images (Claude vision).
"""

import base64
import json
import logging
import os
import time
from pathlib import Path

import anthropic
import httpx

from agents.schemas import AgentMessage, AdvertisingPayload

logger = logging.getLogger(__name__)

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

# ─── Prompts ──────────────────────────────────────────────────────────────────

ADVERTISING_SYSTEM_PROMPT = """You are a world-class e-commerce copywriter and brand strategist.

Given a product, you create:
1. A polished, marketable product name (not the generic supplier name)
2. A punchy tagline (≤ 8 words, no exclamation marks — confidence, not hype)
3. Ad copy (2-3 sentences, benefit-focused, skimmable)
4. An image generation prompt for a hero product photo
5. SEO keywords (5-8 keywords)

Respond ONLY with a valid JSON object — no markdown, no preamble:
{
  "product_name": "...",
  "tagline": "...",
  "ad_copy": "...",
  "hero_image_prompt": "professional product photography of [item], white background, studio lighting, 4k, commercial quality",
  "seo_keywords": ["keyword1", "keyword2", ...]
}

Rules:
- product_name: Catchy, brandable. Can be a real word, portmanteau, or initialism. No generic names like "Premium Mount Pro 3000".
- tagline: No verbs like "Elevate", "Transform", "Revolutionize". Be specific and clever.
- ad_copy: Lead with the #1 user benefit. No fluff. No "game-changing".
- hero_image_prompt: Be specific about the product appearance and style."""


FEATURE_EXTRACTION_SYSTEM = """You are a product analyst. Given a product image, extract:
1. Key visual features (materials, colors, shape, size indicators)
2. Apparent use cases
3. Quality signals (premium, budget, mid-range)
4. Potential selling points visible in the image

Respond ONLY with valid JSON:
{
  "features": ["feature1", "feature2", ...],
  "use_cases": ["use case 1", ...],
  "quality_tier": "budget" | "mid-range" | "premium",
  "selling_points": ["point1", "point2", ...]
}"""


# ─── Image Feature Extraction (Multimodal) ────────────────────────────────────

def extract_features_from_image(image_url: str | None, image_path: str | None = None) -> dict:
    """
    Uses Claude vision to extract product features from an image.
    Accepts either a URL or a local file path.
    Returns dict with features, use_cases, quality_tier, selling_points.
    """
    if not image_url and not image_path:
        return {"features": [], "use_cases": [], "quality_tier": "mid-range", "selling_points": []}

    client = anthropic.Anthropic()

    try:
        # Load image as base64
        if image_path:
            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")
            media_type = _infer_media_type(image_path)
        else:
            # Fetch from URL
            resp = httpx.get(image_url, timeout=10, follow_redirects=True)
            resp.raise_for_status()
            image_data = base64.standard_b64encode(resp.content).decode("utf-8")
            media_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=FEATURE_EXTRACTION_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": "Extract product features from this image. Return JSON only."},
                    ],
                }
            ],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw.strip())
        logger.info(f"[advertising] Extracted {len(result.get('features', []))} features from image")
        return result

    except Exception as e:
        logger.warning(f"[advertising] Image feature extraction failed: {e}")
        return {"features": [], "use_cases": [], "quality_tier": "mid-range", "selling_points": []}


def _infer_media_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp", "gif": "image/gif"}.get(ext.lstrip("."), "image/jpeg")


# ─── Main Advertising Agent ───────────────────────────────────────────────────

def run_advertising_agent(
    product_name: str,
    category: str,
    research_data: dict,
    buyer_data: dict,
    business_id: str,
    product_image_url: str | None = None,
    generate_image: bool = False,
) -> AgentMessage:
    """
    Generates all advertising assets for a product.
    Optionally extracts features from a product image (multimodal).
    """
    client = anthropic.Anthropic()
    start = time.time()

    # Step 1: Multimodal feature extraction (if image available)
    image_features = {}
    if product_image_url:
        logger.info(f"[advertising] Extracting features from image: {product_image_url[:60]}...")
        image_features = extract_features_from_image(image_url=product_image_url)

    # Step 2: Build context-rich prompt for ad generation
    features_context = ""
    if image_features.get("features"):
        features_context = f"\nImage analysis revealed: {', '.join(image_features['features'][:5])}"
        if image_features.get("selling_points"):
            features_context += f"\nKey selling points from image: {', '.join(image_features['selling_points'][:3])}"

    user_prompt = f"""
Product: {product_name}
Category: {category}
Retail price: ${buyer_data.get('suggested_retail_price', 29.99):.2f}
Demand signals: {', '.join(research_data.get('demand_signals', [])[:3])}
Competitor price range: ${min(research_data.get('competitor_prices', [25]), default=25):.2f} – ${max(research_data.get('competitor_prices', [50]), default=50):.2f}
{features_context}

Generate advertising assets. Return JSON only.
""".strip()

    if DEMO_MODE or not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("[advertising] DEMO_MODE or no ANTHROPIC_API_KEY — returning mock ad copy")
        time.sleep(0.8)
        slug_name = product_name.title().replace(" ", "") + " Pro"
        payload = AdvertisingPayload(
            product_name=slug_name,
            tagline=f"The smarter way to use {product_name}.",
            ad_copy=(
                f"Engineered for people who expect more. {slug_name} delivers the performance "
                f"you need at a price that makes sense. Order today and see why customers love it."
            ),
            hero_image_prompt=(
                f"professional product photography of {product_name}, white background, "
                f"studio lighting, 4k, commercial quality"
            ),
            hero_image_url=product_image_url,
            features=image_features.get("features", []),
            seo_keywords=[product_name, f"best {product_name}", f"buy {product_name}", f"{product_name} review"],
        )
        return AgentMessage.success("advertising", "ceo", "ads_complete", payload.__dict__, business_id)

    try:
        logger.info(f"[advertising] Generating ads for: {product_name}")
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            system=[{"type": "text", "text": ADVERTISING_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())

        # Step 3: Generate hero image if requested
        hero_image_url = product_image_url  # fallback to scraped image
        if generate_image:
            hero_image_url = _generate_hero_image(result["hero_image_prompt"]) or hero_image_url

        latency_ms = int((time.time() - start) * 1000)

        # Merge image-extracted features with generated features
        all_features = list(set(
            image_features.get("features", []) +
            image_features.get("selling_points", [])
        ))

        payload = AdvertisingPayload(
            product_name=result["product_name"],
            tagline=result["tagline"],
            ad_copy=result["ad_copy"],
            hero_image_prompt=result["hero_image_prompt"],
            hero_image_url=hero_image_url,
            features=all_features,
            seo_keywords=result.get("seo_keywords", []),
        )

        logger.info(f"[advertising] Done: '{result['product_name']}' | '{result['tagline']}' | {latency_ms}ms")
        _emit_metric(latency_ms)

        return AgentMessage.success(
            from_agent="advertising",
            to_agent="ceo",
            action="ads_complete",
            payload=payload.__dict__,
            business_id=business_id,
        )

    except json.JSONDecodeError as e:
        logger.error(f"[advertising] JSON parse failed: {e}")
        return AgentMessage.failure(
            from_agent="advertising",
            to_agent="ceo",
            action="ads_failed",
            business_id=business_id,
            error=f"Ad generation parse error: {e}",
        )
    except Exception as e:
        logger.error(f"[advertising] Error: {e}")
        return AgentMessage.failure(
            from_agent="advertising",
            to_agent="ceo",
            action="ads_failed",
            business_id=business_id,
            error=str(e),
        )


def _generate_hero_image(prompt: str) -> str | None:
    """
    Calls DALL-E 3 to generate a hero product image.
    Returns a temporary OpenAI CDN URL (valid ~1 hour) or None on failure.
    Set OPENAI_API_KEY in the environment before calling.
    """
    try:
        import openai
        client = openai.OpenAI()
        logger.info(f"[advertising] Generating image via DALL-E 3 (prompt: {prompt[:60]}...)")
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        url = response.data[0].url
        logger.info(f"[advertising] DALL-E 3 image ready: {url[:60]}...")
        return url
    except ImportError:
        logger.warning("[advertising] openai package not installed — skipping image generation")
        return None
    except Exception as e:
        logger.warning(f"[advertising] DALL-E generation failed: {e}")
        return None


def _emit_metric(latency_ms: int):
    try:
        from datadog import statsd
        statsd.increment("agent.decisions", tags=["agent:advertising"])
        statsd.histogram("agent.latency_ms", latency_ms, tags=["agent:advertising"])
    except ImportError:
        pass
