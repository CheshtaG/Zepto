from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class Platform(str, Enum):
    INSTAMART = "instamart"
    BLINKIT = "blinkit"
    ZEPTO = "zepto"


class ProductInfo(BaseModel):
    platform: Platform
    price: Optional[float] = None
    availability: bool = False
    error: Optional[str] = None
    product_url: Optional[str] = None
    # Visible product title on the listing card (as shown on that app).
    listing_title: Optional[str] = None
    image_url: Optional[str] = None
    image_source: Optional[str] = None
    image_confidence: Optional[float] = None
    image_match_reason: Optional[str] = None
    image_debug: Optional[dict] = None
    # Local screenshot path (used for vision analysis; optional in API consumers)
    screenshot_path: Optional[str] = None
    # How price was extracted in scraper (e.g. dom, ocr, dom_fallback_after_ocr).
    price_extraction_method: Optional[str] = None
    # Quantity-normalized comparison (filled after Gemini vision pass when API key is set)
    quantity_label: Optional[str] = None
    quantity_base_value: Optional[float] = None
    quantity_base_unit: Optional[str] = None
    price_per_base_unit: Optional[float] = None
    quantity_comparable: Optional[bool] = None
    quantity_comparison_note: Optional[str] = None
    # Top search-result cards for cross-platform matching (DOM, best-effort).
    candidate_listings: Optional[List[dict]] = None


class ProductComparison(BaseModel):
    product_name: str
    platforms: List[ProductInfo]
