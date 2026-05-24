from __future__ import annotations

import os
from pathlib import Path

# Auto-load .env from the project root so `uv run uvicorn ...` and any
# direct python entry point picks up local secrets without `set -a; source .env`.
# Existing process env vars win — we don't override what's already set. Skipped
# under pytest so tests use their own controlled environment.
import sys as _sys

if "pytest" not in _sys.modules and not os.environ.get("DISABLE_DOTENV_AUTOLOAD"):
    try:
        from dotenv import load_dotenv

        _ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
        if _ENV_PATH.exists():
            load_dotenv(_ENV_PATH, override=False)
    except ImportError:  # python-dotenv not installed (e.g. minimal CI)
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.admin import router as admin_router
from backend.api.auth import router as auth_router
from backend.api.businesses import router as businesses_router
from backend.api.runs import router as runs_router

# Localhost-only for now. When we deploy fastaisolution.com, uncomment the
# entries below (and the regex) to allow prod + wildcard subdomain origins.
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # "https://fastaisolution.com",
    # "https://www.fastaisolution.com",
]

# Matches https://<anything>.fastaisolution.com and onrender preview URLs.
# DEFAULT_ALLOWED_ORIGIN_REGEX = (
#     r"^https://([a-z0-9-]+\.)*fastaisolution\.com$"
#     r"|^https://[a-z0-9-]+\.onrender\.com$"
# )
DEFAULT_ALLOWED_ORIGIN_REGEX = None


def create_app() -> FastAPI:
    app = FastAPI(title="Auto-Ecommerce API")

    extra_origins = [
        origin.strip()
        for origin in os.getenv("CORS_EXTRA_ORIGINS", "").split(",")
        if origin.strip()
    ]
    allow_origins = DEFAULT_ALLOWED_ORIGINS + extra_origins
    allow_origin_regex = os.getenv("CORS_ORIGIN_REGEX", DEFAULT_ALLOWED_ORIGIN_REGEX)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_origin_regex=allow_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(runs_router)
    app.include_router(admin_router)
    app.include_router(businesses_router)
    return app


app = create_app()
