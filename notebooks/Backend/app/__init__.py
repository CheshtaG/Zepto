"""
Application package for the product comparison backend.

This package organizes the codebase into clear layers:
- core: shared config, logging, exception handling
- api: FastAPI routers and request/response models
- services: business logic and orchestration

The root-level main.py simply exposes `app` from `app.main`
so existing uvicorn commands keep working.
"""

