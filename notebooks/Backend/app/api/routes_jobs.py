import asyncio
from fastapi import APIRouter, Depends

from app.schemas.jobs import (
    CreateJobRequest,
    JobStatusResponse,
    JobResultResponse,
    ChatRequest,
    ChatResponse,
)
from app.services.comparison import JobManager


router = APIRouter()


def get_job_manager() -> JobManager:
    from app.main import job_manager  # type: ignore

    return job_manager


@router.post("/api/jobs")
async def create_job(payload: CreateJobRequest, mgr: JobManager = Depends(get_job_manager)):
    items = [s.strip() for s in payload.items if s.strip()]
    if not items:
        return {"job_id": ""}

    job_id = mgr.create_job(items, payload.platforms, payload.location)
    asyncio.create_task(mgr.run_job(job_id))
    return {"job_id": job_id}


@router.get("/api/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str, mgr: JobManager = Depends(get_job_manager)):
    return mgr.get_status(job_id)


@router.get("/api/jobs/{job_id}/result", response_model=JobResultResponse)
async def get_job_result(job_id: str, mgr: JobManager = Depends(get_job_manager)):
    return mgr.get_result(job_id)


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

