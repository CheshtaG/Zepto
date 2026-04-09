import asyncio
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from config import LOGS_DIR, LOGS_JOBS_DIR, LOGS_JOBS_FILE


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
  Structured logging for platform scrape attempts and job events.

  Writes one JSON line per event into a single append-only file:
    {LOGS_JOBS_FILE}
  so logs are naturally ordered by write time (latest lines at the end).
  """

  def __init__(
    self,
    logs_dir: str = LOGS_DIR,
    jobs_dir: str = LOGS_JOBS_DIR,
    jobs_file: str = LOGS_JOBS_FILE,
  ) -> None:
    self.logs_dir = logs_dir
    self.jobs_dir = jobs_dir
    self.jobs_file = jobs_file
    os.makedirs(self.logs_dir, exist_ok=True)
    os.makedirs(self.jobs_dir, exist_ok=True)
    self._lock = threading.Lock()

  def _log_path(self) -> str:
    return self.jobs_file

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
    price_extraction_method: Optional[str] = None,
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
    if price_extraction_method:
      record["price_extraction_method"] = price_extraction_method

    path = self._log_path()
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
    price_extraction_method: Optional[str] = None,
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
      price_extraction_method=price_extraction_method,
    )

  def log_job_event_sync(
    self,
    *,
    job_id: str,
    event: str,
    metadata: Optional[Dict[str, Any]] = None,
  ) -> None:
    record = {
      "job_id": job_id,
      "logged_at": _utc_now_iso(),
      "event": event,
      "metadata": metadata or {},
    }
    path = self._log_path()
    line = json.dumps(record, ensure_ascii=False)
    with self._lock:
      with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

  async def log_job_event(
    self,
    *,
    job_id: str,
    event: str,
    metadata: Optional[Dict[str, Any]] = None,
  ) -> None:
    await asyncio.to_thread(
      self.log_job_event_sync,
      job_id=job_id,
      event=event,
      metadata=metadata,
    )

