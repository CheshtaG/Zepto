from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Browser, ElementHandle, Page, Playwright
from models import ProductInfo, Platform
import asyncio
import os
import shutil
import re


class BaseScraper(ABC):
    # Reuse a single Playwright + browser across requests to reduce startup latency.
    # Contexts are still created per search so we don't share mutable state.
    _shared_playwright: Optional[Playwright] = None
    _shared_browser: Optional[Browser] = None
    _shared_lock: Optional[asyncio.Lock] = None

    def __init__(self):
        self.target_city: Optional[str] = None
        self.target_pincode: Optional[str] = None

    def set_runtime_location(self, city: Optional[str], pincode: Optional[str]) -> None:
        """Set per-request target location for scraper interactions."""
        self.target_city = city
        self.target_pincode = pincode

    @classmethod
    async def _get_shared_browser(cls):
        """Initialize (once) a shared Playwright + browser instance."""
        if cls._shared_playwright is not None and cls._shared_browser is not None:
            return cls._shared_playwright, cls._shared_browser

        if cls._shared_lock is None:
            cls._shared_lock = asyncio.Lock()

        async with cls._shared_lock:
            if cls._shared_playwright is not None and cls._shared_browser is not None:
                return cls._shared_playwright, cls._shared_browser

            playwright = await async_playwright().start()
            # Use Firefox (more stable on macOS, Chromium has issues)
            browser = await playwright.firefox.launch(
                headless=True,
                timeout=90000,
            )

            cls._shared_playwright = playwright
            cls._shared_browser = browser
            return playwright, browser
    
    async def _create_browser_context(self):
        """Create a new browser and page for each operation with anti-detection measures."""
        max_retries = 2
        retry_delay = 1

        playwright, browser = await self._get_shared_browser()

        for attempt in range(max_retries):
            try:
                # Create a fresh context per search so we don't share cookies/modals/state.
                context = await browser.new_context(
                    viewport={"width": 2560, "height": 1440},
                    device_scale_factor=2,
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='Asia/Kolkata',
                    ignore_https_errors=True,
                )
                page = await context.new_page()
                return playwright, browser, context, page
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                raise Exception(f"Failed to create browser context: {e}")
    
    async def _close_browser_context(self, playwright, browser, context, page):
        """Close page+context. Shared browser/playwright stays alive for speed."""
        try:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
        except Exception:
            pass

    async def _recover_from_error_page(self, page: Page, max_attempts: int = 2) -> bool:
        """
        Some platforms show transient error/blocked pages like:
        - 'Something went wrong' with a 'Try Again' button.
        Best-effort recovery by clicking Try Again or reloading.
        Returns True if we *might* have recovered.
        """
        for attempt in range(max_attempts):
            try:
                # Detect common error banners
                error_node = await page.query_selector('text=/Something went wrong/i')
                if not error_node:
                    return True

                # Try click 'Try Again' if present
                try_again = await page.query_selector('text=/Try Again/i')
                if try_again and await try_again.is_visible():
                    try:
                        await try_again.click()
                    except Exception:
                        await try_again.evaluate('el => el.click()')
                else:
                    await page.reload(wait_until="domcontentloaded")

                # Wait a short moment; then rely on the next selectors/waits
                # (in the concrete scraper) to confirm the page recovered.
                await asyncio.sleep(0.8 + 0.4 * attempt)
                # If error text is gone, we recovered.
                still_error = await page.query_selector('text=/Something went wrong/i')
                if not still_error:
                    return True
            except Exception:
                try:
                    await page.reload(wait_until="domcontentloaded")
                    await asyncio.sleep(0.8 + 0.4 * attempt)
                except Exception:
                    pass

        return False
        try:
            # For persistent context, browser and context are the same
            if context and context != browser:
                try:
                    await context.close()
                except Exception:
                    pass
            # Clean up user data dir if it exists
            if hasattr(context, '_user_data_dir'):
                try:
                    shutil.rmtree(context._user_data_dir, ignore_errors=True)
                except:
                    pass
        except Exception:
            pass
        try:
            if browser and browser != context:
                try:
                    await browser.close()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if playwright:
                try:
                    await playwright.stop()
                except Exception:
                    pass
        except Exception:
            pass
    
    def _absolute_media_url(self, page: Page, raw: Optional[str]) -> Optional[str]:
        """Turn a possibly relative image URL into an absolute https URL for the browser."""
        if not raw or not isinstance(raw, str):
            return None
        raw = raw.strip()
        if raw.startswith("data:"):
            return None
        if len(raw) < 8:
            return None
        if raw.startswith("//"):
            return "https:" + raw
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        try:
            return urljoin(page.url, raw)
        except Exception:
            return None

    async def _extract_product_image_url(self, page: Page, root: Optional[ElementHandle]) -> Optional[str]:
        """
        Best-effort URL of the product thumbnail inside the chosen card (CDN img src / lazy attrs / srcset).
        """
        if root is None:
            return None
        try:
            raw = await root.evaluate(
                """(el) => {
                  const bad = (u) => !u || u.startsWith('data:') || u.length < 8;
                  const firstFromSrcset = (s) => {
                    if (!s) return null;
                    const p = s.split(',')[0].trim().split(/\\s+/)[0];
                    return p || null;
                  };
                  const imgs = el.querySelectorAll('img');
                  let best = null;
                  let bestArea = 0;
                  for (const img of imgs) {
                    let u = img.currentSrc || img.getAttribute('src') || '';
                    if (bad(u)) u = img.getAttribute('data-src') || img.getAttribute('data-original') || '';
                    if (bad(u)) u = firstFromSrcset(img.getAttribute('srcset')) || '';
                    if (bad(u)) u = img.getAttribute('data-lazy-src') || '';
                    if (bad(u)) continue;
                    const w = img.naturalWidth || img.width || 0;
                    const h = img.naturalHeight || img.height || 0;
                    const area = w * h;
                    if (area >= bestArea) { bestArea = area; best = u; }
                  }
                  if (best) return best;
                  for (const img of imgs) {
                    const u = img.getAttribute('data-src') || img.getAttribute('data-lazy-src');
                    if (!bad(u)) return u;
                  }
                  const pic = el.querySelector('picture source[srcset]');
                  if (pic) {
                    const u = firstFromSrcset(pic.getAttribute('srcset'));
                    if (!bad(u)) return u;
                  }
                  return null;
                }"""
            )
        except Exception:
            return None
        return self._absolute_media_url(page, raw)

    async def _extract_listing_title(self, root: Optional[ElementHandle]) -> Optional[str]:
        """Best-effort visible product name from the chosen listing card (as on the site)."""
        if root is None:
            return None
        try:
            text = await root.evaluate(
                """(el) => {
                  const priceLike = (t) => /₹|rs\\.?\\s*\\d|mrp|^\\s*\\d+\\s*%|off\\s*₹/i.test(t);
                  const badLine = (t) => {
                    const s = t.trim();
                    if (s.length < 4 || s.length > 240) return true;
                    if (/^add$/i.test(s)) return true;
                    if (/^\\d+\\s*mins?$/i.test(s)) return true;
                    if (priceLike(s) && s.length < 28) return true;
                    return false;
                  };
                  const cands = [];
                  for (const sel of ['[class*="title" i]', '[class*="name" i]', '[class*="Title" i]', 'h1', 'h2', 'h3', 'h4']) {
                    for (const n of el.querySelectorAll(sel)) {
                      const t = (n.textContent || '').replace(/\\s+/g, ' ').trim();
                      if (!badLine(t)) cands.push(t);
                    }
                  }
                  if (cands.length) {
                    cands.sort((a, b) => b.length - a.length);
                    return cands[0];
                  }
                  const lines = (el.innerText || '').split('\\n').map((s) => s.trim()).filter(Boolean);
                  for (const line of lines) {
                    if (!badLine(line)) return line;
                  }
                  return null;
                }"""
            )
        except Exception:
            return None
        if not text or not isinstance(text, str):
            return None
        t = text.strip()
        return t[:500] if t else None

    @abstractmethod
    async def set_location(self, page: Page):
        """Set location to Pune. Should be implemented by each scraper."""
        pass
    
    @abstractmethod
    async def search_product(self, product_name: str) -> ProductInfo:
        """Search for a product and return ProductInfo. Should be implemented by each scraper."""
        pass
    
    def _extract_price(self, price_text: str) -> float:
        """Extract numeric price from text."""
        if not price_text:
            return None

        import re
        txt = price_text.strip()
        low = txt.lower()

        # If this snippet is clearly a discount badge (e.g. "₹8 OFF"), don't treat it as price.
        if "off" in low or "%" in low or "discount" in low or "save" in low:
            return None

        # Prefer explicit currency amounts.
        vals = []
        for m in re.finditer(r'(?:₹|Rs\.?|INR)\s*(\d+\.?\d*)', txt, re.IGNORECASE):
            try:
                v = float(m.group(1))
                if 1.0 <= v <= 10000.0:
                    vals.append(v)
            except Exception:
                continue
        if vals:
            # Selling price is typically lower than MRP in mixed snippets.
            return min(vals)

        # Fallback to plain numbers only when text doesn't look like discount/quantity context.
        if re.search(r'\b(ml|l|g|kg|pcs?|pack|piece)\b', low, re.IGNORECASE):
            return None
        numbers = re.findall(r'\d+\.?\d*', txt)
        if numbers:
            try:
                v = float(numbers[0])
                if 1.0 <= v <= 10000.0:
                    return v
            except Exception:
                return None
        return None
    
    async def _take_screenshot(self, page: Page, screenshot_path: str, selector: Optional[str] = None):
        """Take a screenshot of the page or a specific element."""
        try:
            if selector:
                # Wait for the element to be visible
                element = await page.wait_for_selector(selector, timeout=10000, state='visible')
                if element:
                    await element.screenshot(path=screenshot_path)
                    print(f"[Screenshot] Saved element screenshot to {screenshot_path}")
                else:
                    # Fallback to full page screenshot
                    await page.screenshot(path=screenshot_path, full_page=True)
                    print(f"[Screenshot] Element not found, saved full page screenshot to {screenshot_path}")
            else:
                # Take full page screenshot
                await page.screenshot(path=screenshot_path, full_page=True)
                print(f"[Screenshot] Saved full page screenshot to {screenshot_path}")
            return True
        except Exception as e:
            print(f"[Screenshot] Error taking screenshot: {e}")
            return False
    
    def _extract_text_from_screenshot(self, screenshot_path: str) -> str:
        """Extract text from screenshot using OCR."""
        try:
            import pytesseract
            from PIL import Image

            tesseract_cmd = os.getenv("TESSERACT_CMD") or shutil.which("tesseract")
            if not tesseract_cmd:
                for candidate in ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
                    if os.path.exists(candidate):
                        tesseract_cmd = candidate
                        break
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            
            # Read the image
            image = Image.open(screenshot_path)
            
            # Extract text using OCR
            text = pytesseract.image_to_string(image, lang='eng')
            print(f"[OCR] Extracted text from screenshot: {len(text)} characters")
            if len(text) > 0:
                print(f"[OCR] Sample text: {text[:200]}...")
            return text
        except ImportError:
            print("[OCR] Warning: pytesseract not installed. Install with: pip install pytesseract pillow")
            print("[OCR] Also install Tesseract OCR engine:")
            print("[OCR]   macOS: brew install tesseract")
            print("[OCR]   Linux: sudo apt-get install tesseract-ocr")
            print("[OCR]   Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
            return ""
        except Exception as e:
            error_msg = str(e)
            if "tesseract" in error_msg.lower() or "not found" in error_msg.lower():
                print(f"[OCR] Error: Tesseract OCR not found. Please install Tesseract:")
                print(f"[OCR]   macOS: brew install tesseract")
                print(f"[OCR]   Linux: sudo apt-get install tesseract-ocr")
            else:
                print(f"[OCR] Error extracting text: {e}")
            return ""
    
    def _extract_price_from_ocr_text(self, ocr_text: str) -> Optional[float]:
        """Extract price from OCR text by looking for currency symbols and numbers."""
        if not ocr_text:
            return None
        
        import re
        
        # Prefer currency-symbol candidates, but don't blindly take the first one.
        # Some listings have pack size (e.g. "48 ml") near other numbers; OCR can mix these up.
        # We:
        # 1) Collect all currency matches with positions
        # 2) Filter out candidates whose local context looks like quantity units (ml/g/kg/l/pieces)
        # 3) Pick the last remaining candidate (usually the price is lower than pack size)
        currency_patterns = [
            r'₹\s*(\d+\.?\d*)',  # ₹60, ₹ 60
            r'Rs\.?\s*(\d+\.?\d*)',  # Rs. 60, Rs 60
            r'(\d+\.?\d*)\s*₹',  # 60 ₹
            r'(\d+\.?\d*)\s*Rs',  # 60 Rs
        ]

        candidates: List[Tuple[int, float]] = []
        for pattern in currency_patterns:
            for m in re.finditer(pattern, ocr_text, re.IGNORECASE):
                try:
                    price = float(m.group(1))
                except ValueError:
                    continue
                if not (1.0 <= price <= 10000.0):
                    continue

                start = max(0, m.start() - 18)
                end = min(len(ocr_text), m.end() + 18)
                context = ocr_text[start:end].lower()
                candidates.append((m.start(), price))

        if candidates:
            # Filter out likely quantity values near the candidate.
            valid: List[Tuple[int, float]] = []
            for pos, price in candidates:
                start = max(0, pos - 18)
                end = min(len(ocr_text), pos + 18 + 18)
                context = ocr_text[start:end].lower()
                if re.search(r'\b(ml|l|g|kg|pcs?|pieces?|pack)\b', context, re.IGNORECASE):
                    continue
                # Skip discount badge values like "₹8 OFF"
                if re.search(r'\b(off|discount|save)\b|%', context, re.IGNORECASE):
                    continue
                valid.append((pos, price))

            chosen = (valid or candidates)
            # Prefer the lower non-discount amount (often selling price vs MRP).
            _, best_price = min(chosen, key=lambda x: x[1])
            print(f"[OCR] Found price candidate: ₹{best_price}")
            return best_price
        
        # Fallback (quantities can be mistaken as price):
        # If OCR didn't include currency symbols, we *only* accept numbers that do NOT look like
        # quantity expressions (ml/g/l/kg/pieces). Otherwise we return None and rely on DOM/text
        # extraction which usually contains explicit ₹/Rs.
        for m in re.finditer(r'\b(\d+\.?\d{0,2})\b', ocr_text):
            try:
                num = float(m.group(1))
            except ValueError:
                continue
            if not (5.0 <= num <= 5000.0):
                continue

            start = max(0, m.start() - 12)
            end = min(len(ocr_text), m.end() + 25)
            context = ocr_text[start:end].lower()

            # Skip likely quantities.
            # Examples: "500 ml", "250g", "1 L", "6 x 200 ml", "pcs"
            if re.search(r'\b(ml|l|g|kg|pcs?|pieces?|pack)\b', context, re.IGNORECASE):
                continue

            # Also skip if "mrp" or other non-price patterns dominate.
            if "ml" in context or "g" in context:
                continue

            print(f"[OCR] Found potential price (no currency, quantity-filtered): ₹{num}")
            return num
        
        print("[OCR] No price found in OCR text")
        return None

    def _extract_price_from_text(self, text: str) -> Optional[float]:
        """Extract price from generic text (DOM/OCR fallback)."""
        if not text:
            return None

        import re

        candidates = []
        patterns = [
            r'₹\s*(\d+\.?\d*)',
            r'Rs\.?\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*₹',
            r'(\d+\.?\d*)\s*Rs',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    value = float(match.group(1))
                    if 1.0 <= value <= 5000.0:
                        candidates.append((match.start(), value))
                except Exception:
                    continue

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0])
        early = [v for _, v in candidates[:15]]
        return min(early) if early else None

    async def _extract_price_from_page(self, page: Page) -> Optional[float]:
        """Fallback extraction from rendered page text/content."""
        try:
            text = await page.inner_text("body")
        except Exception:
            try:
                text = await page.content()
            except Exception:
                return None
        return self._extract_price_from_text(text)
