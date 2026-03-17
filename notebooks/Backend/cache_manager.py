import json
import os
from datetime import datetime, timedelta
from typing import Optional
from models import ProductComparison
from config import DATA_DIR, CACHE_EXPIRY_HOURS

CACHE_DIR = os.path.join(DATA_DIR, "cache")


class CacheManager:
    def __init__(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
    
    def _get_cache_path(self, product_name: str) -> str:
        """Get the cache file path for a product."""
        safe_name = product_name.replace(" ", "_").replace("/", "_")
        return os.path.join(CACHE_DIR, f"{safe_name}.json")
    
    def get(self, product_name: str) -> Optional[ProductComparison]:
        """Get cached data for a product if it exists and is not expired."""
        cache_path = self._get_cache_path(product_name)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
            
            # Check if cache is expired
            cached_time = datetime.fromisoformat(data.get('cached_at', ''))
            if datetime.now() - cached_time > timedelta(hours=CACHE_EXPIRY_HOURS):
                os.remove(cache_path)
                return None
            
            # Return the cached comparison data
            return ProductComparison(**data['comparison'])
        except Exception as e:
            print(f"Error reading cache: {e}")
            return None
    
    def set(self, product_name: str, comparison: ProductComparison):
        """Cache the comparison data for a product."""
        cache_path = self._get_cache_path(product_name)
        
        try:
            data = {
                'cached_at': datetime.now().isoformat(),
                'comparison': comparison.dict()
            }
            
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error writing cache: {e}")
