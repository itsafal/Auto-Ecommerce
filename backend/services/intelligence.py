"""Portfolio intelligence projections.

This is the read model that the future pgvector knowledge graph can replace.
For now it derives clusters, supplier fanout, and category stats from the
existing portfolio so the frontend and agents have stable contracts.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from backend.schemas import LaunchRun
from backend.store import run_store


def infer_category(product_name: str) -> str:
    name = product_name.lower()
    if any(token in name for token in ("phone", "charger", "earbud", "camera", "projector")):
        return "electronics"
    if any(token in name for token in ("posture", "massager", "fitness", "sleep")):
        return "health"
    if any(token in name for token in ("pet", "dog", "cat")):
        return "pets"
    if any(token in name for token in ("kitchen", "bottle", "cleaner")):
        return "home"
    return "general"


def _tokens(value: str) -> set[str]:
    return {token for token in value.lower().replace("-", " ").split() if len(token) > 2}


def similarity(a: LaunchRun, b: LaunchRun) -> float:
    left = _tokens(a.product_name)
    right = _tokens(b.product_name)
    if not left or not right:
        return 0.0
    overlap = len(left & right) / len(left | right)
    if infer_category(a.product_name) == infer_category(b.product_name):
        overlap += 0.25
    return round(min(overlap, 1.0), 4)


def similarity_map(runs: list[LaunchRun]) -> dict[str, Any]:
    nodes = []
    edges = []
    for index, run in enumerate(runs):
        category = infer_category(run.product_name)
        nodes.append(
            {
                "id": str(run.run_id),
                "slug": run.slug,
                "label": run.product_name,
                "category": category,
                "score": run.launch_score or 0.0,
                "x": (index % 5) * 140,
                "y": (index // 5) * 100 + (hash(category) % 30),
            }
        )
    for i, left in enumerate(runs):
        for right in runs[i + 1:]:
            weight = similarity(left, right)
            if weight >= 0.25:
                edges.append(
                    {
                        "source": str(left.run_id),
                        "target": str(right.run_id),
                        "relation": "SIMILAR_TO",
                        "weight": weight,
                    }
                )
    return {"nodes": nodes, "edges": edges}


def supplier_network(runs: list[LaunchRun]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for run in runs:
        store = run_store.get_store(run.slug)
        supplier = store.supplier if store is not None else "unknown_supplier"
        supplier_id = f"supplier:{supplier.lower().replace(' ', '_')}"
        nodes.setdefault(
            supplier_id,
            {"id": supplier_id, "label": supplier, "type": "supplier", "fanout": 0},
        )
        nodes[supplier_id]["fanout"] += 1
        business_id = f"business:{run.slug}"
        nodes[business_id] = {
            "id": business_id,
            "label": run.product_name,
            "type": "business",
            "score": run.launch_score or 0.0,
        }
        edges.append(
            {
                "source": supplier_id,
                "target": business_id,
                "relation": "SOURCED_FROM",
                "weight": 1.0,
            }
        )
    return {"nodes": list(nodes.values()), "edges": edges}


def category_leaderboard(runs: list[LaunchRun]) -> list[dict[str, Any]]:
    groups: dict[str, list[LaunchRun]] = defaultdict(list)
    for run in runs:
        groups[infer_category(run.product_name)].append(run)

    rows = []
    for category, items in groups.items():
        live = [run for run in items if run.business_status == "live"]
        shutdown = [run for run in items if run.business_status == "shutdown"]
        avg_score = sum(run.launch_score or 0.0 for run in items) / len(items)
        rows.append(
            {
                "category": category,
                "total": len(items),
                "live": len(live),
                "shutdown": len(shutdown),
                "hit_rate": round(len(live) / len(items), 3) if items else 0.0,
                "avg_launch_score": round(avg_score, 4),
                "top_product": max(items, key=lambda run: run.launch_score or 0.0).product_name,
            }
        )
    rows.sort(key=lambda row: (row["hit_rate"], row["avg_launch_score"]), reverse=True)
    return rows


def portfolio_intelligence(runs: list[LaunchRun]) -> dict[str, Any]:
    return {
        "data_source": "derived_from_launch_runs",
        "similarity_map": similarity_map(runs),
        "supplier_network": supplier_network(runs),
        "category_leaderboard": category_leaderboard(runs),
    }
