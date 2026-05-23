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
    require_auth_for_runs: bool = False
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
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
        require_auth_for_runs=_env_bool("REQUIRE_AUTH_FOR_RUNS", False),
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        nimble_api_key=os.getenv("NIMBLE_API_KEY", ""),
        nimble_api_url=os.getenv("NIMBLE_API_URL", ""),
    )
