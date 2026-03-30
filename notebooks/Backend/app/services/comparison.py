import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union
from datetime import datetime
from uuid import uuid4

from models import ProductComparison, ProductInfo, Platform
from cache_manager import CacheManager
from scrapers.instamart_scraper import InstamartScraper
from scrapers.blinkit_scraper import BlinkitScraper
from scrapers.zepto_scraper import ZeptoScraper
from app.core.config import get_settings
from app.schemas.jobs import (
  JobResultItem,
  JobItemMatch,
  JobResultResponse,
  JobStatusResponse,
  JobState,
  LocationPayload,
)
from app.services.gemini_quantity import (
  enrich_product_infos_async,
  fill_instamart_price_from_screenshot_if_missing,
)
from app.services.cross_platform_matcher import unified_search_after_first_pass
from app.services.job_logger import JobLogger
from config import BLINKIT_SEARCH_URL, INSTAMART_SEARCH_URL, ZEPTO_SEARCH_URL


logger = logging.getLogger("services.comparison")

SCRAPER_CACHE_VERSION = "11"


def _failed_job_row(query: str) -> JobResultItem:
  """Three platform slots so the table does not stay on empty matches=[] after a scrape error."""
  note = "Scrape failed for this product (see server logs)."
  return JobResultItem(
    query=query,
    matches=[
      JobItemMatch(
        platform="instamart",
        price=None,
        in_stock=False,
        quantity_comparison_note=note,
      ),
      JobItemMatch(
        platform="blinkit",
        price=None,
        in_stock=False,
        quantity_comparison_note=note,
      ),
      JobItemMatch(
        platform="zepto",
        price=None,
        in_stock=False,
        quantity_comparison_note=note,
      ),
    ],
  )


