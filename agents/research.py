"""
Research Agent — STUB for Dipesh to implement.
Deepali's orchestrator imports this; replace with real implementation.
"""
from agents.schemas import AgentMessage
import time

def run_research_agent(product_name: str, business_id: str, nimble_data: dict | None = None) -> AgentMessage:
    """
    TODO (Dipesh): Real implementation calls Nimble API and writes to ClickHouse trend_signals.
    This stub returns hardcoded data for ergokeyboard so Deepali can test her agents.
    """
    mock = {
        "product_name": product_name,
        "category": "electronics",
        "trend_score": 0.87,
        "search_volume": 45000,
        "social_mentions": 12000,
        "competitor_prices": [24.99, 34.99, 39.99],
        "estimated_margin": 0.45,
        "demand_signals": ["TikTok viral (#ergonomic 2.1M views)", "Reddit r/MechanicalKeyboards trending"],
    }
    time.sleep(0.5)  # simulate latency
    return AgentMessage.success("research", "ceo", "research_complete", mock, business_id)
