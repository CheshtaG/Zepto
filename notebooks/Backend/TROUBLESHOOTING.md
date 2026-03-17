# Troubleshooting Browser Launch Issues

## Current Issue
The browser is launching but immediately closing. This is a known issue with Playwright on macOS.

## Solutions to Try

### 1. Reinstall Playwright Browsers
```bash
python3 -m playwright uninstall chromium
python3 -m playwright install chromium
```

### 2. Check macOS Security Settings
1. Go to System Preferences > Security & Privacy
2. Check if Chromium is blocked
3. If blocked, click "Allow Anyway"

### 3. Try Running Without Headless Mode (for testing)
We can modify the code to run in non-headless mode to see what's happening.

### 4. Alternative: Use Selenium Instead
If Playwright continues to fail, we can switch to Selenium which sometimes works better on macOS.

### 5. Check Playwright Version
```bash
python3 -m playwright --version
pip3 show playwright
```

### 6. Try Firefox Instead of Chromium
```bash
python3 -m playwright install firefox
```
Then we can modify the code to use Firefox instead.

## To See Server Logs

The server is running in the background. To see logs, you can:

1. **Stop the current server:**
   ```bash
   lsof -ti:8000 | xargs kill -9
   ```

2. **Run it in foreground to see logs:**
   ```bash
   cd "/Users/cheshtagupta17/Data - Cheshta/Projects/Shopping Made Easy/notebooks"
   python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Or check the test script output:**
   ```bash
   python3 test_scraper.py
   ```
