from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.auth import router as auth_router
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
    return app


app = create_app()
