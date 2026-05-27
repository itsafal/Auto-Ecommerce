from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.api.businesses import _portfolio_runs
from backend.services.intelligence import (
    category_leaderboard,
    portfolio_intelligence,
    similarity_map,
    supplier_network,
)

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


@router.get("")
async def get_intelligence() -> dict[str, Any]:
    return portfolio_intelligence(_portfolio_runs())


@router.get("/similarity-map")
async def get_similarity_map() -> dict[str, Any]:
    return similarity_map(_portfolio_runs())


@router.get("/supplier-network")
async def get_supplier_network() -> dict[str, Any]:
    return supplier_network(_portfolio_runs())


@router.get("/category-leaderboard")
async def get_category_leaderboard() -> list[dict[str, Any]]:
    return category_leaderboard(_portfolio_runs())
