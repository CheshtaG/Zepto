#!/usr/bin/env python3
"""
Debug Instamart price-from-screenshot (Gemini + OCR).

Run from the Backend folder:
  cd notebooks/Backend && python scripts/test_instamart_vision.py limca
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from app.core.config import get_settings
from app.services.gemini_quantity import (
    read_instamart_price_from_screenshot_sync,
    resolve_instamart_screenshot_path,
)


def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "limca"
    settings = get_settings()
    path = resolve_instamart_screenshot_path(query, None)
    key = (settings.google_api_key or "").strip()

    print("query:", query)
    print("resolved PNG:", path)
    print("COMPARE_GOOGLE_API_KEY set:", bool(key))
    print("COMPARE_GEMINI_MODEL:", settings.gemini_model)
    print("COMPARE_DATA_DIR (settings):", settings.data_dir)

    if not path:
        print(
            "\nNo file found. Expected something like:",
            f"  <COMPARE_DATA_DIR>/instamart/{query.replace(' ', '_')}_search.png",
        )
        sys.exit(1)

    price = read_instamart_price_from_screenshot_sync(
        path,
        query,
        key,
        settings.gemini_model,
    )
    print("\nextracted price:", price)
    if price is None:
        print(
            "\nBoth Gemini and OCR returned nothing. Check:\n"
            "  - API key and billing for Google AI Studio\n"
            "  - brew install tesseract (then re-run this script)\n"
            "  - Backend logs for lines starting with 'Instamart'"
        )
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
