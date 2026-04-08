import asyncio
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException

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


router = APIRouter()


def _location_from_payload(payload: CreateJobRequest) -> Optional[Union[LocationPayload, str]]:
    """
    Location must be frontend-provided via payload.metadata.location.
    """
    if payload.metadata and isinstance(payload.metadata, dict):
        md_loc = payload.metadata.get("location")
        if isinstance(md_loc, dict):
            try:
                return LocationPayload(**md_loc)
            except Exception:
                return None
        if isinstance(md_loc, str) and md_loc.strip():
            return md_loc.strip()
    return None


def get_job_manager() -> JobManager:
    from app.main import job_manager  # type: ignore

    return job_manager


@router.post("/api/jobs")
async def create_job(
    payload: CreateJobRequest,
    mgr: JobManager = Depends(get_job_manager),
):
    items = [s.strip() for s in payload.items if s.strip()]
    if not items:
        return {"job_id": ""}

    resolved_location = _location_from_payload(payload)
    job_id = mgr.create_job(items, payload.platforms, resolved_location, payload.metadata)
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

