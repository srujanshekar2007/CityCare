"""Environment-backed configuration shared by API and model code."""

import os
from dataclasses import dataclass
from typing import Optional


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw in (None, "") else float(raw)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw in (None, "") else int(raw)


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("ML_HOST", "127.0.0.1")
    port: int = _int_env("ML_PORT", 8001)
    service_token: Optional[str] = os.getenv("ML_SERVICE_TOKEN") or None
    allowed_origins: tuple = tuple(
        origin.strip()
        for origin in os.getenv("ML_ALLOWED_ORIGINS", "http://localhost:4000").split(",")
        if origin.strip()
    )
    semantic_enabled: bool = os.getenv("CITYCARE_ENABLE_SEMANTIC", "false").lower() == "true"
    semantic_model: str = os.getenv(
        "CITYCARE_SEMANTIC_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    semantic_cache_size: int = _int_env("CITYCARE_SEMANTIC_CACHE_SIZE", 2048)
    max_candidates: int = _int_env("CITYCARE_DUPLICATE_MAX_CANDIDATES", 250)
    temporal_half_life_days: float = _float_env("CITYCARE_TEMPORAL_HALF_LIFE_DAYS", 180.0)
    geo_scale_meters: float = _float_env("CITYCARE_GEO_PROXIMITY_SCALE_METERS", 1200.0)
    hotspot_epsilon_meters: float = _float_env("CITYCARE_HOTSPOT_EPSILON_METERS", 500.0)
    hotspot_min_samples: int = _int_env("CITYCARE_HOTSPOT_MIN_SAMPLES", 3)
    high_threshold: Optional[float] = (
        float(os.environ["CITYCARE_DUPLICATE_HIGH_THRESHOLD"])
        if os.getenv("CITYCARE_DUPLICATE_HIGH_THRESHOLD")
        else None
    )
    possible_threshold: Optional[float] = (
        float(os.environ["CITYCARE_DUPLICATE_POSSIBLE_THRESHOLD"])
        if os.getenv("CITYCARE_DUPLICATE_POSSIBLE_THRESHOLD")
        else None
    )


settings = Settings()
