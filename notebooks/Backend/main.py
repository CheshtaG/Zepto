"""
Thin wrapper to expose the FastAPI `app` instance.

The real application is defined in `app.main`. This file exists
so existing commands like `uvicorn main:app --reload` continue to work.
"""

from app.main import app  # noqa: F401