class ComparisonService:
  """Encapsulates product comparison logic and scrapers."""

  def __init__(self) -> None:
    self.cache = CacheManager()

  def _extract_city_pincode(
    self, location: Optional[Union[LocationPayload, str]]
  ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if isinstance(location, LocationPayload):
      name = location.name or location.city
      return location.city, location.pincode, name
    if isinstance(location, str) and location.strip():
      return None, None, location.strip()
    return None, None, None

  def cache_key_for(self, product: str, location: Optional[Union[LocationPayload, str]]) -> str:
    product_lower = product.lower().strip()
    _city, _pincode, location_label = self._extract_city_pincode(location)
    base = product_lower if not location_label else f"{product_lower}::{location_label.lower()}"
    return f"{SCRAPER_CACHE_VERSION}::{base}"

  def get_cached_comparison(
    self, product: str, location: Optional[Union[LocationPayload, str]]
  ) -> Optional[ProductComparison]:
    return self.cache.get(self.cache_key_for(product, location))

  @staticmethod
  def _instamart_price(infos: List[ProductInfo]) -> Optional[float]:
    for p in infos:
      if p.platform == Platform.INSTAMART:
        return p.price
    return None

  async def refresh_instamart_vision_on_infos(
    self, product: str, infos: List[ProductInfo]
  ) -> List[ProductInfo]:
    """Apply Gemini (+ OCR) screenshot price when Instamart DOM price is missing."""
    settings = get_settings()
    key = (settings.google_api_key or "").strip()
    if not settings.enable_gemini_instamart_price_fallback:
      return infos
    if not key:
      logger.warning(
        "Instamart: no COMPARE_GOOGLE_API_KEY — will try OCR-only for %r if screenshot exists",
        product,
      )
    # Always run Instamart-only pass even when full quantity vision is enabled.
    return await fill_instamart_price_from_screenshot_if_missing(
      product,
      infos,
      key,
      settings.gemini_model,
    )

  async def hydrate_cached_comparison(
    self, product: str, location: Optional[Union[LocationPayload, str]]
  ) -> Optional[ProductComparison]:
    """Return file-cached comparison, optionally filling Instamart price from screenshot + Gemini."""
    cached = self.get_cached_comparison(product, location)
    if not cached:
      return None
    before = self._instamart_price(cached.platforms)
    new_platforms = await self.refresh_instamart_vision_on_infos(
      product, list(cached.platforms)
    )
    after = self._instamart_price(new_platforms)
    if before is None and after is not None:
      updated = ProductComparison(product_name=cached.product_name, platforms=new_platforms)
      self.cache.set(self.cache_key_for(product, location), updated)
      logger.info("Cache updated with Instamart vision price for %r", product)
      return updated
    return ProductComparison(product_name=cached.product_name, platforms=new_platforms)

  def merge_triple_results(
    self,
    r_inst: Optional[ProductInfo],
    r_blink: Optional[ProductInfo],
    r_zepto: Optional[ProductInfo],
  ) -> List[ProductInfo]:
    out: List[ProductInfo] = []
    if r_inst is not None:
      out.append(r_inst)
    else:
      out.append(
        ProductInfo(
          platform=Platform.INSTAMART,
          price=None,
          availability=False,
          error="Product not found or scraping failed",
        )
      )
    if r_blink is not None:
      out.append(r_blink)
    else:
      out.append(
        ProductInfo(
          platform=Platform.BLINKIT,
          price=None,
          availability=False,
          error="Product not found or scraping failed",
        )
      )
    if r_zepto is not None:
      out.append(r_zepto)
    else:
      out.append(
        ProductInfo(
          platform=Platform.ZEPTO,
          price=None,
          availability=False,
          error="Product not found or scraping failed",
        )
      )
    return out

  async def enrich_info_list_if_enabled(self, product: str, info_list: List[ProductInfo]) -> List[ProductInfo]:
    settings = get_settings()
    key = (settings.google_api_key or "").strip()

    # Instamart-only screenshot pass (runs even when full quantity vision is on; OCR works without API key).
    if settings.enable_gemini_instamart_price_fallback:
      try:
        info_list = await fill_instamart_price_from_screenshot_if_missing(
          product,
          info_list,
          key,
          settings.gemini_model,
        )
      except Exception:
        logger.exception("Instamart screenshot price fallback failed for %s", product)

    if settings.enable_gemini_quantity and key:
      try:
        return await enrich_product_infos_async(
          product,
          info_list,
          key,
          settings.gemini_model,
        )
      except Exception:
        logger.exception("Gemini quantity enrichment failed for %s", product)
    return info_list

  def job_matches_from_infos(self, infos: List[ProductInfo]) -> List[JobItemMatch]:
    return [
      JobItemMatch(
        platform=p.platform.value,
        price=p.price,
        in_stock=p.availability,
        image_url=p.image_url,
        screenshot_url=p.image_url,
        listing_title=p.listing_title,
        quantity_label=p.quantity_label,
        quantity_base_value=p.quantity_base_value,
        quantity_base_unit=p.quantity_base_unit,
        price_per_base_unit=p.price_per_base_unit,
        quantity_comparable=p.quantity_comparable,
        quantity_comparison_note=p.quantity_comparison_note,
      )
      for p in infos
    ]

  async def scrape_triple_as_completed(
    self,
    product: str,
    location: Optional[Union[LocationPayload, str]],
    on_partial: Callable[[List[ProductInfo], bool], Awaitable[None]],
    on_platform_scrape: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
  ) -> ProductComparison:
    """Run the three scrapers; call on_partial(merged_infos, progress_tick) after each platform.

    progress_tick is True for each finished scraper; False for the final post-enrichment refresh.
    """
    city, pincode, _label = self._extract_city_pincode(location)
    instamart = InstamartScraper()
    blinkit = BlinkitScraper()
    zepto = ZeptoScraper()
    instamart.set_runtime_location(city, pincode)
    blinkit.set_runtime_location(city, pincode)
    zepto.set_runtime_location(city, pincode)

    async def _safe_scrape(
      key: str,
      label: str,
      query_used: str,
      round_tag: str,
      coro,
    ):
      logger.info("Scraping %s for %s", label, query_used)
      t0 = time.perf_counter()
      started_at = datetime.utcnow().isoformat()

      try:
        info = await coro
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        finished_at = datetime.utcnow().isoformat()

        if on_platform_scrape:
          search_url = (
            f"{INSTAMART_SEARCH_URL}{query_used}"
            if key == "instamart"
            else (
              f"{BLINKIT_SEARCH_URL}{query_used}"
              if key == "blinkit"
              else f"{ZEPTO_SEARCH_URL}{query_used}"
            )
          )
          await on_platform_scrape(
            {
              "job_item": product,
              "query_used": query_used,
              "platform": key,
              "search_url": search_url,
              "round": round_tag,
              "started_at": started_at,
              "finished_at": finished_at,
              "elapsed_ms": elapsed_ms,
              "success": True,
              "error": None,
            }
          )
        return info
      except Exception as e:
        logger.exception("Scraper %s failed for %s", label, query_used)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        finished_at = datetime.utcnow().isoformat()

        if on_platform_scrape:
          search_url = (
            f"{INSTAMART_SEARCH_URL}{query_used}"
            if key == "instamart"
            else (
              f"{BLINKIT_SEARCH_URL}{query_used}"
              if key == "blinkit"
              else f"{ZEPTO_SEARCH_URL}{query_used}"
            )
          )
          await on_platform_scrape(
            {
              "job_item": product,
              "query_used": query_used,
              "platform": key,
              "search_url": search_url,
              "round": round_tag,
              "started_at": started_at,
              "finished_at": finished_at,
              "elapsed_ms": elapsed_ms,
              "success": False,
              "error": str(e) or "Scraper exception",
            }
          )
        return None

    partial: Dict[str, Optional[ProductInfo]] = {"instamart": None, "blinkit": None, "zepto": None}

    async def run_one(key: str, label: str, scraper):
      info = await _safe_scrape(key, label, product, "initial", scraper.search_product(product))
      return key, info

    tasks = [
      asyncio.create_task(run_one("instamart", "Instamart", instamart)),
      asyncio.create_task(run_one("blinkit", "Blinkit", blinkit)),
      asyncio.create_task(run_one("zepto", "Zepto", zepto)),
    ]

    for fut in asyncio.as_completed(tasks):
      key, info = await fut
      partial[key] = info
      merged = self.merge_triple_results(
        partial["instamart"], partial["blinkit"], partial["zepto"]
      )
      await on_partial(merged, True)

    merged = self.merge_triple_results(
      partial["instamart"], partial["blinkit"], partial["zepto"]
    )
    enriched = await self.enrich_info_list_if_enabled(product, merged)

    settings = get_settings()
    refined_query: Optional[str] = None
    if settings.enable_cross_platform_match:
      key = (settings.google_api_key or "").strip()
      if key:
        try:
          refined_query = await asyncio.to_thread(
            unified_search_after_first_pass,
            product,
            enriched,
            key,
            settings.gemini_match_model,
          )
        except Exception:
          logger.exception("cross_platform_match failed for %r", product)

    if refined_query:
      partial2: Dict[str, Optional[ProductInfo]] = {"instamart": None, "blinkit": None, "zepto": None}

      async def run_one_refined(key: str, label: str, scraper):
        info = await _safe_scrape(key, label, refined_query, "refined", scraper.search_product(refined_query))
        return key, info

      tasks2 = [
        asyncio.create_task(run_one_refined("instamart", "Instamart", instamart)),
        asyncio.create_task(run_one_refined("blinkit", "Blinkit", blinkit)),
        asyncio.create_task(run_one_refined("zepto", "Zepto", zepto)),
      ]
      for fut in asyncio.as_completed(tasks2):
        key, info = await fut
        partial2[key] = info
        merged2 = self.merge_triple_results(
          partial2["instamart"], partial2["blinkit"], partial2["zepto"]
        )
        await on_partial(merged2, True)
      merged = self.merge_triple_results(
        partial2["instamart"], partial2["blinkit"], partial2["zepto"]
      )
      enriched = await self.enrich_info_list_if_enabled(product, merged)

    comparison = ProductComparison(product_name=product, platforms=enriched)
    self.cache.set(self.cache_key_for(product, location), comparison)
    await on_partial(enriched, False)
    return comparison

  async def compare_product(
    self, product: str, location: Optional[Union[LocationPayload, str]] = None
  ) -> ProductComparison:
    hydrated = await self.hydrate_cached_comparison(product, location)
    if hydrated:
      return hydrated

    async def _noop(_infos: List[ProductInfo], _tick: bool) -> None:
      return None

    return await self.scrape_triple_as_completed(product, location, _noop)


class JobManager:
  """In-memory job orchestration for batch comparisons."""

  def __init__(
    self, comparison_service: ComparisonService, job_logger: Optional[JobLogger] = None
  ) -> None:
    self._comparison = comparison_service
    self._jobs: Dict[str, JobState] = {}
    self._job_logger = job_logger

  def create_job(
    self,
    items: List[str],
    platforms: List[str],
    location: Optional[Union[LocationPayload, str]],
  ) -> str:
    clean_items = [s.strip() for s in items if s.strip()]
    job_id = str(uuid4())
    # Create placeholder result immediately so the frontend can render incrementally.
    placeholder_results = [
      JobResultItem(query=item, matches=[])
      for item in clean_items
    ]
    self._jobs[job_id] = JobState(
      id=job_id,
      items=clean_items,
      platforms=platforms,
      location=location,
      status="capturing",
      progress=0,
      result=JobResultResponse(items=placeholder_results, summary=None),
    )
    return job_id

  def has_job(self, job_id: str) -> bool:
    return job_id in self._jobs

  def get_status(self, job_id: str) -> JobStatusResponse:
    job = self._jobs.get(job_id)
    if not job:
      return JobStatusResponse(status="failed", progress=0, message="Job not found")
    return JobStatusResponse(status=job.status, progress=job.progress, message=job.error)

  def get_result(self, job_id: str) -> JobResultResponse:
    job = self._jobs.get(job_id)
    if not job or job.result is None:
      raise RuntimeError("Result not ready or job not found")
    return job.result

  async def run_job(self, job_id: str) -> None:
    job = self._jobs[job_id]
    total = max(len(job.items), 1)
    settings = get_settings()
    sem = asyncio.Semaphore(max(1, settings.job_max_concurrent_items))
    progress_lock = asyncio.Lock()
    done_count = sum(1 for it in (job.result.items if job.result else []) if it.matches)
    # One unit per finished platform scrape so the UI can update before all three complete.
    platform_done = [0]

    async def compare_one_item(idx: int, item: str) -> Tuple[int, JobResultItem]:
      async with sem:
        hydrated = await self._comparison.hydrate_cached_comparison(item, job.location)
        if hydrated:
          row = JobResultItem(
            query=hydrated.product_name,
            matches=self._comparison.job_matches_from_infos(hydrated.platforms),
          )
          async with progress_lock:
            platform_done[0] += 3
            job.progress = min(99, int(platform_done[0] / max(total * 3, 1) * 100))
            if idx < len(result_items):
              result_items[idx] = row
            job.result = JobResultResponse(items=list(result_items), summary=None)
            self._jobs[job_id] = job
          return idx, row

        async def on_partial(infos: List[ProductInfo], tick: bool) -> None:
          async with progress_lock:
            if tick:
              platform_done[0] += 1
            job.progress = min(99, int(platform_done[0] / max(total * 3, 1) * 100))
            if idx < len(result_items):
              result_items[idx] = JobResultItem(
                query=item,
                matches=self._comparison.job_matches_from_infos(infos),
              )
            job.result = JobResultResponse(items=list(result_items), summary=None)
            self._jobs[job_id] = job

        async def on_platform_scrape(event: Dict[str, Any]) -> None:
          if not self._job_logger:
            return
          await self._job_logger.log_platform_attempt(
            job_id=job_id,
            item=item,
            location=job.location,
            platform=str(event.get("platform") or ""),
            query_used=str(event.get("query_used") or item),
            search_url=str(event.get("search_url") or ""),
            started_at=str(event.get("started_at") or ""),
            finished_at=str(event.get("finished_at") or ""),
            elapsed_ms=int(event.get("elapsed_ms") or 0),
            success=bool(event.get("success")),
            error=event.get("error"),
            round_tag=event.get("round"),
          )

        comparison = await self._comparison.scrape_triple_as_completed(
          item,
          job.location,
          on_partial,
          on_platform_scrape=on_platform_scrape,
        )
        row = JobResultItem(
          query=comparison.product_name,
          matches=self._comparison.job_matches_from_infos(comparison.platforms),
        )
      return idx, row

    try:
      # Use as_completed so we can update job.result incrementally.
      items = job.items
      if job.result is None:
        job.result = JobResultResponse(items=[JobResultItem(query=i, matches=[]) for i in items], summary=None)
      result_items: List[JobResultItem] = list(job.result.items)

      tasks = [asyncio.create_task(compare_one_item(i, item)) for i, item in enumerate(items)]
      # Do not use as_completed: if one task raises, awaiting that future aborts the loop and
      # other rows can stay stuck with matches=[] (all dashes in the UI).
      outcomes = await asyncio.gather(*tasks, return_exceptions=True)
      async with progress_lock:
        for i, outcome in enumerate(outcomes):
          item_name = items[i]
          if isinstance(outcome, tuple) and len(outcome) == 2:
            idx, row = outcome
            if idx < len(result_items):
              result_items[idx] = row
          else:
            logger.exception("Job %s item %r scrape failed", job_id, item_name, exc_info=outcome)
            if i < len(result_items):
              result_items[i] = _failed_job_row(item_name)
          done_count += 1
        job.status = "capturing"
        job.result = JobResultResponse(items=result_items, summary=None)
        self._jobs[job_id] = job

      job.status = "done"
      job.progress = 100
      summary = None
      if job.location:
        summary = {
          "location": job.location if isinstance(job.location, str) else job.location.model_dump()
        }
      job.result = JobResultResponse(items=result_items, summary=summary)
      self._jobs[job_id] = job
    except Exception as e:
      logger.exception("Job %s failed: %s", job_id, e)
      job.status = "failed"
      job.error = f"Job failed: {e}"
      job.progress = job.progress or 0
      self._jobs[job_id] = job

  async def _run_add_items(
    self,
    job_id: str,
    start_idx: int,
    new_items: List[str],
  ) -> None:
    """Compare only `new_items` and append them into the existing job result."""
    job = self._jobs[job_id]
    total = max(len(job.items), 1)
    settings = get_settings()
    sem = asyncio.Semaphore(max(1, settings.job_max_concurrent_items))
    progress_lock = asyncio.Lock()

    # Count already-completed rows (each counts as one "row done" for finalization).
    done_count = sum(1 for it in (job.result.items if job.result else []) if it.matches)
    # Rows before `start_idx` are already fully scraped (3 platforms each).
    platform_done = [start_idx * 3]
    result_items: List[JobResultItem] = list(job.result.items) if job.result else []

    async def compare_new_item(global_idx: int, item: str) -> Tuple[int, JobResultItem]:
      async with sem:
        hydrated = await self._comparison.hydrate_cached_comparison(item, job.location)
        if hydrated:
          row = JobResultItem(
            query=hydrated.product_name,
            matches=self._comparison.job_matches_from_infos(hydrated.platforms),
          )
          async with progress_lock:
            platform_done[0] += 3
            job.progress = min(99, int(platform_done[0] / max(total * 3, 1) * 100))
            if global_idx < len(result_items):
              result_items[global_idx] = row
            job.result = JobResultResponse(items=list(result_items), summary=None)
            self._jobs[job_id] = job
          return global_idx, row

        async def on_partial(infos: List[ProductInfo], tick: bool) -> None:
          async with progress_lock:
            if tick:
              platform_done[0] += 1
            job.progress = min(99, int(platform_done[0] / max(total * 3, 1) * 100))
            if global_idx < len(result_items):
              result_items[global_idx] = JobResultItem(
                query=item,
                matches=self._comparison.job_matches_from_infos(infos),
              )
            job.result = JobResultResponse(items=list(result_items), summary=None)
            self._jobs[job_id] = job

        async def on_platform_scrape(event: Dict[str, Any]) -> None:
          if not self._job_logger:
            return
          await self._job_logger.log_platform_attempt(
            job_id=job_id,
            item=item,
            location=job.location,
            platform=str(event.get("platform") or ""),
            query_used=str(event.get("query_used") or item),
            search_url=str(event.get("search_url") or ""),
            started_at=str(event.get("started_at") or ""),
            finished_at=str(event.get("finished_at") or ""),
            elapsed_ms=int(event.get("elapsed_ms") or 0),
            success=bool(event.get("success")),
            error=event.get("error"),
            round_tag=event.get("round"),
          )

        comparison = await self._comparison.scrape_triple_as_completed(
          item,
          job.location,
          on_partial,
          on_platform_scrape=on_platform_scrape,
        )
        row = JobResultItem(
          query=comparison.product_name,
          matches=self._comparison.job_matches_from_infos(comparison.platforms),
        )
      return global_idx, row

    try:
      tasks = [
        asyncio.create_task(compare_new_item(start_idx + i, item))
        for i, item in enumerate(new_items)
      ]

      outcomes = await asyncio.gather(*tasks, return_exceptions=True)
      async with progress_lock:
        for i, outcome in enumerate(outcomes):
          global_idx = start_idx + i
          item_name = new_items[i]
          if job.result is None:
            job.result = JobResultResponse(items=[], summary=None)
          if isinstance(outcome, tuple) and len(outcome) == 2:
            idx, row = outcome
            while len(result_items) <= idx:
              result_items.append(JobResultItem(query="", matches=[]))
            if idx < len(result_items):
              result_items[idx] = row
          else:
            logger.exception(
              "Add-items job %s item %r failed", job_id, item_name, exc_info=outcome
            )
            while len(result_items) <= global_idx:
              result_items.append(JobResultItem(query="", matches=[]))
            if global_idx < len(result_items):
              result_items[global_idx] = _failed_job_row(item_name)
          done_count += 1
        job.status = "capturing"
        job.result = JobResultResponse(items=result_items, summary=None)
        self._jobs[job_id] = job

      # Finalize (if no more items are added after this request)
      if done_count >= total:
        job.status = "done"
        job.progress = 100
        summary = None
        if job.location:
          summary = {
            "location": job.location if isinstance(job.location, str) else job.location.model_dump()
          }
        job.result = JobResultResponse(items=job.result.items, summary=summary)  # type: ignore[union-attr]
        self._jobs[job_id] = job
    except Exception as e:
      logger.exception("Add-items for job %s failed: %s", job_id, e)
      job.status = "failed"
      job.error = f"Add-items job failed: {e}"
      self._jobs[job_id] = job

  def add_items(self, job_id: str, new_items: List[str]) -> bool:
    """Append items into an existing job and start scraping only those items."""
    job = self._jobs.get(job_id)
    if not job:
      raise RuntimeError("Job not found")

    clean_new = [s.strip() for s in new_items if s.strip()]
    existing = {it.strip().lower() for it in job.items}
    to_add = [it for it in clean_new if it.lower() not in existing]
    if not to_add:
      return False

    start_idx = len(job.items)
    job.items.extend(to_add)

    if job.result is None:
      job.result = JobResultResponse(
        items=[JobResultItem(query=item, matches=[]) for item in job.items],
        summary=None,
      )
    else:
      # Append placeholders so the frontend keeps old items and shows new ones immediately.
      for item in to_add:
        job.result.items.append(JobResultItem(query=item, matches=[]))

    # Reset progress/status for incremental run.
    job.status = "capturing"
    # progress will be recalculated as tasks finish.
    self._jobs[job_id] = job

    asyncio.create_task(self._run_add_items(job_id, start_idx, to_add))
    return True

