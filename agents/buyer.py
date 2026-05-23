"""
Buyer Agent — STUB for Dipesh to implement.
"""
from agents.schemas import AgentMessage
import time

def run_buyer_agent(product_name: str, research_data: dict, business_id: str) -> AgentMessage:
    """TODO (Dipesh): Real implementation queries supplier APIs."""
    mock = {
        "product_name": product_name,
        "selected_supplier": {
            "name": "AliExpress Seller #4821",
            "price": 12.50,
            "shipping_days": 7,
            "moq": 1,
            "url": "https://aliexpress.com/item/mock",
        },
        "all_suppliers": [],
        "unit_cost": 12.50,
        "suggested_retail_price": 34.99,
        "projected_margin": 0.64,
    }
    time.sleep(0.5)
    return AgentMessage.success("buyer", "ceo", "supplier_selected", mock, business_id)
