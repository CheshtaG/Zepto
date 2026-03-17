# How to Install Tesseract OCR

## Current Status

✅ Browser is working (Firefox)
✅ Screenshots are being saved successfully
⚠️ Tesseract OCR needs to be installed for text extraction

## Installation Methods

### Option 1: Using Homebrew (Recommended for macOS)

If you have Homebrew installed:
```bash
brew install tesseract
```

### Option 2: Manual Installation (macOS)

1. Download Tesseract from: https://github.com/tesseract-ocr/tesseract/releases
2. Or use MacPorts: `sudo port install tesseract`
3. Or use Conda: `conda install -c conda-forge tesseract`

### Option 3: Using MacPorts

If you have MacPorts:
```bash
sudo port install tesseract
```

### Option 4: Download Pre-built Binary

1. Visit: https://github.com/tesseract-ocr/tesseract/wiki
2. Download the macOS installer
3. Install the .dmg file
4. Add to PATH if needed

## Verify Installation

After installation, verify it works:
```bash
tesseract --version
```

## Test OCR

Once installed, test the API:
```bash
curl "http://localhost:8000/compare?product=Milk"
```

The OCR will extract text from screenshots and parse prices automatically.

## Screenshot Location

Screenshots are saved in:
```
/Users/cheshtagupta17/Data - Cheshta/Projects/Shopping Made Easy/data/instamart/
```

You can manually check the screenshots to see what the OCR will process.
