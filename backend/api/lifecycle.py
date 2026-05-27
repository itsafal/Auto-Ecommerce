from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.services.lifecycle import (
    evaluate_shutdown_candidates,
    promote_top_of_backlog,
    run_lifecycle_tick,
    shutdown_underperformers,
)

router = APIRouter(prefix="/api/lifecycle", tags=["lifecycle"])


@router.get("/candidates")
async def lifecycle_candidates() -> dict[str, Any]:
    return {
        "shutdown_candidates": [
            candidate.__dict__ for candidate in evaluate_shutdown_candidates()
        ]
    }


@router.post("/shutdown-underperformers")
async def lifecycle_shutdown_underperformers() -> dict[str, Any]:
    return {"shutdowns": shutdown_underperformers()}


@router.post("/promote")
async def lifecycle_promote() -> dict[str, Any]:
    return {"promotion": await promote_top_of_backlog()}


@router.post("/tick")
async def lifecycle_tick(promote: bool = True) -> dict[str, Any]:
    return await run_lifecycle_tick(promote=promote)
