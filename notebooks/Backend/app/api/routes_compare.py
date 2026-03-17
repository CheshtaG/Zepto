from fastapi import APIRouter, Depends
from models import ProductComparison
from app.core.config import get_settings
from app.services.comparison import ComparisonService


router = APIRouter()

DEFAULT_PRODUCTS = ["Milk", "Bread", "Eggs", "Rice", "Tomatoes", "Onions"]


def get_comparison_service() -> ComparisonService:
    # This will be overridden in app.main using app.state, but keeps type hints clear.
    from app.main import comparison_service  # type: ignore

    return comparison_service


@router.get("/")
async def root():
    settings = get_settings()
    return {"message": settings.app_name, "version": settings.app_version}


@router.get("/compare", response_model=ProductComparison)
async def compare_product(product: str, svc: ComparisonService = Depends(get_comparison_service)):
    """Compare a single product across all platforms."""
    return await svc.compare_product(product)


@router.get("/products")
async def get_default_products():
    return {"products": DEFAULT_PRODUCTS}


@router.get("/health")
async def health_check():
    return {"status": "healthy"}

