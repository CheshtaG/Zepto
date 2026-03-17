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
    image_url: Optional[str] = None


class ProductComparison(BaseModel):
    product_name: str
    platforms: List[ProductInfo]
