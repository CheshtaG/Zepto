import asyncio
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from config import LOGS_DIR, LOGS_JOBS_DIR


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def _location_to_label(location: Optional[Union[Dict[str, Any], Any, str]]) -> Dict[str, Any]:
  if location is None:
    return {"label": None}

  if isinstance(location, str):
    return {"label": location, "source": "manual"}

  # Pydantic model or dataclass: try common serialization helpers.
  model_dump = getattr(location, "model_dump", None)
  if callable(model_dump):
    data = model_dump()
  else:
    data = location if isinstance(location, dict) else {}

  label = data.get("name") or data.get("city") or data.get("label")
  pincode = data.get("pincode")

  return {
    "label": label,
    "city": data.get("city"),
    "pincode": pincode,
    "lat": data.get("lat"),
    "lng": data.get("lng"),
    "source": data.get("source"),
  }


class JobLogger:
  """
  Structured logging for platform scrape attempts.

  Writes one JSON line per platform scrape attempt into:
    {LOGS_JOBS_DIR}/{job_id}.jsonl
  so you can query logs per job easily.
  """

  def __init__(self, logs_dir: str = LOGS_DIR, jobs_dir: str = LOGS_JOBS_DIR) -> None:
    self.logs_dir = logs_dir
    self.jobs_dir = jobs_dir
    os.makedirs(self.jobs_dir, exist_ok=True)
    self._lock = threading.Lock()

  def _job_path(self, job_id: str) -> str:
    safe_job_id = str(job_id).replace("/", "_")
    return os.path.join(self.jobs_dir, f"{safe_job_id}.jsonl")

  def log_platform_attempt_sync(
    self,
    *,
    job_id: str,
    item: str,
    location: Optional[Union[Dict[str, Any], Any, str]],
    platform: str,
    query_used: str,
    search_url: str,
    started_at: str,
    finished_at: str,
    elapsed_ms: int,
    success: bool,
    error: Optional[str] = None,
    round_tag: Optional[str] = None,
  ) -> None:
    record = {
      "job_id": job_id,
      "logged_at": _utc_now_iso(),
      "item": item,
      "location": _location_to_label(location),
      "platform": platform,
      "query_used": query_used,
      "search_url": search_url,
      "round": round_tag,
      "started_at": started_at,
      "finished_at": finished_at,
      "elapsed_ms": elapsed_ms,
      "success": success,
    }
    if error:
      record["error"] = error

    path = self._job_path(job_id)
    line = json.dumps(record, ensure_ascii=False)
    # Serialize writes so concurrent scrapes don't interleave lines.
    with self._lock:
      with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

  async def log_platform_attempt(
    self,
    *,
    job_id: str,
    item: str,
    location: Optional[Union[Dict[str, Any], Any, str]],
    platform: str,
    query_used: str,
    search_url: str,
    started_at: str,
    finished_at: str,
    elapsed_ms: int,
    success: bool,
    error: Optional[str] = None,
    round_tag: Optional[str] = None,
  ) -> None:
    await asyncio.to_thread(
      self.log_platform_attempt_sync,
      job_id=job_id,
      item=item,
      location=location,
      platform=platform,
      query_used=query_used,
      search_url=search_url,
      started_at=started_at,
      finished_at=finished_at,
      elapsed_ms=elapsed_ms,
      success=success,
      error=error,
      round_tag=round_tag,
    )

