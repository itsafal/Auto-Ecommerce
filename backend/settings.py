from __future__ import annotations

from dataclasses import dataclass
import os


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    use_temporal: bool = False
    use_agent_fixtures: bool = True
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "launch-store"
    base_domain: str = "fastaisolution.com"
    demo_mode: bool = True
    auth_secret: str = "dev-auth-secret-change-me"
    auth_token_ttl_minutes: int = 60 * 24 * 7
    agent_stream_delay_ms: int = 0
    # Secure default: production should require auth. Local dev and tests
    # explicitly disable via REQUIRE_AUTH_FOR_RUNS=false in their .env/conftest.
    require_auth_for_runs: bool = True
    google_api_key: str = ""
    # flash-lite has 1000 req/day free vs flash's 20 req/min, which matters
    # when the dashboard polls trending products on every mount.
    gemini_model: str = "gemini-2.5-flash-lite"
    portkey_api_key: str = ""
    portkey_base_url: str = "https://ai-gateway.apps.cloud.rt.nyu.edu/v1"
    portkey_model: str = "@vertexai/gemini-3.5-flash"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    # "auto" = try providers in order (portkey, anthropic, gemini) based on which
    # keys are set. Override with "anthropic" | "portkey" | "gemini" to force one.
    llm_provider: str = "auto"
    # Batch deployment defaults — operator can override per request.
    launch_score_threshold: float = 0.55
    batch_target_count: int = 5
    # DEPRECATED (plan 04): superseded by attempts_per_product + max_products_per_slot.
    # Kept so old env vars don't crash; ignored by the new retry loop.
    batch_max_attempts_per_slot: int = 5
    # New per-slot retry policy (plan 04):
    #   - Each product gets `attempts_per_product` chances (LLM-noise retries).
    #   - On full failure, swap to a new product. Slot keeps trying until a
    #     winner lands or `max_products_per_slot` distinct products fail.
    #   - If attempt 1 scores below `fast_fail_threshold`, skip attempt 2.
    #   - Initial candidate pool size = count * candidate_pool_multiplier.
    attempts_per_product: int = 2
    max_products_per_slot: int = 10
    candidate_pool_multiplier: int = 4
    fast_fail_threshold: float = 0.40
    # Dedup window: never re-attempt a product researched in the last N days.
    # Set to 0 to disable dedup (e.g. for testing or demos that re-use products).
    dedup_window_days: int = 7
    # Max concurrently live stores. Surfaced in the UI now; enforced when the
    # autonomous lifecycle loop ships (Phase E foundation only in this PR).
    max_concurrent_live: int = 5
    lifecycle_grace_days: float = 1.0
    lifecycle_min_revenue_24h: float = 10.0
    lifecycle_min_conversion_rate: float = 0.005
    nimble_api_key: str = ""
    nimble_api_url: str = ""


def get_settings() -> Settings:
    return Settings(
        use_temporal=_env_bool("USE_TEMPORAL", False),
        use_agent_fixtures=_env_bool("USE_AGENT_FIXTURES", True),
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        temporal_namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
        temporal_task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "launch-store"),
        base_domain=os.getenv("BASE_DOMAIN", "fastaisolution.com"),
        demo_mode=_env_bool("DEMO_MODE", True),
        auth_secret=os.getenv("AUTH_SECRET", "dev-auth-secret-change-me"),
        auth_token_ttl_minutes=int(os.getenv("AUTH_TOKEN_TTL_MINUTES", str(60 * 24 * 7))),
        agent_stream_delay_ms=int(os.getenv("AGENT_STREAM_DELAY_MS", "0")),
        require_auth_for_runs=_env_bool("REQUIRE_AUTH_FOR_RUNS", True),
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        portkey_api_key=os.getenv("PORTKEY_API_KEY", ""),
        portkey_base_url=os.getenv("PORTKEY_BASE_URL", "https://ai-gateway.apps.cloud.rt.nyu.edu/v1"),
        portkey_model=os.getenv("PORTKEY_MODEL", "@vertexai/gemini-3.5-flash"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        llm_provider=(os.getenv("LLM_PROVIDER", "auto") or "auto").strip().lower(),
        launch_score_threshold=float(os.getenv("LAUNCH_SCORE_THRESHOLD", "0.55")),
        batch_target_count=int(os.getenv("BATCH_TARGET_COUNT", "5")),
        batch_max_attempts_per_slot=int(os.getenv("BATCH_MAX_ATTEMPTS_PER_SLOT", "5")),
        attempts_per_product=int(os.getenv("ATTEMPTS_PER_PRODUCT", "2")),
        max_products_per_slot=int(os.getenv("MAX_PRODUCTS_PER_SLOT", "10")),
        candidate_pool_multiplier=int(os.getenv("CANDIDATE_POOL_MULTIPLIER", "4")),
        fast_fail_threshold=float(os.getenv("FAST_FAIL_THRESHOLD", "0.40")),
        dedup_window_days=int(os.getenv("DEDUP_WINDOW_DAYS", "7")),
        max_concurrent_live=int(os.getenv("MAX_CONCURRENT_LIVE", "5")),
        lifecycle_grace_days=float(os.getenv("LIFECYCLE_GRACE_DAYS", "1.0")),
        lifecycle_min_revenue_24h=float(os.getenv("LIFECYCLE_MIN_REVENUE_24H", "10.0")),
        lifecycle_min_conversion_rate=float(os.getenv("LIFECYCLE_MIN_CONVERSION_RATE", "0.005")),
        nimble_api_key=os.getenv("NIMBLE_API_KEY", ""),
        nimble_api_url=os.getenv("NIMBLE_API_URL", ""),
    )
