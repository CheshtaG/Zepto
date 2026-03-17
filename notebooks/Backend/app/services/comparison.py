import asyncio
import logging
from typing import List, Dict, Optional
from uuid import uuid4

from models import ProductComparison, ProductInfo, Platform
from cache_manager import CacheManager
from scrapers.instamart_scraper import InstamartScraper
from scrapers.blinkit_scraper import BlinkitScraper
from scrapers.zepto_scraper import ZeptoScraper
from app.schemas.jobs import (
  JobResultItem,
  JobItemMatch,
  JobResultResponse,
  JobStatusResponse,
  JobState,
)


logger = logging.getLogger("services.comparison")


class ComparisonService:
  """Encapsulates product comparison logic and scrapers."""

  def __init__(self) -> None:
    self.cache = CacheManager()
    self.instamart = InstamartScraper()
    self.blinkit = BlinkitScraper()
    self.zepto = ZeptoScraper()

  async def compare_product(self, product: str) -> ProductComparison:
    product_lower = product.lower().strip()

    cached = self.cache.get(product_lower)
    if cached:
      return cached

    results: List[ProductInfo | None] = []
    try:
      logger.info("Scraping Instamart for %s", product)
      r1 = await self.instamart.search_product(product)
      results.append(r1)
      await asyncio.sleep(2)

      logger.info("Scraping Blinkit for %s", product)
      r2 = await self.blinkit.search_product(product)
      results.append(r2)
      await asyncio.sleep(2)

      logger.info("Scraping Zepto for %s", product)
      r3 = await self.zepto.search_product(product)
      results.append(r3)
    except Exception as e:
      logger.exception("Error during scraping for %s: %s", product, e)
      while len(results) < 3:
        results.append(None)

    info_list: List[ProductInfo] = []

    # Instamart
    if len(results) > 0 and results[0] is not None:
      info_list.append(results[0])
    else:
      info_list.append(
        ProductInfo(
          platform=Platform.INSTAMART,
          price=None,
          availability=False,
          error="Product not found or scraping failed",
        )
      )

    # Blinkit
    if len(results) > 1 and results[1] is not None:
      info_list.append(results[1])
    else:
      info_list.append(
        ProductInfo(
          platform=Platform.BLINKIT,
          price=None,
          availability=False,
          error="Product not found or scraping failed",
        )
      )

    # Zepto
    if len(results) > 2 and results[2] is not None:
      info_list.append(results[2])
    else:
      info_list.append(
        ProductInfo(
          platform=Platform.ZEPTO,
          price=None,
          availability=False,
          error="Product not found or scraping failed",
        )
      )

    comparison = ProductComparison(product_name=product, platforms=info_list)
    self.cache.set(product_lower, comparison)
    return comparison


class JobManager:
  """In-memory job orchestration for batch comparisons."""

  def __init__(self, comparison_service: ComparisonService) -> None:
    self._comparison = comparison_service
    self._jobs: Dict[str, JobState] = {}

  def create_job(self, items: List[str], platforms: List[str], location: Optional[str]) -> str:
    clean_items = [s.strip() for s in items if s.strip()]
    job_id = str(uuid4())
    self._jobs[job_id] = JobState(
      id=job_id,
      items=clean_items,
      platforms=platforms,
      location=location,
      status="capturing",
      progress=0,
    )
    return job_id

  def get_status(self, job_id: str) -> JobStatusResponse:
    job = self._jobs.get(job_id)
    if not job:
      return JobStatusResponse(status="failed", progress=0, message="Job not found")
    return JobStatusResponse(status=job.status, progress=job.progress, message=job.error)

  def get_result(self, job_id: str) -> JobResultResponse:
    job = self._jobs.get(job_id)
    if not job or not job.result:
      raise RuntimeError("Result not ready or job not found")
    return job.result

  async def run_job(self, job_id: str) -> None:
    job = self._jobs[job_id]
    total = max(len(job.items), 1)
    results: List[JobResultItem] = []

    try:
      for idx, item in enumerate(job.items):
        comparison = await self._comparison.compare_product(item)

        matches: List[JobItemMatch] = []
        for p in comparison.platforms:
          matches.append(
            JobItemMatch(
              platform=p.platform.value,
              price=p.price,
              in_stock=p.availability,
              screenshot_url=p.image_url,
            )
          )

        results.append(JobResultItem(query=comparison.product_name, matches=matches))

        progress = int(((idx + 1) / total) * 100)
        job.status = "capturing"
        job.progress = progress
        self._jobs[job_id] = job

      job.status = "done"
      job.progress = 100
      job.result = JobResultResponse(items=results, summary=None)
      self._jobs[job_id] = job
    except Exception as e:
      logger.exception("Job %s failed: %s", job_id, e)
      job.status = "failed"
      job.error = f"Job failed: {e}"
      job.progress = job.progress or 0
      self._jobs[job_id] = job

