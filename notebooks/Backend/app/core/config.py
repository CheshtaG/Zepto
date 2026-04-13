from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env from notebooks/Backend regardless of process cwd (uvicorn, IDE, etc.).
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables with defaults."""

    app_name: str = "Product Comparison API"
    app_version: str = "1.0.0"

    instamart_search_url: AnyHttpUrl = (
        "https://www.swiggy.com/instamart/search?custom_back=true&query="
    )
    blinkit_search_url: AnyHttpUrl = "https://blinkit.com/s/?q="
    zepto_search_url: AnyHttpUrl = "https://www.zepto.com/search?query="

    default_location: str = "Pune"
    default_pincode: str = "411001"

    page_load_timeout_ms: int = 30000
    element_wait_timeout_ms: int = 5000
    search_delay_seconds: int = 2

    cache_expiry_minutes: int = 15
    cache_expiry_hours: int = 24  # legacy; file-cache uses notebooks/Backend/config.py

    data_dir: str = "/Users/cheshtagupta17/Data - Cheshta/Projects/Zepto/data"

    # Google AI (Gemini) — set COMPARE_GOOGLE_API_KEY in .env; never commit real keys.
    google_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"
    # After first pass, propose one search string for all platforms (same SKU / pack size).
    gemini_match_model: str = "gemini-2.0-flash-lite"
    enable_cross_platform_match: bool = True
    # Gemini quantity/vision pass is slow; keep it off by default so prices return quickly.
    # Set COMPARE_ENABLE_GEMINI_QUANTITY=1 to enable.
    enable_gemini_quantity: bool = False
    # When DOM misses Instamart price but a fallback screenshot exists, one small Gemini call
    # reads the first card price (no full 3-image quantity pass). Requires COMPARE_GOOGLE_API_KEY.
    enable_gemini_instamart_price_fallback: bool = True
    # Product image resolution: use Gemini + Google Search only after DOM-card extraction fails/low confidence.
    enable_gemini_image_fallback: bool = True

    # Concurrent shopping-list items per job (each item runs 3 scrapers in parallel).
    job_max_concurrent_items: int = 2

    model_config = SettingsConfigDict(
        env_prefix="COMPARE_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance so we don't re-parse on every request."""
    return Settings()

