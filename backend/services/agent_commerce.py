"""Agent-readable commerce manifests for generated storefronts."""

from __future__ import annotations

from typing import Any

from backend.schemas import StoreOutput


def build_agent_manifest(store: StoreOutput) -> dict[str, Any]:
    """Expose a compact product contract for shopping agents and catalog crawlers."""
    return {
        "schema_version": "2026-05-agent-commerce-v1",
        "type": "ProductOffer",
        "store": {
            "slug": store.slug,
            "url": store.store_url,
            "checkout_url": f"{store.store_url}#checkout",
        },
        "product": {
            "name": store.product_name,
            "description": store.description,
            "tagline": store.tagline,
            "image": store.hero_image_url,
            "price": {
                "amount": round(float(store.price), 2),
                "currency": "USD",
            },
            "supplier": store.supplier,
            "features": store.features,
            "specs": store.specs,
            "variants": [
                {
                    "name": variant.name,
                    "price": round(float(variant.price), 2),
                    "badge": variant.badge,
                    "description": variant.blurb,
                }
                for variant in store.variants
            ],
        },
        "policies": {
            "shipping": store.shipping_note,
            "returns": "30-day satisfaction guarantee",
            "support": "support@fastaisolution.com",
        },
        "actions": [
            {
                "name": "view_product",
                "method": "GET",
                "url": store.store_url,
            },
            {
                "name": "begin_checkout",
                "method": "GET",
                "url": f"{store.store_url}#checkout",
            },
        ],
        "json_ld": {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": store.product_name,
            "description": store.description,
            "image": store.hero_image_url,
            "offers": {
                "@type": "Offer",
                "price": round(float(store.price), 2),
                "priceCurrency": "USD",
                "availability": "https://schema.org/InStock",
                "url": store.store_url,
            },
        },
    }
