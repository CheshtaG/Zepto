"""
Configuration file for platform URLs and settings.
Update these URLs if the platform web addresses change.
"""

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
SEARCH_DELAY = 2  # seconds

# Cache Settings
CACHE_EXPIRY_HOURS = 24

# Data Directory
DATA_DIR = "/Users/cheshtagupta17/Data - Cheshta/Projects/Shopping Made Easy/data"
