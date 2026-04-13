from typing import Optional
from playwright.async_api import Page
from models import ProductInfo, Platform
from scrapers.base_scraper import BaseScraper
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ZEPTO_URL, ZEPTO_SEARCH_URL, DEFAULT_PINCODE, PAGE_LOAD_TIMEOUT, ELEMENT_WAIT_TIMEOUT, SEARCH_DELAY, DATA_DIR


class ZeptoScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = ZEPTO_URL

    async def set_location(self, page: Page):
        """Set location to Pune for Zepto. Assumes page is already navigated."""
        try:
            await asyncio.sleep(1)

            location_selectors = [
                'button:has-text("Pune")',
                'button:has-text("Change")',
                '[data-testid="location-picker"]',
                'input[placeholder*="location" i]',
                'input[placeholder*="area" i]',
                'input[placeholder*="pincode" i]',
                'input[placeholder*="Enter delivery location" i]',
            ]

            location_set = False

            for selector in location_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=ELEMENT_WAIT_TIMEOUT)
                    if element:
                        await element.click()
                        await asyncio.sleep(1)

                        search_input = await page.wait_for_selector('input[type="text"], input[type="search"]', timeout=3000)
                        if search_input:
                            city = self.target_city or "Pune"
                            await search_input.fill(city)
                            await asyncio.sleep(SEARCH_DELAY)

                            pune_option = await page.wait_for_selector(f"text={city}", timeout=3000)
                            if pune_option:
                                await pune_option.click()
                                await asyncio.sleep(SEARCH_DELAY)
                                location_set = True
                                break
                except Exception:
                    continue

            if not location_set:
                pune_pincode = self.target_pincode or DEFAULT_PINCODE
                pincode_selectors = [
                    'input[placeholder*="pincode" i]',
                    'input[placeholder*="pin" i]',
                    'input[type="text"]',
                    'input[type="number"]',
                    'input[placeholder*="Enter delivery location" i]',
                ]

                for selector in pincode_selectors:
                    try:
                        element = await page.wait_for_selector(selector, timeout=3000)
                        if element:
                            await element.fill(pune_pincode)
                            await page.keyboard.press("Enter")
                            await asyncio.sleep(3)
                            location_set = True
                            break
                    except Exception:
                        continue

            return location_set
        except Exception as e:
            print(f"Error setting location for Zepto: {e}")
            return False

    async def search_product(self, product_name: str) -> Optional[ProductInfo]:
        """Search for a product on Zepto."""
        playwright = None
        browser = None
        context = None
        page = None
        try:
            print(f"[Zepto] Starting search for: {product_name}")
            print("[Zepto] Creating browser context...")
            playwright, browser, context, page = await self._create_browser_context()
            print("[Zepto] Browser context created successfully")

            import random

            await asyncio.sleep(random.uniform(1, 3))

            search_url = f"{ZEPTO_SEARCH_URL}{product_name}"
            print(f"[Zepto] Trying URL-based search: {search_url}")
            search_input = None
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                print("[Zepto] URL-based search navigation successful")

                try:
                    await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                except Exception:
                    pass

                await asyncio.sleep(5 + random.uniform(0, 2))
                product_check = await page.query_selector_all(
                    '[class*="product" i], [class*="Product" i], [data-testid*="product" i]'
                )
                if len(product_check) > 0:
                    print(f"[Zepto] Found {len(product_check)} products via URL search, skipping input search")
                    search_input = "URL_SEARCH"
                else:
                    print("[Zepto] No products found via URL, trying input search...")
                    await page.goto(self.base_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                    await asyncio.sleep(SEARCH_DELAY)
                    search_input = None
            except Exception as url_error:
                print(f"[Zepto] URL search failed: {url_error}, trying base URL...")
                print(f"[Zepto] Navigating to: {self.base_url}")
                try:
                    await page.goto(self.base_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                    print("[Zepto] Initial navigation successful")
                    await asyncio.sleep(SEARCH_DELAY)
                    search_input = None

                    print("[Zepto] Attempting to set location...")
                    try:
                        location_set = await self.set_location(page)
                        if location_set:
                            print("[Zepto] Location set successfully")
                        else:
                            print("[Zepto] Location setting skipped (not critical)")
                    except Exception as loc_error:
                        print(f"[Zepto] Location setting failed (non-critical): {loc_error}")
                except Exception as e:
                    error_str = str(e)
                    print(f"[Zepto] Navigation error: {error_str}")
                    if "closed" in error_str.lower() or "Target" in error_str:
                        raise Exception(f"Browser/page was closed during navigation: {error_str}")
                    print("[Zepto] Attempting to continue despite navigation error...")

            if search_input == "URL_SEARCH":
                print("[Zepto] Using URL-based search results")
                # Same as Blinkit: URL search can still leave a location modal; without an address,
                # listings/prices often never hydrate in the DOM.
                try:
                    print("[Zepto] Attempting to set location (URL-search path)...")
                    await self.set_location(page)
                except Exception as loc_error:
                    print(f"[Zepto] Location setting failed (non-critical, URL path): {loc_error}")
            else:
                await asyncio.sleep(3)

                try:
                    close_buttons = await page.query_selector_all(
                        'button[aria-label*="close" i], button[aria-label*="Close" i], .close, [class*="close"], [class*="modal-close"]'
                    )
                    for btn in close_buttons[:3]:
                        try:
                            if await btn.is_visible():
                                await btn.click()
                                await asyncio.sleep(1)
                        except Exception:
                            pass
                except Exception:
                    pass

                print("[Zepto] Looking for search input...")
                search_selectors = [
                    'input[placeholder*="search" i]',
                    'input[placeholder*="Search" i]',
                    'input[type="search"]',
                    'input[type="text"][placeholder*="search" i]',
                    'input[type="text"][placeholder*="Search" i]',
                    'input[name*="search" i]',
                    '[data-testid="search-input"]',
                    '[data-testid*="search" i]',
                    'input[class*="search" i]',
                    'input[aria-label*="search" i]',
                    'input[aria-label*="Search" i]',
                    "input",
                ]

                search_input = None
                for selector in search_selectors:
                    try:
                        search_input = await page.wait_for_selector(selector, timeout=5000, state="visible")
                        if search_input:
                            is_visible = await search_input.is_visible()
                            if is_visible:
                                print(f"[Zepto] Found search input with selector: {selector}")
                                break
                            search_input = None
                    except Exception as e:
                        if "closed" in str(e).lower() or "Target" in str(e):
                            print(f"[Zepto] Browser closed while searching for input: {e}")
                            raise Exception(f"Browser/page was closed while searching for input: {e}")
                        continue

                if not search_input:
                    return ProductInfo(
                        platform=Platform.ZEPTO,
                        price=None,
                        availability=False,
                        error="Search input not found",
                    )

                tag_name = None
                try:
                    tag_name = await search_input.evaluate("el => el.tagName.toLowerCase()")
                    print(f"[Zepto] Search element tag: {tag_name}")
                except Exception as eval_error:
                    print(f"[Zepto] Could not evaluate tag name: {eval_error}, trying click directly...")
                    tag_name = "unknown"

                input_found = False
                if tag_name and tag_name != "input" and tag_name != "textarea":
                    print("[Zepto] Clicking search element to open search (using JS)...")
                    try:
                        await search_input.evaluate("el => el.click()")
                        await asyncio.sleep(2)
                    except Exception as click_error:
                        try:
                            await search_input.click(timeout=5000)
                            await asyncio.sleep(2)
                        except Exception as click_error2:
                            print(f"[Zepto] Both JS and regular click failed: {click_error2}")

                    actual_input_selectors = [
                        "input[type=\"search\"]",
                        "input[type=\"text\"]",
                        'input[placeholder*="search" i]',
                        'input[placeholder*="Search" i]',
                        "input",
                    ]
                    for selector in actual_input_selectors:
                        try:
                            actual_input = await page.wait_for_selector(selector, timeout=5000, state="visible")
                            if actual_input and await actual_input.is_visible():
                                search_input = actual_input
                                input_found = True
                                print(f"[Zepto] Found actual input after clicking: {selector}")
                                break
                        except Exception:
                            continue

                    if not input_found:
                        print("[Zepto] Could not find input after clicking")
                        search_input = None

                    if not search_input:
                        print("[Zepto] Trying alternative search methods...")
                        try:
                            search_buttons = await page.query_selector_all(
                                'button[aria-label*="search" i], button[class*="search" i], [role="search"]'
                            )
                            if search_buttons:
                                print(f"[Zepto] Found {len(search_buttons)} potential search buttons")
                                await search_buttons[0].click()
                                await asyncio.sleep(2)
                                search_input = await page.wait_for_selector(
                                    'input[type="search"], input[type="text"]', timeout=3000
                                )
                        except Exception:
                            pass

                    if not search_input:
                        return ProductInfo(
                            platform=Platform.ZEPTO,
                            price=None,
                            availability=False,
                            error="Search input not found after all attempts",
                        )

                    print(f"[Zepto] Entering search term: {product_name}")
                    await search_input.fill(product_name)
                    await asyncio.sleep(1)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(5)

                    print("[Zepto] Waiting for search results to load...")
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15000)
                        await asyncio.sleep(SEARCH_DELAY)
                    except Exception:
                        await asyncio.sleep(SEARCH_DELAY)
                else:
                    print(f"[Zepto] Entering search term (direct input): {product_name}")
                    await search_input.fill(product_name)
                    await asyncio.sleep(1)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(5)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15000)
                        await asyncio.sleep(SEARCH_DELAY)
                    except Exception:
                        await asyncio.sleep(SEARCH_DELAY)

            print("[Zepto] Searching for product elements...")
            await self._wait_for_spa_dom_commit(page)
            await asyncio.sleep(0.5)

            product_selectors = [
                '[data-testid*="product" i]',
                '[data-testid*="Product" i]',
                ".product-card",
                ".product-item",
                '[class*="product" i]',
                '[class*="Product" i]',
                "article",
                'div[class*="ProductCard" i]',
                'div[class*="product-card" i]',
                '[class*="ProductTile" i]',
                '[role="article"]',
                'div[class*="item" i]',
                'div[class*="card" i]',
                'a[href*="product" i]',
                'div[class*="grid" i] > div',
            ]

            product_element = None
            for selector in product_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    print(f"[Zepto] Found {len(elements)} elements with selector: {selector}")
                    for elem in elements[:15]:
                        try:
                            if await elem.is_visible():
                                product_element = elem
                                print(f"[Zepto] Found visible product element with selector: {selector}")
                                break
                        except Exception:
                            continue
                    if product_element:
                        break
                except Exception as e:
                    if "closed" in str(e).lower() or "Target" in str(e):
                        raise Exception(f"Browser/page was closed while finding product: {e}")
                    continue

            screenshot_dir = os.path.join(DATA_DIR, "zepto")
            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_path = os.path.join(screenshot_dir, f"{product_name.replace(' ', '_')}_search.png")

            product_container = None
            container_selectors = [
                '[class*="product-list" i]',
                '[class*="ProductList" i]',
                '[class*="search-results" i]',
                '[class*="results" i]',
                '[class*="grid" i]',
                "main",
                "article",
                'div[class*="container" i]',
            ]

            for selector in container_selectors:
                try:
                    containers = await page.query_selector_all(selector)
                    for container in containers[:5]:
                        if await container.is_visible():
                            product_container = container
                            print(f"[Zepto] Found product container: {selector}")
                            break
                    if product_container:
                        break
                except Exception:
                    continue

            price_selectors = [
                '[class*="price" i]',
                '[class*="Price" i]',
                'span:has-text("₹")',
                'div:has-text("₹")',
                '[class*="ProductPrice" i]',
                '[class*="amount" i]',
                '[class*="cost" i]',
            ]

            extraction_method = "none"
            price = None
            price = await self._extract_price_vdom_from_element(product_element)
            if price is not None:
                extraction_method = "vdom_element"
            if price is None:
                price = await self._extract_price_vdom_first_product_card(page)
                if price is not None:
                    extraction_method = "vdom_first_card"
            if price is None:
                price = await self._extract_price_dom_playwright(
                    page, product_element, price_selectors
                )
                if price is not None:
                    extraction_method = "dom"

            # Rest (unchanged): screenshot + OCR
            if price is None:
                print("[Zepto] VDOM/DOM didn't find price, trying OCR fallback...")
                if product_container:
                    try:
                        await product_container.screenshot(path=screenshot_path)
                        print(f"[Zepto] Screenshot saved: {screenshot_path}")
                    except Exception:
                        await page.screenshot(path=screenshot_path, full_page=True)
                        print(f"[Zepto] Full page screenshot saved: {screenshot_path}")
                else:
                    await page.screenshot(path=screenshot_path, full_page=True)
                    print(f"[Zepto] Full page screenshot saved: {screenshot_path}")
                ocr_text = self._extract_text_from_screenshot(screenshot_path)
                price = self._extract_price_from_ocr_text(ocr_text)
                if price is not None:
                    extraction_method = "ocr_fallback_after_dom"

            availability = price is not None

            product_url = page.url

            listing_title = await self._extract_listing_title(product_element)
            if listing_title:
                print(f"[Zepto] Listing title: {listing_title[:100]}...")
            quantity_label = await self._extract_quantity_label(product_element, listing_title)
            brand = self._extract_brand_from_title(listing_title or product_name)
            image_resolution = await self._resolve_product_image(
                page=page,
                root=product_element,
                platform=Platform.ZEPTO,
                query=product_name,
                listing_title=listing_title,
                quantity_label=quantity_label,
                brand=brand,
                product_url=product_url,
            )
            image_url = image_resolution.get("image_url")
            if image_url:
                print(f"[Zepto] Product image URL ({image_resolution.get('image_source')}): {str(image_url)[:120]}...")
            else:
                print(f"[Zepto] No confident product image; source={image_resolution.get('image_source')}")
            candidate_listings = await self._candidate_listings_with_primary(
                page, Platform.ZEPTO, product_selectors, product_element, 10
            )
            if product_element:
                link = await self._product_link_from_root(product_element)
                if link:
                    product_url = link

            return ProductInfo(
                platform=Platform.ZEPTO,
                price=price,
                availability=availability,
                product_url=product_url,
                listing_title=listing_title,
                image_url=image_url,
                image_source=image_resolution.get("image_source"),
                image_confidence=image_resolution.get("image_confidence"),
                image_match_reason=image_resolution.get("image_match_reason"),
                image_debug=image_resolution.get("image_debug"),
                price_extraction_method=extraction_method,
                quantity_label=quantity_label,
                candidate_listings=candidate_listings or None,
            )

        except Exception as e:
            print(f"Error scraping Zepto for {product_name}: {e}")
            return ProductInfo(
                platform=Platform.ZEPTO,
                price=None,
                availability=False,
                error=str(e),
                price_extraction_method=None,
            )
        finally:
            try:
                if playwright or browser or context or page:
                    await self._close_browser_context(playwright, browser, context, page)
            except Exception as e:
                print(f"Error in finally block: {e}")
