"""
Configuration file for platform URLs and settings.
Update these URLs if the platform web addresses change.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

# Platform Base URLs
INSTAMART_URL = "https://www.swiggy.com/instamart"
BLINKIT_URL = "https://blinkit.com"
ZEPTO_URL = "https://www.zepto.com"

# Platform Search URL Templates (product name goes after =)
INSTAMART_SEARCH_URL = "https://www.swiggy.com/instamart/search?custom_back=true&query="
BLINKIT_SEARCH_URL = "https://blinkit.com/s/?q="
ZEPTO_SEARCH_URL = "https://www.zepto.com/search?query="

# Location Settings
DEFAULT_LOCATION = "Pune"
DEFAULT_PINCODE = "411001"

# Scraping Settings
PAGE_LOAD_TIMEOUT = 30000  # milliseconds
ELEMENT_WAIT_TIMEOUT = 5000  # milliseconds
SEARCH_DELAY = 0.8  # seconds

# Cache Settings
CACHE_EXPIRY_MINUTES = int(os.environ.get("COMPARE_CACHE_EXPIRY_MINUTES", "15"))
CACHE_EXPIRY_HOURS = CACHE_EXPIRY_MINUTES / 60.0

# Data directory: screenshots (instamart/blinkit/zepto) and file cache live under here.
# Override with env COMPARE_DATA_DIR if needed.
_DATA_DIR_DEFAULT = "/Users/cheshtagupta17/Data - Cheshta/Projects/Zepto/data"
DATA_DIR = os.environ.get("COMPARE_DATA_DIR", _DATA_DIR_DEFAULT)

# Logs directory (structured JSONL logs)
# Override with env COMPARE_LOGS_DIR if needed.
_LOGS_DIR_DEFAULT = os.path.join(DATA_DIR, "logs")
LOGS_DIR = os.environ.get("COMPARE_LOGS_DIR", _LOGS_DIR_DEFAULT)
LOGS_JOBS_DIR = os.path.join(LOGS_DIR, "jobs")
# Single append-only log file containing events across all jobs.
LOGS_JOBS_FILE = os.environ.get("COMPARE_LOGS_JOBS_FILE", os.path.join(LOGS_DIR, "jobs.jsonl"))
