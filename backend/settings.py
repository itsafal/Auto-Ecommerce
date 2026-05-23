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
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "launch-store"
    base_domain: str = "fastaisolution.com"
    demo_mode: bool = True
    auth_secret: str = "dev-auth-secret-change-me"
    auth_token_ttl_minutes: int = 60 * 24 * 7


def get_settings() -> Settings:
    return Settings(
        use_temporal=_env_bool("USE_TEMPORAL", False),
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        temporal_namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
        temporal_task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "launch-store"),
        base_domain=os.getenv("BASE_DOMAIN", "fastaisolution.com"),
        demo_mode=_env_bool("DEMO_MODE", True),
        auth_secret=os.getenv("AUTH_SECRET", "dev-auth-secret-change-me"),
        auth_token_ttl_minutes=int(os.getenv("AUTH_TOKEN_TTL_MINUTES", str(60 * 24 * 7))),
    )
