from functools import lru_cache
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables with defaults."""

    app_name: str = "Product Comparison API"
    app_version: str = "1.0.0"

    # External service/base URLs – keep defaults aligned with existing config.py
    instamart_url: AnyHttpUrl = "https://www.swiggy.com/instamart"
    blinkit_url: AnyHttpUrl = "https://blinkit.com"
    zepto_url: AnyHttpUrl = "https://www.zepto.com"

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

    cache_expiry_hours: int = 24

    data_dir: str = "/Users/cheshtagupta17/Data - Cheshta/Projects/Shopping Made Easy/data"

    class Config:
        env_prefix = "COMPARE_"
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance so we don't re-parse on every request."""
    return Settings()

