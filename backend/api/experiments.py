from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.api.businesses import _portfolio_runs
from backend.services.experiments import build_experiment_plan, summarize_portfolio_experiments

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("/plan/{slug}")
async def get_experiment_plan(slug: str, daily_budget: float = 50.0) -> dict[str, Any]:
    run = next((item for item in _portfolio_runs() if item.slug == slug), None)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No launched business for slug {slug!r}")
    return build_experiment_plan(run, daily_budget=daily_budget)


@router.get("/portfolio")
async def get_portfolio_experiments(daily_budget: float = 50.0) -> dict[str, Any]:
    live_runs = [run for run in _portfolio_runs() if run.business_status == "live"]
    return summarize_portfolio_experiments(live_runs, daily_budget=daily_budget)
