from typing import Optional
from playwright.async_api import Page
from models import ProductInfo, Platform
from scrapers.base_scraper import BaseScraper
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import INSTAMART_URL, INSTAMART_SEARCH_URL, DEFAULT_PINCODE, PAGE_LOAD_TIMEOUT, ELEMENT_WAIT_TIMEOUT, SEARCH_DELAY, DATA_DIR


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
                    'input[type="number"]'
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
            print(f"Error setting location for Instamart: {e}")
            return False
    
    async def search_product(self, product_name: str) -> Optional[ProductInfo]:
        """Search for a product on Instamart."""
        playwright = None
        browser = None
        context = None
        page = None
        try:
            print(f"[Instamart] Starting search for: {product_name}")
            # Create fresh browser context for this operation
            print("[Instamart] Creating browser context...")
            playwright, browser, context, page = await self._create_browser_context()
            print("[Instamart] Browser context created successfully")
            
            # Use URL-based search directly
            import random
            await asyncio.sleep(random.uniform(1, 3))
            
            search_url = f"{INSTAMART_SEARCH_URL}{product_name}"
            print(f"[Instamart] Using URL-based search: {search_url}")
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                print("[Instamart] URL-based search navigation successful")
                
                # Simulate human-like behavior
                try:
                    await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                except:
                    pass
                
                await asyncio.sleep(5 + random.uniform(0, 2))  # Wait for results to load
                
            except Exception as e:
                error_str = str(e)
                print(f"[Instamart] URL search navigation error: {error_str}")
                if "closed" in error_str.lower() or "Target" in error_str:
                    raise Exception(f"Browser/page was closed during navigation: {error_str}")
                print("[Instamart] Attempting to continue despite navigation error...")
            
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
            
            # URL-based search - no input interaction needed
            print("[Instamart] URL-based search completed, waiting for results to load...")
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
                await asyncio.sleep(SEARCH_DELAY)
                print("[Instamart] Page loaded, looking for products...")
            except Exception as e:
                if "closed" in str(e).lower() or "Target" in str(e):
                    raise Exception(f"Browser/page was closed during search: {e}")
                print(f"[Instamart] Load state wait failed (continuing): {e}")
                await asyncio.sleep(SEARCH_DELAY)
            
            # Try to find first product result - wait a bit longer and try more selectors
            print("[Instamart] Searching for product elements...")
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
                '[role="article"]',
                'div[class*="item" i]',
                'div[class*="card" i]'
            ]
            
            product_element = None
            for selector in product_selectors:
                try:
                    # Try to find multiple elements and get the FIRST visible one only
                    elements = await page.query_selector_all(selector)
                    print(f"[Instamart] Found {len(elements)} elements with selector: {selector}")
                    for elem in elements[:1]:  # Only check the FIRST element
                        try:
                            if await elem.is_visible():
                                product_element = elem
                                print(f"[Instamart] Found FIRST visible product element with selector: {selector}")
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
            print("[Instamart] Using screenshot + OCR method to extract price...")
            
            # Create screenshot directory if it doesn't exist
            screenshot_dir = os.path.join(DATA_DIR, "instamart")
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
            
            # Take screenshot
            if product_container:
                # Screenshot just the product container
                try:
                    await product_container.screenshot(path=screenshot_path)
                    print(f"[Instamart] Screenshot saved: {screenshot_path}")
                except:
                    # Fallback to full page
                    await page.screenshot(path=screenshot_path, full_page=True)
                    print(f"[Instamart] Full page screenshot saved: {screenshot_path}")
            else:
                # Full page screenshot
                await page.screenshot(path=screenshot_path, full_page=True)
                print(f"[Instamart] Full page screenshot saved: {screenshot_path}")
            
            # Extract text from screenshot using OCR
            ocr_text = self._extract_text_from_screenshot(screenshot_path)
            
            # Extract price from OCR text
            price = self._extract_price_from_ocr_text(ocr_text)
            
            # If OCR didn't find price, try traditional method as fallback
            if price is None:
                print("[Instamart] OCR didn't find price, trying traditional extraction...")
                
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
                        
                        price_found = False
                        for selector in price_selectors_in_product:
                            try:
                                price_elements = await product_element.query_selector_all(selector)
                                print(f"[Instamart] Found {len(price_elements)} price elements in product with selector: {selector}")
                                for price_elem in price_elements[:5]:  # Check first 5 price elements
                                    try:
                                        if await price_elem.is_visible():
                                            text = await price_elem.inner_text()
                                            print(f"[Instamart] Price element text: {text}")
                                            # Make sure it contains currency symbol
                                            if '₹' in text or 'Rs' in text.lower():
                                                # Check if it's not a quantity (doesn't contain g, kg, ml, etc. after the number)
                                                import re
                                                # Extract the price number
                                                price_match = re.search(r'[₹Rs]\.?\s*(\d+\.?\d*)', text, re.IGNORECASE)
                                                if price_match:
                                                    # Check if this number is followed by quantity units in the text
                                                    price_num = price_match.group(1)
                                                    # Get text after the price to check for quantity units
                                                    price_end_pos = price_match.end()
                                                    text_after_price = text[price_end_pos:price_end_pos+10].lower()
                                                    
                                                    # Skip if followed by quantity units
                                                    if re.search(r'^\s*[gkm]?g|ml|l|pcs?|pack|unit|piece', text_after_price, re.IGNORECASE):
                                                        print(f"[Instamart] Skipping {price_num} - appears to be a quantity")
                                                        continue
                                                    
                                                    extracted = float(price_num)
                                                    # Reasonable price range: ₹5 to ₹10000
                                                    if 5.0 <= extracted <= 10000.0:
                                                        price = extracted
                                                        print(f"[Instamart] Found price in product element: ₹{price} (text: {text})")
                                                        price_found = True
                                                        break
                                    except Exception as e:
                                        print(f"[Instamart] Error checking price element: {e}")
                                        continue
                                if price_found:
                                    break
                            except Exception as e:
                                print(f"[Instamart] Error with selector {selector}: {e}")
                                continue
                        
                        # If price not found in specific elements, try extracting from product text
                        if not price_found:
                            all_text = await product_element.inner_text()
                            print(f"[Instamart] Product element text: {all_text[:300]}...")
                            
                            import re
                            # Find all prices with ₹ symbol
                            price_matches = list(re.finditer(r'[₹Rs]\.?\s*(\d+\.?\d*)', all_text, re.IGNORECASE))
                            print(f"[Instamart] Found {len(price_matches)} price matches in product text")
                            
                            found_prices = []
                            for match in price_matches:
                                try:
                                    # Check the context around the match to ensure it's not a quantity
                                    start_pos = max(0, match.start() - 5)
                                    end_pos = min(len(all_text), match.end() + 15)
                                    context = all_text[start_pos:end_pos].lower()
                                    
                                    # Skip if the number is followed by quantity units (g, kg, ml, l, etc.)
                                    if re.search(r'\d+\s*[gkm]?g|ml|l|pcs?|pack|unit|piece', context, re.IGNORECASE):
                                        print(f"[Instamart] Skipping potential price {match.group(1)} - appears to be quantity in context: {context}")
                                        continue
                                    
                                    potential_price = float(match.group(1))
                                    # Prices are typically between ₹5 and ₹10000
                                    if 5.0 <= potential_price <= 10000.0:
                                        found_prices.append((potential_price, match.start()))
                                        print(f"[Instamart] Found valid price candidate: ₹{potential_price}")
                                except Exception as e:
                                    print(f"[Instamart] Error processing price match: {e}")
                                    continue
                            
                            # If we found prices, use the first one (they should be in order)
                            if found_prices:
                                price = found_prices[0][0]  # Take the first price found
                                print(f"[Instamart] Selected price from product text: ₹{price}")
                    except Exception as e:
                        print(f"[Instamart] Error extracting price from product element: {e}")
                        import traceback
                        print(f"[Instamart] Traceback: {traceback.format_exc()}")
                        pass
                
                # Strategy 2: Look for price selectors page-wide, but take FIRST price (from first product)
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
                    
                    for selector in price_selectors:
                        try:
                            price_elements = await page.query_selector_all(selector)
                            print(f"[Instamart] Found {len(price_elements)} elements with selector: {selector}")
                            # Check first few elements (should be from first product)
                            for elem in price_elements[:5]:  # Check first 5 elements
                                try:
                                    if await elem.is_visible():
                                        text = await elem.inner_text().strip()
                                        print(f"[Instamart] Checking element text: {text}")
                                        if '₹' in text or 'Rs' in text.lower():
                                            # Check if it's not a quantity
                                            import re
                                            # Extract the price number
                                            price_match = re.search(r'[₹Rs]\.?\s*(\d+\.?\d*)', text, re.IGNORECASE)
                                            if price_match:
                                                price_num = price_match.group(1)
                                                # Check if followed by quantity units
                                                price_end_pos = price_match.end()
                                                text_after = text[price_end_pos:price_end_pos+5].lower().strip()
                                                
                                                # Skip if it's a quantity (followed by g, kg, ml, etc.)
                                                if re.match(r'^[gkm]?g|ml|l|pcs?|pack|unit|piece', text_after, re.IGNORECASE):
                                                    print(f"[Instamart] Skipping {price_num} - quantity unit detected: {text_after}")
                                                    continue
                                                
                                                extracted = float(price_num)
                                                # Reasonable price range
                                                if 5.0 <= extracted <= 10000.0:
                                                    price = extracted
                                                    print(f"[Instamart] Found price with selector {selector}: ₹{price} (text: {text})")
                                                    break
                                except Exception as e:
                                    print(f"[Instamart] Error checking element: {e}")
                                    continue
                            if price:
                                break
                        except Exception as e:
                            if "closed" in str(e).lower() or "Target" in str(e):
                                raise Exception(f"Browser/page was closed while extracting price: {e}")
                            print(f"[Instamart] Error with selector {selector}: {e}")
                            continue
                
                # Strategy 3: Look for any text containing ₹ symbol (more comprehensive)
                # This is a fallback when product elements aren't found
                if price is None:
                    try:
                        # Get all text from the page
                        page_text = await page.inner_text('body')
                        print(f"[Instamart] Page text length: {len(page_text)} characters")
                        
                        # Look for price patterns in the entire page text
                        import re
                        # Find all prices with ₹ symbol
                        price_patterns = list(re.finditer(r'[₹Rs]\.?\s*(\d+\.?\d*)', page_text, re.IGNORECASE))
                        print(f"[Instamart] Found {len(price_patterns)} price patterns in page text")
                        
                        found_prices = []
                        for match in price_patterns:
                            try:
                                potential_price = float(match.group(1))
                                # Reasonable price range: ₹1 to ₹2000 for groceries
                                if 1.0 <= potential_price <= 2000.0:
                                    found_prices.append((potential_price, match.start()))
                                    print(f"[Instamart] Price candidate from page text: ₹{potential_price}")
                            except Exception as e:
                                print(f"[Instamart] Error processing price match: {e}")
                                continue
                        
                        if found_prices:
                            # Prefer the earliest occurrence (likely first product), then the lowest price
                            found_prices.sort(key=lambda x: (x[1], x[0]))
                            price = found_prices[0][0]
                            print(f"[Instamart] Selected price from page text (relaxed): ₹{price}")
                    except Exception as e:
                        print(f"[Instamart] Error extracting from page text: {e}")
                        import traceback
                        print(f"[Instamart] Traceback: {traceback.format_exc()}")
                        pass
            
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
            
            return ProductInfo(
                platform=Platform.INSTAMART,
                price=price,
                availability=availability,
                product_url=product_url
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
                error=error_msg
            )
        finally:
            # Always close browser context
            try:
                if playwright or browser or context or page:
                    await self._close_browser_context(playwright, browser, context, page)
            except Exception as e:
                print(f"Error in finally block: {e}")
