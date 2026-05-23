"""
A2A (Agent-to-Agent) Message Protocol
All inter-agent communication uses AgentMessage as the envelope.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

# ─── Agent Names ────────────────────────────────────────────────────────────
AgentName = Literal["ceo", "research", "buyer", "legal", "advertising"]

# ─── Action Types ────────────────────────────────────────────────────────────
ActionType = Literal[
    # Research agent
    "research_complete",
    "research_failed",
    # Buyer agent
    "supplier_selected",
    "buyer_failed",
    # Legal agent
    "legal_cleared",
    "legal_flagged",
    # Advertising agent
    "ads_complete",
    "ads_failed",
    # CEO orchestrator
    "launch_initiated",
    "store_live",
    "pipeline_failed",
]

# ─── Payload Schemas ─────────────────────────────────────────────────────────

@dataclass
class ResearchPayload:
    product_name: str
    category: str
    trend_score: float           # 0-1 from Nimble
    search_volume: int
    social_mentions: int
    competitor_prices: list[float]
    estimated_margin: float      # 0-1
    demand_signals: list[str]    # ["TikTok viral", "Reddit trending", ...]
    raw_nimble_data: dict = field(default_factory=dict)

@dataclass
class BuyerPayload:
    product_name: str
    selected_supplier: dict      # {name, price, shipping_days, moq, url}
    all_suppliers: list[dict]
    unit_cost: float
    suggested_retail_price: float
    projected_margin: float

@dataclass
class LegalPayload:
    product_name: str
    category: str
    cleared: bool
    flags: list[str]             # ["Possible trademark: 'MagSafe'", ...]
    recommendation: str
    risk_level: Literal["low", "medium", "high"]

@dataclass
class AdvertisingPayload:
    product_name: str            # Final polished name e.g. "MagSnap Pro"
    tagline: str
    ad_copy: str
    hero_image_prompt: str
    hero_image_url: str | None   # None until image generation completes
    features: list[str]          # Extracted from product images (multimodal)
    seo_keywords: list[str]

@dataclass
class StorePayload:
    slug: str
    store_url: str
    product_name: str
    description: str
    price: float
    hero_image_url: str | None
    supplier: str
    cta_text: str

# ─── Core Envelope ───────────────────────────────────────────────────────────

@dataclass
class AgentMessage:
    from_agent: AgentName
    to_agent: AgentName
    action: ActionType
    payload: dict                # Serialized payload dataclass
    business_id: str
    message_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: str | None = None     # Set on failure actions

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "action": self.action,
            "payload": self.payload,
            "business_id": self.business_id,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
        }

    @classmethod
    def success(
        cls,
        from_agent: AgentName,
        to_agent: AgentName,
        action: ActionType,
        payload: dict,
        business_id: str,
    ) -> "AgentMessage":
        return cls(from_agent=from_agent, to_agent=to_agent, action=action,
                   payload=payload, business_id=business_id)

    @classmethod
    def failure(
        cls,
        from_agent: AgentName,
        to_agent: AgentName,
        action: ActionType,
        business_id: str,
        error: str,
    ) -> "AgentMessage":
        return cls(from_agent=from_agent, to_agent=to_agent, action=action,
                   payload={}, business_id=business_id, error=error)
