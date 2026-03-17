from typing import Optional
from playwright.async_api import Page
from models import ProductInfo, Platform
from scrapers.base_scraper import BaseScraper
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BLINKIT_URL, BLINKIT_SEARCH_URL, DEFAULT_PINCODE, PAGE_LOAD_TIMEOUT, ELEMENT_WAIT_TIMEOUT, SEARCH_DELAY, DATA_DIR


class BlinkitScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = BLINKIT_URL
    
    async def set_location(self, page: Page):
        """Set location to Pune for Blinkit. Assumes page is already navigated."""
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
                'input[placeholder*="pincode" i]',
                'input[placeholder*="Enter delivery location" i]'
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
                            await search_input.fill("Pune")
                            await asyncio.sleep(SEARCH_DELAY)
                            
                            # Click on Pune option
                            pune_option = await page.wait_for_selector('text=Pune', timeout=3000)
                            if pune_option:
                                await pune_option.click()
                                await asyncio.sleep(SEARCH_DELAY)
                                location_set = True
                                break
                except:
                    continue
            
            # If location picker didn't work, try pincode
            if not location_set:
                pune_pincode = DEFAULT_PINCODE
                pincode_selectors = [
                    'input[placeholder*="pincode" i]',
                    'input[placeholder*="pin" i]',
                    'input[type="text"]',
                    'input[type="number"]',
                    'input[placeholder*="Enter delivery location" i]'
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
                    except:
                        continue
            
            return location_set
        except Exception as e:
            print(f"Error setting location for Blinkit: {e}")
            return False
    
    async def search_product(self, product_name: str) -> Optional[ProductInfo]:
        """Search for a product on Blinkit."""
        playwright = None
        browser = None
        context = None
        page = None
        try:
            print(f"[Blinkit] Starting search for: {product_name}")
            # Create fresh browser context for this operation
            print("[Blinkit] Creating browser context...")
            playwright, browser, context, page = await self._create_browser_context()
            print("[Blinkit] Browser context created successfully")
            
            # Add random delay before navigation to avoid detection
            import random
            await asyncio.sleep(random.uniform(1, 3))
            
            # Use URL-based search directly
            search_url = f"{BLINKIT_SEARCH_URL}{product_name}"
            print(f"[Blinkit] Trying URL-based search: {search_url}")
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                print("[Blinkit] URL-based search navigation successful")
                
                # Simulate human-like behavior
                try:
                    await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                except:
                    pass
                
                await asyncio.sleep(5 + random.uniform(0, 2))  # Wait for results to load
                # Check if we got results directly
                product_check = await page.query_selector_all('[class*="product" i], [class*="Product" i], [data-testid*="product" i]')
                if len(product_check) > 0:
                    print(f"[Blinkit] Found {len(product_check)} products via URL search, skipping input search")
                    # Skip to product extraction
                    search_input = "URL_SEARCH"  # Marker to skip input search
                else:
                    # Navigate to base URL and try input search
                    print("[Blinkit] No products found via URL, trying input search...")
                    await page.goto(self.base_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                    await asyncio.sleep(SEARCH_DELAY)
                    search_input = None
            except Exception as url_error:
                print(f"[Blinkit] URL search failed: {url_error}, trying base URL...")
                # Navigate to the page (this will also handle location if needed)
                print(f"[Blinkit] Navigating to: {self.base_url}")
                try:
                    await page.goto(self.base_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                    print("[Blinkit] Initial navigation successful")
                    await asyncio.sleep(SEARCH_DELAY)
                    search_input = None
                    
                    # Try to set location (but don't fail if it doesn't work)
                    print("[Blinkit] Attempting to set location...")
                    try:
                        location_set = await self.set_location(page)
                        if location_set:
                            print("[Blinkit] Location set successfully")
                        else:
                            print("[Blinkit] Location setting skipped (not critical)")
                    except Exception as loc_error:
                        print(f"[Blinkit] Location setting failed (non-critical): {loc_error}")
                except Exception as e:
                    error_str = str(e)
                    print(f"[Blinkit] Navigation error: {error_str}")
                    if "closed" in error_str.lower() or "Target" in error_str:
                        raise Exception(f"Browser/page was closed during navigation: {error_str}")
                    print("[Blinkit] Attempting to continue despite navigation error...")
            
            # If URL search worked, skip input finding
            if search_input == "URL_SEARCH":
                print("[Blinkit] Using URL-based search results")
            else:
                # Wait a bit more for page to fully load and handle any modals/popups
                await asyncio.sleep(3)
                
                # Try to close any popups/modals that might be blocking
                try:
                    close_buttons = await page.query_selector_all('button[aria-label*="close" i], button[aria-label*="Close" i], .close, [class*="close"], [class*="modal-close"]')
                    for btn in close_buttons[:3]:  # Try first 3 close buttons
                        try:
                            if await btn.is_visible():
                                await btn.click()
                                await asyncio.sleep(1)
                        except:
                            pass
                except:
                    pass
                
                # Find search input - try multiple strategies
                print("[Blinkit] Looking for search input...")
                search_selectors = [
                    '[data-testid*="search" i]',  # Try data-testid first (most reliable)
                    'input[placeholder*="search" i]',
                    'input[placeholder*="Search" i]',
                    'input[type="search"]',
                    'input[type="text"][placeholder*="search" i]',
                    'input[type="text"][placeholder*="Search" i]',
                    'input[name*="search" i]',
                    '[data-testid="search-input"]',
                    'input[class*="search" i]',
                    'input[aria-label*="search" i]',
                    'input[aria-label*="Search" i]',
                    'button[aria-label*="search" i]',  # Sometimes it's a button
                    'a[href*="search" i]',  # Sometimes it's a link
                    'input'  # Last resort - any input
                ]
                
                search_input = None
                for selector in search_selectors:
                    try:
                        # Try query_selector_all first to find all matches, then check visibility
                        elements = await page.query_selector_all(selector)
                        print(f"[Blinkit] Found {len(elements)} elements with selector: {selector}")
                        for elem in elements[:10]:  # Check first 10 elements
                            try:
                                if await elem.is_visible():
                                    search_input = elem
                                    print(f"[Blinkit] Found visible search input with selector: {selector}")
                                    break
                            except:
                                continue
                        if search_input:
                            break
                    except Exception as e:
                        if "closed" in str(e).lower() or "Target" in str(e):
                            print(f"[Blinkit] Browser closed while searching for input: {e}")
                            raise Exception(f"Browser/page was closed while searching for input: {e}")
                        continue
                
                # If no search input found, skip to screenshot method
                if not search_input:
                    print("[Blinkit] Search input not found, will use screenshot method directly")
                    search_input = None  # Will skip to screenshot method
            
            # Skip this section if URL search was used
            if search_input == "URL_SEARCH":
                print("[Blinkit] URL search used, skipping input interaction")
            elif search_input:
                # Check if it's actually an input element, if not, click it first to open search
                tag_name = None
                try:
                    tag_name = await search_input.evaluate('el => el.tagName.toLowerCase()')
                    print(f"[Blinkit] Search element tag: {tag_name}")
                except Exception as eval_error:
                    # If evaluate fails, try to get tag name differently or assume it's not an input
                    print(f"[Blinkit] Could not evaluate tag name: {eval_error}, trying click directly...")
                    tag_name = "unknown"
                
                input_found = False
                if tag_name and tag_name != 'input' and tag_name != 'textarea':
                    # It's probably a button/div - click it using JavaScript to open the search
                    print("[Blinkit] Clicking search element to open search (using JS)...")
                    try:
                        await search_input.evaluate('el => el.click()')
                        await asyncio.sleep(2)
                    except Exception as click_error:
                        # Try regular click as fallback
                        try:
                            await search_input.click(timeout=5000)
                            await asyncio.sleep(2)
                        except Exception as click_error2:
                            print(f"[Blinkit] Both JS and regular click failed: {click_error2}")
                            # Continue anyway - might still work
                            pass
                
                # Now try to find the actual input
                actual_input_selectors = [
                    'input[type="search"]',
                    'input[type="text"]',
                    'input[placeholder*="search" i]',
                    'input[placeholder*="Search" i]',
                    'input'
                ]
                for selector in actual_input_selectors:
                    try:
                        actual_input = await page.wait_for_selector(selector, timeout=5000, state='visible')
                        if actual_input and await actual_input.is_visible():
                            search_input = actual_input
                            input_found = True
                            print(f"[Blinkit] Found actual input after clicking: {selector}")
                            break
                    except:
                        continue
                
                # If still no input found after clicking
                if not input_found:
                    print("[Blinkit] Could not find input after clicking, will use screenshot method")
                    search_input = None  # Will skip to screenshot method
            
            # Enter product name and search (only if we have a valid input and not URL search)
            if search_input and search_input != "URL_SEARCH" and search_input is not None:
                print(f"[Blinkit] Entering search term: {product_name}")
                try:
                    await search_input.fill(product_name)
                    await asyncio.sleep(1)
                    print("[Blinkit] Pressing Enter to search...")
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(5)  # Wait longer for search results
                except Exception as fill_error:
                    print(f"[Blinkit] Fill failed, trying type instead: {fill_error}")
                    try:
                        await search_input.focus()
                        await page.keyboard.type(product_name, delay=100)
                        await asyncio.sleep(1)
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(5)
                    except:
                        print("[Blinkit] Search input interaction failed, will use screenshot method")
                
                # Wait for results to load
                print("[Blinkit] Waiting for search results to load...")
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await asyncio.sleep(SEARCH_DELAY)
                    print("[Blinkit] Page loaded, looking for products...")
                except Exception as e:
                    print(f"[Blinkit] Load state wait failed (continuing): {e}")
                    await asyncio.sleep(SEARCH_DELAY)
            else:
                print("[Blinkit] No search input available, will use screenshot method on current page")
            
            # Try to find first product result - wait longer and try more selectors
            print("[Blinkit] Searching for product elements...")
            await asyncio.sleep(2)  # Give page more time to render
            
            product_selectors = [
                '[data-testid*="product" i]',
                '[data-testid*="Product" i]',
                '.product-card',
                '.product-item',
                '[class*="product" i]',
                '[class*="Product" i]',
                'article',
                'div[class*="ProductCard" i]',
                'div[class*="product-card" i]',
                '[class*="ProductTile" i]',
                '[role="article"]',
                'div[class*="item" i]',
                'div[class*="card" i]',
                'a[href*="product" i]',
                'div[class*="grid" i] > div',  # Generic grid items
            ]
            
            product_element = None
            for selector in product_selectors:
                try:
                    # Try to find multiple elements and get the first visible one
                    elements = await page.query_selector_all(selector)
                    print(f"[Blinkit] Found {len(elements)} elements with selector: {selector}")
                    for elem in elements[:15]:  # Check first 15 elements
                        try:
                            if await elem.is_visible():
                                product_element = elem
                                print(f"[Blinkit] Found visible product element with selector: {selector}")
                                break
                        except:
                            continue
                    if product_element:
                        break
                except Exception as e:
                    if "closed" in str(e).lower() or "Target" in str(e):
                        raise Exception(f"Browser/page was closed while finding product: {e}")
                    continue
            
            # Use screenshot + OCR method to extract price
            print("[Blinkit] Using screenshot + OCR method to extract price...")
            
            # Create screenshot directory if it doesn't exist
            screenshot_dir = os.path.join(DATA_DIR, "blinkit")
            os.makedirs(screenshot_dir, exist_ok=True)
            
            # Take screenshot of the page (focus on product listing area if possible)
            screenshot_path = os.path.join(screenshot_dir, f"{product_name.replace(' ', '_')}_search.png")
            
            # Try to find product listing container for better screenshot
            product_container = None
            container_selectors = [
                '[class*="product-list" i]',
                '[class*="ProductList" i]',
                '[class*="search-results" i]',
                '[class*="results" i]',
                '[class*="grid" i]',
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
                            print(f"[Blinkit] Found product container: {selector}")
                            break
                    if product_container:
                        break
                except:
                    continue
            
            # Take screenshot
            if product_container:
                # Screenshot just the product container
                try:
                    await product_container.screenshot(path=screenshot_path)
                    print(f"[Blinkit] Screenshot saved: {screenshot_path}")
                except:
                    # Fallback to full page
                    await page.screenshot(path=screenshot_path, full_page=True)
                    print(f"[Blinkit] Full page screenshot saved: {screenshot_path}")
            else:
                # Full page screenshot
                await page.screenshot(path=screenshot_path, full_page=True)
                print(f"[Blinkit] Full page screenshot saved: {screenshot_path}")
            
            # Extract text from screenshot using OCR
            ocr_text = self._extract_text_from_screenshot(screenshot_path)
            
            # Extract price from OCR text
            price = self._extract_price_from_ocr_text(ocr_text)
            
            # If OCR didn't find price, try traditional method as fallback
            if price is None:
                print("[Blinkit] OCR didn't find price, trying traditional extraction...")
                if product_element:
                    price_selectors = [
                        '[class*="price" i]',
                        '[class*="Price" i]',
                        'span:has-text("₹")',
                        'div:has-text("₹")',
                        '[class*="ProductPrice" i]',
                        '[class*="amount" i]',
                        '[class*="cost" i]'
                    ]
                    
                    price_text = None
                    # First try to find price within the product element
                    try:
                        price_in_product = await product_element.query_selector_all('span, div, p')
                        for elem in price_in_product[:10]:
                            try:
                                text = await elem.inner_text()
                                if '₹' in text or 'Rs' in text.lower():
                                    import re
                                    if re.search(r'[₹Rs]?\s*\d+', text):
                                        price_text = text
                                        break
                            except:
                                continue
                    except:
                        pass
                    
                    # If not found in product element, try page-wide
                    if not price_text:
                        for selector in price_selectors:
                            try:
                                price_elements = await page.query_selector_all(selector)
                                for elem in price_elements[:10]:
                                    try:
                                        text = await elem.inner_text()
                                        if '₹' in text or 'Rs' in text.lower():
                                            price_text = text
                                            break
                                    except:
                                        continue
                                if price_text:
                                    break
                            except:
                                continue
                    
                    price = self._extract_price(price_text) if price_text else None
            
            # Check availability (if price is found, assume available)
            availability = price is not None
            
            # Get product URL
            product_url = page.url
            
            return ProductInfo(
                platform=Platform.BLINKIT,
                price=price,
                availability=availability,
                product_url=product_url
            )
            
        except Exception as e:
            print(f"Error scraping Blinkit for {product_name}: {e}")
            return ProductInfo(
                platform=Platform.BLINKIT,
                price=None,
                availability=False,
                error=str(e)
            )
        finally:
            # Always close browser context
            try:
                if playwright or browser or context or page:
                    await self._close_browser_context(playwright, browser, context, page)
            except Exception as e:
                print(f"Error in finally block: {e}")
