from typing import List, Optional
from playwright.async_api import Page
from models import ProductInfo, Platform
from scrapers.base_scraper import BaseScraper
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import INSTAMART_URL, INSTAMART_SEARCH_URL, DEFAULT_PINCODE, PAGE_LOAD_TIMEOUT, ELEMENT_WAIT_TIMEOUT, SEARCH_DELAY, DATA_DIR

# Unicode rupee U+20B9, literal ₹, and Rs — Instamart often uses U+20B9 in fonts while DOM text varies.
RUPEE_CLASS = r"(?:\u20b9|₹|[Rr][sS]\.?)"

# Instamart sometimes returns an empty illustration state (no grid); manual refresh usually fixes in 3–4 tries.
INSTAMART_EMPTY_RESULT_RETRIES = 10


def _prices_from_rupee_text(text: str) -> List[float]:
    import re

    found: List[float] = []
    for m in re.finditer(
        rf"{RUPEE_CLASS}\s*(\d+\.?\d*)",
        text,
        re.IGNORECASE,
    ):
        try:
            v = float(m.group(1))
            if 5.0 <= v <= 10000.0:
                found.append(v)
        except ValueError:
            continue
    return found


class InstamartScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = INSTAMART_URL
    
    async def set_location(self, page: Page):
        """Set location to Pune for Instamart. Assumes page is already navigated."""
        try:
            # Don't navigate again - page should already be at the base URL
            await asyncio.sleep(1)  # Small delay to ensure page is ready
            
            # Try to find and click location picker
            location_selectors = [
                'button:has-text("Pune")',
                'button:has-text("Change")',
                '[data-testid="location-picker"]',
                'input[placeholder*="location" i]',
                'input[placeholder*="area" i]',
                'input[placeholder*="pincode" i]'
            ]
            
            location_set = False
            
            # Try location picker first
            for selector in location_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=ELEMENT_WAIT_TIMEOUT)
                    if element:
                        await element.click()
                        await asyncio.sleep(1)
                        
                        # Try to search for Pune
                        search_input = await page.wait_for_selector('input[type="text"], input[type="search"]', timeout=3000)
                        if search_input:
                            await search_input.fill(self.target_city or "Pune")
                            await asyncio.sleep(SEARCH_DELAY)
                            
                            # Click on Pune option
                            pune_option = await page.wait_for_selector(f"text={self.target_city or 'Pune'}", timeout=3000)
                            if pune_option:
                                await pune_option.click()
                                await asyncio.sleep(SEARCH_DELAY)
                                location_set = True
                                break
                except:
                    continue
            
            # If location picker didn't work, try pincode
            if not location_set:
                pune_pincode = self.target_pincode or DEFAULT_PINCODE
                pincode_selectors = [
                    'input[placeholder*="pincode" i]',
                    'input[placeholder*="pin" i]',
                    'input[type="text"]',
                    'input[type="number"]'
                ]
                
                for selector in pincode_selectors:
                    try:
                        element = await page.wait_for_selector(selector, timeout=3000)
                        if element:
                            await element.fill(pune_pincode)
                            await page.keyboard.press("Enter")
                            await asyncio.sleep(1.2)
                            location_set = True
                            break
                    except:
                        continue
            
            return location_set
        except Exception as e:
            print(f"Error setting location for Instamart: {e}")
            return False

    async def _instamart_has_visible_product_listings(self, page: Page) -> bool:
        """
        True when search results show at least one plausible Instamart product tile.
        When this is false, Swiggy often shows an empty illustration page that recovers after reload.
        """
        try:
            has_listing = await page.evaluate(
                """() => {
                  const links = document.querySelectorAll('a[href*="/p/"]');
                  for (const a of links) {
                    const href = (a.getAttribute('href') || '');
                    if (!href.toLowerCase().includes('instamart')) continue;
                    const r = a.getBoundingClientRect();
                    if (r.width < 72 || r.height < 72) continue;
                    const vh = window.innerHeight || 900;
                    if (r.bottom < 0 || r.top > vh + 240) continue;
                    const t = (a.innerText || '').replace(/\\s+/g, ' ').trim();
                    if (t.length < 14) continue;
                    if (/₹|\\u20b9|[Rr][sS]\\.?|OFF|%/.test(t) || /\\d/.test(t)) return true;
                  }
                  return false;
                }"""
            )
            return bool(has_listing)
        except Exception as e:
            print(f"[Instamart] Listing detection failed (treating as empty): {e}")
            return False

    async def _wait_until_listings_visible(self, page: Page, timeout_ms: int) -> bool:
        """
        Poll for real Instamart product tiles instead of using fixed sleeps.
        Returns True as soon as listings are visible, else False on timeout.
        """
        import time

        deadline = time.monotonic() + max(0, timeout_ms) / 1000.0
        while time.monotonic() < deadline:
            try:
                if await self._instamart_has_visible_product_listings(page):
                    return True
            except Exception:
                # Keep polling; page may still be hydrating.
                pass
            await asyncio.sleep(0.25)

        return False

    async def search_product(self, product_name: str) -> Optional[ProductInfo]:
        """Search for a product on Instamart."""
        playwright = None
        browser = None
        context = None
        page = None
        screenshot_path = None
        try:
            print(f"[Instamart] Starting search for: {product_name}")
            # Create fresh browser context for this operation
            print("[Instamart] Creating browser context...")
            playwright, browser, context, page = await self._create_browser_context()
            print("[Instamart] Browser context created successfully")
            
            # Use URL-based search directly
            
            search_url = f"{INSTAMART_SEARCH_URL}{product_name}"
            print(f"[Instamart] Using URL-based search: {search_url}")
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                print("[Instamart] URL-based search navigation successful")
            except Exception as e:
                error_str = str(e)
                print(f"[Instamart] URL search navigation error: {error_str}")
                if "closed" in error_str.lower() or "Target" in error_str:
                    raise Exception(f"Browser/page was closed during navigation: {error_str}")
                print("[Instamart] Attempting to continue despite navigation error...")

            for empty_round in range(INSTAMART_EMPTY_RESULT_RETRIES + 1):
                if empty_round > 0:
                    print(
                        f"[Instamart] Empty / illustration-only search UI — refreshing "
                        f"({empty_round}/{INSTAMART_EMPTY_RESULT_RETRIES})"
                    )
                    try:
                        await page.reload(wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                    except Exception as re_err:
                        print(f"[Instamart] Reload failed: {re_err}")

                    # Give Swiggy a brief moment to start rendering after reload.
                    await asyncio.sleep(0.25)

                # Try to close any popups/modals that might be blocking
                try:
                    close_buttons = await page.query_selector_all(
                        'button[aria-label*="close" i], button[aria-label*="Close" i], .close, [class*="close"], [class*="modal-close"]'
                    )
                    for btn in close_buttons[:3]:
                        try:
                            if await btn.is_visible():
                                await btn.click()
                                await asyncio.sleep(0.2)
                        except Exception:
                            pass
                except Exception:
                    pass

                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception as e:
                    if "closed" in str(e).lower() or "Target" in str(e):
                        raise Exception(f"Browser/page was closed during search: {e}")
                    print(f"[Instamart] Load state wait failed (continuing): {e}")

                # Wait until we see at least one real product tile (or timeout).
                if await self._wait_until_listings_visible(page, timeout_ms=ELEMENT_WAIT_TIMEOUT):
                    if empty_round > 0:
                        print(f"[Instamart] Product listings visible after {empty_round} refresh(es)")
                    break
                if empty_round >= INSTAMART_EMPTY_RESULT_RETRIES:
                    print(
                        "[Instamart] No listings after all refresh attempts; continuing with extraction anyway"
                    )
            
            # Try to find first product result - wait a bit longer and try more selectors
            print("[Instamart] Searching for product elements...")
            try:
                await page.wait_for_selector('a[href*="/p/"]', timeout=ELEMENT_WAIT_TIMEOUT)
            except Exception:
                # We'll fall back to the existing DOM heuristics even if we can't find a tile quickly.
                pass
            
            import re as _re_card
            query_tokens = [t.strip().lower() for t in product_name.split() if len(t.strip()) >= 3]
            product_selectors = [
                'a[href*="/instamart/"][href*="/p/"]',
                'a[href*="/p/"]',
                '[data-testid*="product" i]',
                '[data-testid*="Product" i]',
                '.product-card',
                '.product-item',
                '[class*="product" i]',
                '[class*="Product" i]',
                'article',
                'div[class*="ProductCard" i]',
                'div[class*="product-card" i]',
                '[role="article"]',
                'div[class*="item" i]',
                'div[class*="card" i]',
            ]

            def _score_tile_text(text: str) -> int:
                if not text or len(text.strip()) < 6:
                    return 0
                low = text.lower()
                score = 0
                if _re_card.search(rf"{RUPEE_CLASS}\s*\d", text, _re_card.IGNORECASE):
                    score += 6
                if _re_card.search(r"\d+\s*(?:ml|g|kg|l)\b", text, _re_card.IGNORECASE):
                    score += 2
                if _re_card.search(r"\d+\s*(ml|g|kg|l)\b", text, _re_card.IGNORECASE):
                    score += 2
                if "OFF" in text.upper() or "%" in text:
                    score += 1
                # Prefer product cards that actually mention the query.
                if query_tokens:
                    score += sum(4 for tok in query_tokens if tok in low)
                return score

            product_element = None
            best_score = 0
            for selector in product_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    print(f"[Instamart] Found {len(elements)} elements with selector: {selector}")
                    limit = 5 if selector.startswith("a[href") else 18
                    for elem in elements[:limit]:
                        try:
                            if not await elem.is_visible():
                                continue
                            t = await elem.inner_text()
                            sc = _score_tile_text(t)
                            if sc > best_score:
                                best_score = sc
                                product_element = elem
                                print(
                                    f"[Instamart] Candidate product tile (score={sc}) selector={selector}"
                                )
                        except Exception:
                            continue
                    if product_element and best_score >= 6:
                        break
                except Exception as e:
                    if "closed" in str(e).lower() or "Target" in str(e):
                        raise Exception(f"Browser/page was closed while finding product: {e}")
                    continue

            if product_element is not None and best_score < 4:
                print(
                    f"[Instamart] Low-confidence tile (score={best_score}); continuing with best candidate"
                )
            
            # Use screenshot + OCR method to extract price
            print("[Instamart] Using screenshot + OCR method to extract price...")
            
            # Create screenshot directory if it doesn't exist
            screenshot_dir = os.path.join(DATA_DIR, "instamart")
            os.makedirs(screenshot_dir, exist_ok=True)
            
            safe_name = product_name.replace(" ", "_")
            # Single screenshot per platform: full page.
            screenshot_path = os.path.join(screenshot_dir, f"{safe_name}_search.png")
            
            # Try to find product listing container for better screenshot
            product_container = None
            container_selectors = [
                '[class*="product-list" i]',
                '[class*="ProductList" i]',
                '[class*="search-results" i]',
                '[class*="results" i]',
                'main',
                'article',
                'div[class*="container" i]'
            ]
            
            for selector in container_selectors:
                try:
                    containers = await page.query_selector_all(selector)
                    for container in containers[:5]:
                        if await container.is_visible():
                            product_container = container
                            print(f"[Instamart] Found product container: {selector}")
                            break
                    if product_container:
                        break
                except:
                    continue

            # If we couldn't pinpoint the first product card, fall back to the best
            # visible container to keep extraction scoped to the results area.
            if product_element is None and product_container is not None:
                product_element = product_container
            
            await self._recover_from_error_page(page, max_attempts=3)
            # Ensure we are back on a results page before price extraction.
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
            except:
                pass
            try:
                await page.wait_for_selector(
                    '[class*="product" i], [data-testid*="product" i]',
                    timeout=5000,
                )
            except:
                pass
            
            # We'll extract the price using targeted product-card DOM selectors below.
            # Generic page-wide text tends to pick small numbers (delivery/fees), causing
            # errors like ₹2 instead of the actual product price.
            price = None
            extraction_method = "none"

            # Strategy 0: query-aware extraction directly from rendered page text.
            # This survives dynamic layouts where product-card selectors can return zero elements.
            if price is None:
                try:
                    query_tokens = [t.strip().lower() for t in product_name.split() if len(t.strip()) >= 3]
                    js_price = await page.evaluate(
                        """(tokens) => {
                          const bodyText = ((document.body && document.body.innerText) || '')
                            .replace(/\\s+/g, ' ')
                            .trim();
                          if (!bodyText) return null;

                          const prices = [];
                          const re = /(?:₹|Rs\\.?|INR)\\s*(\\d+(?:\\.\\d+)?)/gi;
                          let m;
                          while ((m = re.exec(bodyText)) !== null) {
                            const v = Number(m[1]);
                            if (Number.isFinite(v) && v >= 5 && v <= 10000) {
                              prices.push({ idx: m.index, v });
                              if (prices.length >= 120) break;
                            }
                          }
                          if (!prices.length) return null;

                          // Prefer prices close to query-token mentions in the text.
                          if (tokens && tokens.length) {
                            let best = null;
                            const low = bodyText.toLowerCase();
                            for (const tok of tokens) {
                              const pos = low.indexOf(tok);
                              if (pos < 0) continue;
                              for (const p of prices) {
                                const d = Math.abs(p.idx - pos);
                                if (d > 1800) continue;
                                if (!best || d < best.d) best = { d, v: p.v };
                              }
                            }
                            if (best) return best.v;
                          }

                          // Fallback to the first plausible rupee value.
                          return prices[0].v;
                        }""",
                        query_tokens,
                    )
                    if js_price is not None:
                        price = float(js_price)
                        extraction_method = "dom_query_text"
                        print(f"[Instamart] Selected price from query-aware page-text strategy: ₹{price}")
                except Exception as e:
                    print(f"[Instamart] Query-aware page-text strategy failed: {e}")
            
            # If OCR didn't find price OR returned an implausibly small value,
            # try traditional method as fallback (OCR can confuse digits).
            if price is None or (price is not None and price < 5.0):
                if price is not None and price < 5.0:
                    print(f"[Instamart] DOM price seems suspicious ({price}); retrying extraction...")
                    price = None
                else:
                    print("[Instamart] DOM didn't find price, trying traditional extraction...")
                
                # Try multiple strategies to find price
                price_text = None
                
                # Strategy 1: Look for price elements WITHIN the first product element
                if product_element:
                    try:
                        # First, try to find price-specific elements within the product
                        price_selectors_in_product = [
                            '[class*="price" i]',
                            '[class*="Price" i]',
                            'span:has-text("₹")',
                            'div:has-text("₹")',
                            '[class*="amount" i]',
                            '[class*="cost" i]',
                            '[class*="rupee" i]',
                            'span[class*="currency" i]',
                            'div[class*="currency" i]'
                        ]
                        
                        price_candidates = []
                        for selector in price_selectors_in_product:
                            try:
                                price_elements = await product_element.query_selector_all(selector)
                                print(f"[Instamart] Found {len(price_elements)} price elements in product with selector: {selector}")
                                for price_elem in price_elements[:5]:  # Check first 5 price elements
                                    try:
                                        if await price_elem.is_visible():
                                            text = await price_elem.inner_text()
                                            print(f"[Instamart] Price element text: {text}")
                                            import re
                                            # Some Instamart tiles render the rupee sign as an icon/SVG,
                                            # so the numeric price might exist without a literal '₹' char.
                                            rupee_match = re.search(
                                                rf"{RUPEE_CLASS}\s*(\d+\.?\d*)", text, re.IGNORECASE
                                            )
                                            units_present = bool(
                                                re.search(
                                                    r'\b(ml|g|kg|l|pcs?|pack|unit|piece)\b',
                                                    text,
                                                    re.IGNORECASE,
                                                )
                                            )

                                            price_num = None
                                            if rupee_match:
                                                price_num = rupee_match.group(1)
                                            else:
                                                # If we only see a percentage/discount number, skip it.
                                                if '%' in text:
                                                    continue
                                                numbers = re.findall(r'(\d+\.?\d*)', text)
                                                if numbers:
                                                    price_num = numbers[-1]

                                            if price_num is not None:
                                                # If this number seems tied to units (ml/g/etc) and there's no
                                                # rupee match, it's likely quantity, not price.
                                                # Don't skip when quantity-like units are present.
                                                # On Instamart tiles, the rupee symbol can be rendered as an icon/SVG,
                                                # so relying on `rupee_match` alone can otherwise lead to blanks.

                                                extracted = float(price_num)
                                                if 5.0 <= extracted <= 10000.0:
                                                    price_candidates.append(extracted)
                                                    print(
                                                        f"[Instamart] Found candidate price in product element: ₹{extracted} (text: {text})"
                                                    )
                                    except Exception as e:
                                        print(f"[Instamart] Error checking price element: {e}")
                                        continue
                            except Exception as e:
                                print(f"[Instamart] Error with selector {selector}: {e}")
                                continue
                        
                        if price_candidates:
                            # Choose the last candidate (price is typically below quantity info).
                            price = price_candidates[-1]
                            extraction_method = "dom_product_selector"
                            print(
                                f"[Instamart] Selected price from product element candidates: ₹{price}"
                            )
                        
                        # If price not found in specific elements, try extracting from product text
                        if not price_candidates:
                            all_text = await product_element.inner_text()
                            print(f"[Instamart] Product element text: {all_text[:300]}...")
                            
                            import re
                            # Find all prices with ₹ symbol
                            price_matches = list(
                                re.finditer(rf"{RUPEE_CLASS}\s*(\d+\.?\d*)", all_text, re.IGNORECASE)
                            )
                            print(f"[Instamart] Found {len(price_matches)} price matches in product text")
                            
                            found_prices = []
                            for match in price_matches:
                                try:
                                    # Check the context around the match.
                                    start_pos = max(0, match.start() - 5)
                                    end_pos = min(len(all_text), match.end() + 15)
                                    context = all_text[start_pos:end_pos].lower()
                                    
                                    
                                    potential_price = float(match.group(1))
                                    # Prices are typically between ₹5 and ₹10000
                                    if 5.0 <= potential_price <= 10000.0:
                                        found_prices.append((potential_price, match.start()))
                                        print(f"[Instamart] Found valid price candidate: ₹{potential_price}")
                                except Exception as e:
                                    print(f"[Instamart] Error processing price match: {e}")
                                    continue
                            
                            # If we found prices, prefer the highest plausible rupee value.
                            if found_prices:
                                # Choose the last ₹ occurrence in the tile text.
                                price = max(found_prices, key=lambda x: x[1])[0]
                                extraction_method = "dom_product_text"
                                print(f"[Instamart] Selected price from product text: ₹{price}")
                    except Exception as e:
                        print(f"[Instamart] Error extracting price from product element: {e}")
                        import traceback
                        print(f"[Instamart] Traceback: {traceback.format_exc()}")
                        pass
                
                # Strategy 2: Scan within the scoped results area and pick the best plausible price.
                if price is None:
                    price_selectors = [
                        'span:has-text("₹")',  # Try spans with ₹ first (most common)
                        'div:has-text("₹")',
                        '[class*="price" i]',
                        '[class*="Price" i]',
                        '[class*="amount" i]',
                        '[class*="cost" i]',
                        '[class*="rupee" i]',
                        'span[class*="currency" i]',
                        'div[class*="currency" i]'
                    ]
                    search_root = product_element or product_container or page
                    price_candidates = []
                    
                    for selector in price_selectors:
                        try:
                            price_elements = await search_root.query_selector_all(selector)
                            print(f"[Instamart] Found {len(price_elements)} elements with selector: {selector}")
                            # Check first few elements (should be from first product)
                            for elem in price_elements[:5]:  # Check first 5 elements
                                try:
                                    if await elem.is_visible():
                                        text = await elem.inner_text().strip()
                                        print(f"[Instamart] Checking element text: {text}")

                                        import re
                                        rupee_match = re.search(
                                            rf"{RUPEE_CLASS}\s*(\d+\.?\d*)", text, re.IGNORECASE
                                        )
                                        units_present = bool(
                                            re.search(
                                                r'\b(ml|g|kg|l|pcs?|pack|unit|piece)\b',
                                                text,
                                                re.IGNORECASE,
                                            )
                                        )

                                        price_num = None
                                        if rupee_match:
                                            price_num = rupee_match.group(1)
                                        else:
                                            if '%' in text:
                                                continue
                                            numbers = re.findall(r'(\d+\.?\d*)', text)
                                            if numbers:
                                                price_num = numbers[-1]

                                        if price_num is not None:
                                            # Don't skip when quantity-like units are present.
                                            # On Instamart tiles, the rupee symbol can be rendered as an icon/SVG,
                                            # so relying on `rupee_match` alone can otherwise lead to blanks.
                                            extracted = float(price_num)
                                            if 5.0 <= extracted <= 10000.0:
                                                price_candidates.append(extracted)
                                                print(
                                                    f"[Instamart] Found candidate price with selector {selector}: ₹{extracted} (text: {text})"
                                                )
                                except Exception as e:
                                    print(f"[Instamart] Error checking element: {e}")
                                    continue
                            
                            # keep scanning other selectors to collect more candidates
                        except Exception as e:
                            if "closed" in str(e).lower() or "Target" in str(e):
                                raise Exception(f"Browser/page was closed while extracting price: {e}")
                            print(f"[Instamart] Error with selector {selector}: {e}")
                            continue
                    
                    if price_candidates:
                        # Choose the last candidate (most likely the discounted price).
                        price = price_candidates[-1]
                        extraction_method = "dom_scoped_selector"
                        print(f"[Instamart] Selected best price from scoped DOM scan: ₹{price}")

                # Strategy 2.5: First visible Instamart product link innerText (covers shadow-less React tiles).
                if price is None:
                    try:
                        tile_blob = await page.evaluate(
                            """() => {
                              const nodes = Array.from(document.querySelectorAll('a[href*="instamart"]'));
                              for (const el of nodes) {
                                const href = el.getAttribute('href') || '';
                                if (!href.includes('/instamart/')) continue;
                                const r = el.getBoundingClientRect();
                                if (r.bottom < 0 || r.top > (window.innerHeight || 900)) continue;
                                if (r.width < 72 || r.height < 72) continue;
                                const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                                if (t.length > 14) return t.slice(0, 900);
                              }
                              return '';
                            }"""
                        )
                        if isinstance(tile_blob, str) and tile_blob.strip():
                            print(f"[Instamart] Link tile text (sample): {tile_blob[:220]}...")
                            rupee_vals = _prices_from_rupee_text(tile_blob)
                            if rupee_vals:
                                price = rupee_vals[-1]
                                extraction_method = "dom_link_tile"
                                print(f"[Instamart] Selected price from link tile text: ₹{price}")
                    except Exception as e:
                        print(f"[Instamart] Evaluate link-tile extraction failed: {e}")

                # Strategy 2.75: JS scan of first visible card's price-like nodes.
                # Handles cases where currency symbol is an icon and innerText misses the obvious ₹ marker.
                if price is None:
                    try:
                        js_prices = await page.evaluate(
                            """() => {
                              const out = [];
                              const cards = Array.from(document.querySelectorAll(
                                'a[href*="instamart"], [data-testid*="product" i], .product-card, .product-item, article, [role="article"]'
                              ));
                              const vh = window.innerHeight || 900;
                              for (const card of cards) {
                                const r = card.getBoundingClientRect();
                                if (r.width < 80 || r.height < 80) continue;
                                if (r.bottom < 0 || r.top > vh + 260) continue;
                                const txt = (card.textContent || '').replace(/\\s+/g, ' ').trim();
                                if (txt.length < 12) continue;
                                const nodes = Array.from(card.querySelectorAll(
                                  '[class*="price" i], [class*="amount" i], [class*="cost" i], span, div, p'
                                ));
                                for (const n of nodes.slice(0, 50)) {
                                  const t = (n.textContent || '').replace(/\\s+/g, ' ').trim();
                                  if (!t || t.length > 120) continue;
                                  if (/%|OFF/i.test(t)) continue;
                                  const nums = t.match(/\\d+(?:\\.\\d+)?/g) || [];
                                  for (const s of nums) {
                                    const v = Number(s);
                                    if (Number.isFinite(v) && v >= 5 && v <= 10000) out.push(v);
                                  }
                                }
                                if (out.length) break;
                              }
                              return out;
                            }"""
                        )
                        if isinstance(js_prices, list):
                            vals: List[float] = []
                            for x in js_prices:
                                try:
                                    fv = float(x)
                                    if 5.0 <= fv <= 10000.0:
                                        vals.append(fv)
                                except Exception:
                                    continue
                            if vals:
                                price = vals[-1]
                                extraction_method = "dom_js_card"
                                print(f"[Instamart] Selected price from JS card fallback: ₹{price}")
                    except Exception as e:
                        print(f"[Instamart] JS card fallback failed: {e}")
                
                # Strategy 3: Robust numeric heuristic from the tile text.
                # Instamart sometimes renders the rupee sign as an icon, so the price may be
                # present as a plain number without "₹" in the extracted DOM text.
                if price is None:
                    try:
                        root = product_element or product_container or page
                        # ElementHandle.inner_text() needs no args, but Page.inner_text() requires a selector.
                        if root is page:
                            tile_text = await page.inner_text("body")
                        else:
                            tile_text = await root.inner_text()
                        lines = [ln.strip() for ln in tile_text.splitlines() if ln.strip()]

                        import re
                        def looks_like_quantity(line: str) -> bool:
                            return bool(
                                re.search(
                                    r'\b(ml|g|kg|l|pcs?|pack|unit|piece)\b',
                                    line,
                                    re.IGNORECASE,
                                )
                            )

                        def looks_like_delivery_or_meta(line: str) -> bool:
                            # "14 MINS" etc. must not win over tile price via candidates[-1].
                            return bool(
                                re.search(
                                    r'\b(mins?|minutes?|delivery|arriving|arrives|free\s*delivery|'
                                    r'located|km\b|location|ad\b|sponsored)\b',
                                    line,
                                    re.IGNORECASE,
                                )
                            )

                        candidates: List[float] = []
                        for ln in lines:
                            # Skip discounts/percentages.
                            if '%' in ln or 'OFF' in ln.upper() or 'off' in ln:
                                continue
                            # Skip lines that clearly represent quantity.
                            if looks_like_quantity(ln):
                                continue
                            if looks_like_delivery_or_meta(ln):
                                continue

                            nums = re.findall(r'(\d+\.?\d*)', ln)
                            for n in nums:
                                try:
                                    val = float(n)
                                except Exception:
                                    continue
                                if 5.0 <= val <= 2000.0:
                                    candidates.append(val)

                        if candidates:
                            # Price on Instamart tiles is typically the last relevant rupee value.
                            price = candidates[-1]
                            extraction_method = "dom_numeric_heuristic"
                            print(f"[Instamart] Selected price from numeric tile heuristic: ₹{price}")
                    except Exception as e:
                        print(f"[Instamart] Error extracting numeric heuristic from tile text: {e}")

                # Strategy 4: Query-targeted JS extraction from visible cards.
                if price is None and query_tokens:
                    try:
                        js_price = await page.evaluate(
                            """(tokens) => {
                              const cards = Array.from(document.querySelectorAll(
                                'a[href*="instamart"], [data-testid*="product" i], .product-card, .product-item, article, [role="article"]'
                              ));
                              const vh = window.innerHeight || 900;
                              for (const card of cards) {
                                const r = card.getBoundingClientRect();
                                if (r.width < 80 || r.height < 80) continue;
                                if (r.bottom < 0 || r.top > vh + 260) continue;
                                const cardText = (card.innerText || card.textContent || '').toLowerCase();
                                if (!cardText) continue;
                                let match = false;
                                for (const tok of tokens) {
                                  if (cardText.includes(tok)) { match = true; break; }
                                }
                                if (!match) continue;

                                const nodes = Array.from(card.querySelectorAll('span, div, p, [class*="price" i], [class*="amount" i], [class*="cost" i]'));
                                const vals = [];
                                for (const n of nodes.slice(0, 60)) {
                                  const t = (n.textContent || '').replace(/\\s+/g, ' ').trim();
                                  if (!t || t.length > 120) continue;
                                  if (/%|OFF/i.test(t)) continue;
                                  const nums = t.match(/(?:₹|Rs\\.?|INR)?\\s*(\\d+(?:\\.\\d+)?)/gi) || [];
                                  for (const s of nums) {
                                    const m = s.match(/(\\d+(?:\\.\\d+)?)/);
                                    if (!m) continue;
                                    const v = Number(m[1]);
                                    if (Number.isFinite(v) && v >= 5 && v <= 10000) vals.push(v);
                                  }
                                }
                                if (vals.length) return vals[0];
                              }
                              return null;
                            }""",
                            query_tokens,
                        )
                        if js_price is not None:
                            price = float(js_price)
                            extraction_method = "dom_query_card"
                            print(f"[Instamart] Selected price from query-targeted JS fallback: ₹{price}")
                    except Exception as e:
                        print(f"[Instamart] Query-targeted JS fallback failed: {e}")
            
            # If extraction failed, capture a screenshot for debugging.
            if price is None:
                try:
                    # Use a smaller element screenshot when possible to reduce vision/OCR latency.
                    root = product_element or product_container
                    if root:
                        try:
                            await root.screenshot(path=screenshot_path)
                            print(f"[Instamart] Element screenshot saved (fallback): {screenshot_path}")
                        except Exception:
                            # Element handles can detach during rerenders; fall back to full-page capture.
                            await page.screenshot(path=screenshot_path, full_page=True)
                            print(f"[Instamart] Full page screenshot saved (fallback): {screenshot_path}")
                    else:
                        await page.screenshot(path=screenshot_path, full_page=True)
                        print(f"[Instamart] Full page screenshot saved (fallback): {screenshot_path}")
                except Exception as exc:
                    print(f"[Instamart] Failed full-page screenshot (fallback): {exc}")

            # Check availability (if price is found, assume available)
            availability = price is not None
            
            # Get product URL
            try:
                product_url = page.url
            except Exception as e:
                if "closed" in str(e).lower() or "Target" in str(e):
                    product_url = None
                else:
                    raise
            
            image_url = await self._extract_product_image_url(page, product_element)
            if image_url:
                print(f"[Instamart] Product image URL: {image_url[:120]}...")
            listing_title = await self._extract_listing_title(product_element)
            if listing_title:
                print(f"[Instamart] Listing title: {listing_title[:100]}...")

            return ProductInfo(
                platform=Platform.INSTAMART,
                price=price,
                availability=availability,
                product_url=product_url,
                listing_title=listing_title,
                image_url=image_url,
                screenshot_path=os.path.abspath(screenshot_path) if screenshot_path and os.path.isfile(screenshot_path) else screenshot_path,
                price_extraction_method=extraction_method,
            )
            
        except Exception as e:
            error_msg = str(e)
            print(f"[Instamart] Error scraping for {product_name}: {error_msg}")
            import traceback
            print(f"[Instamart] Traceback: {traceback.format_exc()}")
            return ProductInfo(
                platform=Platform.INSTAMART,
                price=None,
                availability=False,
                error=error_msg,
                screenshot_path=os.path.abspath(screenshot_path) if screenshot_path and os.path.isfile(screenshot_path) else None,
                price_extraction_method=None,
            )
        finally:
            # Always close browser context
            try:
                if playwright or browser or context or page:
                    await self._close_browser_context(playwright, browser, context, page)
            except Exception as e:
                print(f"Error in finally block: {e}")
