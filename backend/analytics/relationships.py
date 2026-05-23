"""Relationship generator — turns the businesses table into a knowledge graph.

For each pair of businesses we emit zero or more edges in the
business_relationships table:

  shared_category   weight = 1.0
  shared_supplier   weight = 1.0
  similar_margin    weight = 1 - normalized_distance   (only if within MARGIN_TOLERANCE)
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Iterable

MARGIN_TOLERANCE = 0.10  # absolute margin distance to be considered "similar"


@dataclass(frozen=True)
class Relationship:
    from_business_id: str
    to_business_id: str
    relationship_type: str
    weight: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_business_id": self.from_business_id,
            "to_business_id": self.to_business_id,
            "relationship_type": self.relationship_type,
            "weight": round(self.weight, 4),
            "reason": self.reason,
        }


def _normalize_supplier(business: dict[str, Any]) -> str:
    """Suppliers might be tracked by id or by name; use whichever is present."""
    return (business.get("supplier_id") or business.get("supplier_name") or "").strip()


def _pair_edges(a: dict[str, Any], b: dict[str, Any]) -> list[Relationship]:
    """Emit one or both directions of every relationship that applies to (a, b)."""
    edges: list[Relationship] = []
    a_id = str(a.get("id", ""))
    b_id = str(b.get("id", ""))
    if not a_id or not b_id:
        return edges

    category_a = a.get("category", "")
    category_b = b.get("category", "")
    if category_a and category_a == category_b:
        reason = f"Both operate in category '{category_a}'."
        edges.append(Relationship(a_id, b_id, "shared_category", 1.0, reason))
        edges.append(Relationship(b_id, a_id, "shared_category", 1.0, reason))

    supplier_a = _normalize_supplier(a)
    supplier_b = _normalize_supplier(b)
    if supplier_a and supplier_a == supplier_b:
        reason = f"Both source from supplier '{supplier_a}'."
        edges.append(Relationship(a_id, b_id, "shared_supplier", 1.0, reason))
        edges.append(Relationship(b_id, a_id, "shared_supplier", 1.0, reason))

    margin_a = a.get("margin_estimate")
    margin_b = b.get("margin_estimate")
    if margin_a is not None and margin_b is not None:
        distance = abs(float(margin_a) - float(margin_b))
        if distance <= MARGIN_TOLERANCE:
            weight = 1.0 - (distance / MARGIN_TOLERANCE if MARGIN_TOLERANCE else 0.0)
            reason = (
                f"Margins {float(margin_a):.2f} and {float(margin_b):.2f} differ by only {distance:.2f}."
            )
            edges.append(Relationship(a_id, b_id, "similar_margin", weight, reason))
            edges.append(Relationship(b_id, a_id, "similar_margin", weight, reason))

    return edges


def build_relationships(businesses: Iterable[dict[str, Any]]) -> list[Relationship]:
    """Generate every edge implied by the businesses list."""
    edges: list[Relationship] = []
    business_list = list(businesses)
    for a, b in combinations(business_list, 2):
        edges.extend(_pair_edges(a, b))
    return edges
