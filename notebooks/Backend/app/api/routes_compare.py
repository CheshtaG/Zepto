from fastapi import APIRouter, Depends, Request
from models import ProductComparison
from app.core.config import get_settings
from app.services.comparison import ComparisonService


router = APIRouter()



def get_comparison_service(request: Request) -> ComparisonService:
    # Keep business logic clean: fetch the shared service from app.state instead
    # of importing from `app.main` (which creates unnecessary coupling).
    return request.app.state.comparison_service  # type: ignore[attr-defined]


@router.get("/")
async def root():
    settings = get_settings()
    return {"message": settings.app_name, "version": settings.app_version}


@router.get("/compare", response_model=ProductComparison)
async def compare_product(product: str, svc: ComparisonService = Depends(get_comparison_service)):
    """Compare a single product across all platforms."""
    return await svc.compare_product(product)


@router.get("/health")
async def health_check():
    return {"status": "healthy"}

