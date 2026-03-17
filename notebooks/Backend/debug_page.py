"""
Debug script to capture page structure and help identify correct selectors
"""
import asyncio
from scrapers.base_scraper import BaseScraper
from playwright.async_api import async_playwright

async def debug_page(url, platform_name):
    """Capture page HTML and structure for debugging"""
    playwright = await async_playwright().start()
    try:
        browser = await playwright.firefox.launch(headless=False)  # Non-headless to see what's happening
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        print(f"\n=== Debugging {platform_name} ===")
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)  # Wait for page to load
        
        # Get page title
        title = await page.title()
        print(f"Page title: {title}")
        
        # Try to find search inputs
        print("\n--- Searching for input elements ---")
        all_inputs = await page.query_selector_all('input')
        print(f"Found {len(all_inputs)} input elements")
        for i, inp in enumerate(all_inputs[:10]):  # First 10
            try:
                placeholder = await inp.get_attribute('placeholder') or 'N/A'
                input_type = await inp.get_attribute('type') or 'N/A'
                name = await inp.get_attribute('name') or 'N/A'
                class_name = await inp.get_attribute('class') or 'N/A'
                data_testid = await inp.get_attribute('data-testid') or 'N/A'
                is_visible = await inp.is_visible()
                print(f"  Input {i+1}: type={input_type}, placeholder={placeholder}, name={name}, visible={is_visible}")
                print(f"    class={class_name[:50]}, data-testid={data_testid}")
            except:
                pass
        
        # Try to find buttons
        print("\n--- Searching for button elements ---")
        all_buttons = await page.query_selector_all('button')
        print(f"Found {len(all_buttons)} button elements")
        for i, btn in enumerate(all_buttons[:10]):  # First 10
            try:
                text = await btn.inner_text() or 'N/A'
                aria_label = await btn.get_attribute('aria-label') or 'N/A'
                class_name = await btn.get_attribute('class') or 'N/A'
                data_testid = await btn.get_attribute('data-testid') or 'N/A'
                is_visible = await btn.is_visible()
                if 'search' in text.lower() or 'search' in aria_label.lower() or 'search' in class_name.lower():
                    print(f"  Button {i+1} (SEARCH-RELATED): text={text[:30]}, aria-label={aria_label}, visible={is_visible}")
                    print(f"    class={class_name[:50]}, data-testid={data_testid}")
            except:
                pass
        
        # Save page HTML
        html = await page.content()
        filename = f"debug_{platform_name.lower()}_page.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"\nPage HTML saved to: {filename}")
        
        # Take screenshot
        screenshot_path = f"debug_{platform_name.lower()}_screenshot.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"Screenshot saved to: {screenshot_path}")
        
        print("\nPress Enter to close browser...")
        input()
        
        await browser.close()
    finally:
        await playwright.stop()

if __name__ == "__main__":
    from config import INSTAMART_URL, BLINKIT_URL, ZEPTO_URL
    
    print("Choose platform to debug:")
    print("1. Instamart")
    print("2. Blinkit")
    print("3. Zepto")
    choice = input("Enter choice (1-3): ")
    
    if choice == "1":
        asyncio.run(debug_page(INSTAMART_URL, "Instamart"))
    elif choice == "2":
        asyncio.run(debug_page(BLINKIT_URL, "Blinkit"))
    elif choice == "3":
        asyncio.run(debug_page(ZEPTO_URL, "Zepto"))
    else:
        print("Invalid choice")
