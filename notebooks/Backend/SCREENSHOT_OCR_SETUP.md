# Screenshot + OCR Setup Guide

## What's Been Implemented

I've added screenshot + OCR functionality to extract prices from product listings:

1. **Screenshot Method**: Takes screenshots of product listing areas
2. **OCR Text Extraction**: Uses Tesseract OCR to extract text from screenshots
3. **Price Parsing**: Parses prices from OCR text using pattern matching

## Current Status

✅ Screenshot functionality added to `base_scraper.py`
✅ OCR text extraction method implemented
✅ Price extraction from OCR text implemented
✅ Modified `instamart_scraper.py` to use screenshot method

## Installation Required

### 1. Install Tesseract OCR

**macOS:**
```bash
brew install tesseract
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install tesseract-ocr
```

**Windows:**
Download from: https://github.com/UB-Mannheim/tesseract/wiki

### 2. Python Dependencies

Already installed:
- `pytesseract==0.3.13`
- `Pillow==10.1.0`

## ✅ Browser Launch Fixed!

The browser launch issue has been resolved by switching from Chromium to Firefox. Screenshots are now being saved successfully!

## How Screenshot Method Works

1. Navigate to the product search page
2. Take a screenshot of the product listing area
3. Use OCR to extract all text from the screenshot
4. Parse the OCR text to find prices (looking for ₹, Rs, numbers)
5. Return the extracted price

## Advantages of Screenshot Method

- ✅ Less interaction with DOM elements (might bypass some blocking)
- ✅ Works even if page structure changes
- ✅ Can capture visual content that's not in DOM
- ✅ Screenshots saved for debugging

## Disadvantages

- ❌ Requires Tesseract OCR installation
- ❌ OCR accuracy depends on image quality
- ❌ Slower than direct DOM extraction
- ❌ May miss prices if OCR doesn't recognize them

## ✅ Current Status

1. ✅ **Browser launch fixed** - Using Firefox instead of Chromium
2. ✅ **Screenshots working** - Screenshots are being saved successfully
3. ⚠️ **Tesseract OCR needed** - Install Tesseract to extract text from screenshots
4. ⏳ **Apply to all scrapers** - Currently only Instamart uses screenshot method

## Next Steps

1. **Install Tesseract OCR** - Required for OCR to work (see installation instructions above)
2. **Test OCR extraction** - Once Tesseract is installed, test price extraction from screenshots
3. **Apply to Blinkit and Zepto** - Add screenshot method to other scrapers

## Testing

Once browser launch is fixed and Tesseract is installed:

```bash
curl "http://localhost:8000/compare?product=Milk"
```

Check screenshots saved in:
```
/Users/cheshtagupta17/Data - Cheshta/Projects/Shopping Made Easy/data/instamart/
```
