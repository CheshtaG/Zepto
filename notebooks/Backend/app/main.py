import logging
import time
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.exceptions import validation_exception_handler, unhandled_exception_handler
from app.api.routes_compare import router as compare_router
from app.api.routes_jobs import router as jobs_router
from app.services.comparison import ComparisonService, JobManager
from app.services.job_logger import JobLogger


configure_logging()
logger = logging.getLogger("app")


settings = get_settings()
comparison_service = ComparisonService()
job_logger = JobLogger()
job_manager = JobManager(comparison_service=comparison_service, job_logger=job_logger)


def create_app() -> FastAPI:
  app = FastAPI(title=settings.app_name, version=settings.app_version)

  # Exception handlers
  app.add_exception_handler(RequestValidationError, validation_exception_handler)
  app.add_exception_handler(Exception, unhandled_exception_handler)

  # Simple request timing middleware
  @app.middleware("http")
  async def add_process_time_header(request: Request, call_next: Callable):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (start_time - time.perf_counter()) * -1
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    logger.info("%s %s completed in %.4fs", request.method, request.url.path, process_time)
    return response

  # Routers
  app.include_router(compare_router)
  app.include_router(jobs_router)

  # Attach shared services to state for future extensions
  app.state.comparison_service = comparison_service
  app.state.job_manager = job_manager
  app.state.job_logger = job_logger

  return app


app = create_app()


