from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


class Settings:
    """Runtime settings loaded from environment variables."""

    PROJECT_NAME: str = "Quant Insight API"
    API_PREFIX: str = "/api"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{Path(__file__).resolve().parents[2] / 'quant_app.db'}",
    )
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]
    DATA_PROVIDER: str = os.getenv("DATA_PROVIDER", "auto")
    ALLOW_SAMPLE_FALLBACK: bool = _env_bool("ALLOW_SAMPLE_FALLBACK", False)
    LOG_DATA_PROVIDER_ERRORS: bool = _env_bool("LOG_DATA_PROVIDER_ERRORS", True)
    BUY_SIGNAL_KR_LIMIT: int = int(os.getenv("BUY_SIGNAL_KR_LIMIT", "100"))
    BUY_SIGNAL_US_LIMIT: int = int(os.getenv("BUY_SIGNAL_US_LIMIT", "100"))
    BUY_SIGNAL_BATCH_SIZE: int = int(os.getenv("BUY_SIGNAL_BATCH_SIZE", "10"))
    BUY_SIGNAL_MAX_WORKERS: int = int(os.getenv("BUY_SIGNAL_MAX_WORKERS", "5"))
    BUY_SIGNAL_ITEM_TIMEOUT_SECONDS: int = int(os.getenv("BUY_SIGNAL_ITEM_TIMEOUT_SECONDS", "25"))
    BUY_SIGNAL_REFRESH_SECONDS: int = int(os.getenv("BUY_SIGNAL_REFRESH_SECONDS", "60"))
    DATA_PROVIDER_TIMEOUT_SECONDS: int = int(os.getenv("DATA_PROVIDER_TIMEOUT_SECONDS", "12"))
    DATA_CACHE_TTL_SECONDS: int = int(os.getenv("DATA_CACHE_TTL_SECONDS", "60"))
    UNIVERSE_CACHE_TTL_SECONDS: int = int(os.getenv("UNIVERSE_CACHE_TTL_SECONDS", "3600"))
    SAMPLE_DATA_SEED: int = int(os.getenv("SAMPLE_DATA_SEED", "42"))
    # 백테스트용 (실거래 X — 외부 매매 앱 사용)
    COMMISSION_RATE: float = float(os.getenv("COMMISSION_RATE", "0.00015"))
    SLIPPAGE_RATE: float = float(os.getenv("SLIPPAGE_RATE", "0.0005"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
