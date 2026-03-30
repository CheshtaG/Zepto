import asyncio
from typing import Any, Dict, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request

from app.schemas.jobs import (
    CreateJobRequest,
    AddItemsRequest,
    ClarifyItemsRequest,
    ClarifyItemsResponse,
    JobStatusResponse,
    JobResultResponse,
    ChatRequest,
    ChatResponse,
    LocationPayload,
)
from app.core.config import get_settings
from app.services.item_clarifier import clarify_items_with_llm
from app.services.comparison import JobManager
from app.services.location import (
    extract_client_ip,
    lookup_location_by_ip,
    reverse_geocode_lat_lng,
)


router = APIRouter()


def _normalize_location_input(
    payload_location: Optional[Union[LocationPayload, str]], request: Request
) -> Optional[LocationPayload]:
    # Structured location from frontend (preferred).
    if isinstance(payload_location, LocationPayload):
        loc = payload_location
        if loc.lat is not None and loc.lng is not None and (not loc.city or not loc.pincode):
            geo = reverse_geocode_lat_lng(loc.lat, loc.lng)
            if geo:
                return LocationPayload(
                    name=loc.name or geo.get("label"),
                    city=loc.city or geo.get("city"),
                    pincode=loc.pincode or geo.get("pincode"),
                    lat=loc.lat,
                    lng=loc.lng,
                    source=loc.source or "geolocation",
                )
        return loc

    # Backward-compatible plain string location.
    if isinstance(payload_location, str) and payload_location.strip():
        return LocationPayload(name=payload_location.strip(), source="manual")

    # Automatic fallback by client IP.
    ip = extract_client_ip(dict(request.headers), request.client.host if request.client else None)
    by_ip = lookup_location_by_ip(ip)
    if by_ip:
        return LocationPayload(
            name=by_ip.get("label"),
            city=by_ip.get("city"),
            pincode=by_ip.get("pincode"),
            lat=by_ip.get("lat"),
            lng=by_ip.get("lng"),
            source="ip",
        )
    return None


def get_job_manager() -> JobManager:
    from app.main import job_manager  # type: ignore

    return job_manager


@router.post("/api/jobs")
async def create_job(
    payload: CreateJobRequest,
    request: Request,
    mgr: JobManager = Depends(get_job_manager),
):
    items = [s.strip() for s in payload.items if s.strip()]
    if not items:
        return {"job_id": ""}

    resolved_location = _normalize_location_input(payload.location, request)
    job_id = mgr.create_job(items, payload.platforms, resolved_location)
    asyncio.create_task(mgr.run_job(job_id))
    return {"job_id": job_id}


@router.post("/api/items/clarify", response_model=ClarifyItemsResponse)
async def clarify_items(payload: ClarifyItemsRequest):
    items = [s.strip() for s in payload.items if s.strip()]
    settings = get_settings()
    questions = await clarify_items_with_llm(
        items,
        settings.google_api_key or "",
        "gemini-2.0-flash-lite",
    )
    return ClarifyItemsResponse(resolved_items=items, questions=questions)


@router.get("/api/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str, mgr: JobManager = Depends(get_job_manager)):
    return mgr.get_status(job_id)


@router.get("/api/jobs/{job_id}/result", response_model=JobResultResponse)
async def get_job_result(job_id: str, mgr: JobManager = Depends(get_job_manager)):
    return mgr.get_result(job_id)


@router.post("/api/jobs/{job_id}/items")
async def add_job_items(
    job_id: str,
    payload: AddItemsRequest,
    mgr: JobManager = Depends(get_job_manager),
):
    if not mgr.has_job(job_id):
        raise HTTPException(
            status_code=404,
            detail="Job not found (server may have restarted; start a new comparison).",
        )
    ok = mgr.add_items(job_id, payload.items)
    return {"ok": ok}


@router.get("/api/location/auto")
async def detect_location(request: Request) -> Dict[str, Any]:
    """
    Best-effort server-side location detection using client IP.
    Frontend geolocation (lat/lng) is more accurate and should be preferred.
    """
    ip = extract_client_ip(dict(request.headers), request.client.host if request.client else None)
    by_ip = lookup_location_by_ip(ip)
    if not by_ip:
        return {"location": None}
    return {"location": by_ip}


@router.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    """
    Stub chat endpoint for POC.
    Returns a simple acknowledgment message.
    """
    last_user = next((m for m in reversed(payload.messages) if m.role == "user"), None)
    content = last_user.content if last_user else ""
    return ChatResponse(
        assistant_message=f"Thanks for your message. LLM integration coming soon!",
        actions=[],
    )

