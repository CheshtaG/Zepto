from abc import ABC, abstractmethod
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, Playwright
from models import ProductInfo, Platform
import asyncio


class BaseScraper(ABC):
    def __init__(self):
        pass
    
    async def _create_browser_context(self):
        """Create a new browser and page for each operation with anti-detection measures."""
        import tempfile
        import os
        import random
        
        playwright = await async_playwright().start()
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                print(f"[Browser] Launch attempt {attempt + 1}/{max_retries}")
                
                # Use Firefox (more stable on macOS, Chromium has issues)
                print("[Browser] Attempting to launch Firefox...")
                browser = await playwright.firefox.launch(
                    headless=True,
                    timeout=90000
                )
                print("[Browser] ✓ Firefox launched successfully")
                
                # Small delay to ensure browser is fully ready
                await asyncio.sleep(1)
                
                # Simple context with minimal configuration
                print("[Browser] Creating browser context...")
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='Asia/Kolkata',
                    ignore_https_errors=True
                )
                print("[Browser] ✓ Context created successfully")
                
                print("[Browser] Creating new page...")
                page = await context.new_page()
                print("[Browser] ✓ Page created successfully")
                
                print(f"[Browser] Successfully launched on attempt {attempt + 1}")
                return playwright, browser, context, page
                
            except Exception as e:
                error_str = str(e)
                import traceback
                print(f"[Browser] Attempt {attempt + 1} failed: {error_str}")
                print(f"[Browser] Full traceback:")
                traceback.print_exc()
                
                # Clean up failed attempt
                try:
                    if 'browser' in locals():
                        await browser.close()
                except:
                    pass
                try:
                    if 'context' in locals():
                        await context.close()
                except:
                    pass
                
                if attempt < max_retries - 1:
                    print(f"[Browser] Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Final attempt failed
                    try:
                        await playwright.stop()
                    except:
                        pass
                    raise Exception(f"Failed to launch browser after {max_retries} attempts: {error_str}")
        
        # Should never reach here, but just in case
        try:
            await playwright.stop()
        except:
            pass
        raise Exception("Failed to launch browser")
    
    async def _close_browser_context(self, playwright, browser, context, page):
        """Close browser, page, context, and playwright."""
        import shutil
        try:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
        except Exception:
            pass
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
        
        # Remove currency symbols and commas
        price_text = price_text.replace('₹', '').replace(',', '').replace('Rs.', '').replace('Rs', '').strip()
        
        # Extract numbers
        import re
        numbers = re.findall(r'\d+\.?\d*', price_text)
        if numbers:
            try:
                return float(numbers[0])
            except:
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
        
        # Look for patterns like: ₹60, ₹ 60, Rs. 60, 60.00, etc.
        # Try to find price patterns near currency symbols
        price_patterns = [
            r'₹\s*(\d+\.?\d*)',  # ₹60, ₹ 60
            r'Rs\.?\s*(\d+\.?\d*)',  # Rs. 60, Rs 60
            r'(\d+\.?\d*)\s*₹',  # 60 ₹
            r'(\d+\.?\d*)\s*Rs',  # 60 Rs
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, ocr_text, re.IGNORECASE)
            if matches:
                try:
                    # Take the first match (usually the most prominent price)
                    price = float(matches[0])
                    # Filter out unrealistic prices (too high or too low)
                    if 1.0 <= price <= 10000.0:
                        print(f"[OCR] Found price: ₹{price}")
                        return price
                except ValueError:
                    continue
        
        # Fallback: look for any number that might be a price
        # This is less reliable but might catch prices without currency symbols
        numbers = re.findall(r'\b(\d+\.?\d{0,2})\b', ocr_text)
        for num_str in numbers[:5]:  # Check first 5 numbers
            try:
                num = float(num_str)
                # Reasonable price range for grocery items
                if 10.0 <= num <= 1000.0:
                    print(f"[OCR] Found potential price: ₹{num}")
                    return num
            except ValueError:
                continue
        
        print("[OCR] No price found in OCR text")
        return None
