# Product Comparison Platform - Backend

A FastAPI-based backend that compares product prices and availability across Instamart, Blinkit, and Zepto platforms.

## Features

- Compare product prices across three platforms (Instamart, Blinkit, Zepto)
- Automatic location selection (Pune)
- Caching mechanism for faster responses
- RESTful API endpoints

## Setup

### Prerequisites

- Python 3.8 or higher
- pip

### Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install chromium
```

3. Create data directories (if they don't exist):
```bash
mkdir -p "/Users/cheshtagupta17/Data - Cheshta/Projects/Shopping Made Easy/data/cache"
mkdir -p "/Users/cheshtagupta17/Data - Cheshta/Projects/Shopping Made Easy/data/instamart"
mkdir -p "/Users/cheshtagupta17/Data - Cheshta/Projects/Shopping Made Easy/data/blinkit"
mkdir -p "/Users/cheshtagupta17/Data - Cheshta/Projects/Shopping Made Easy/data/zepto"
```

## Running the Server

Start the FastAPI server:

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Compare Product
```
GET /compare?product=<product_name>
```

Compares a product across all three platforms and returns price and availability information.

**Example:**
```bash
curl "http://localhost:8000/compare?product=Milk"
```

**Response:**
```json
{
  "product_name": "Milk",
  "platforms": [
    {
      "platform": "instamart",
      "price": 60.0,
      "availability": true,
      "error": null,
      "product_url": "https://...",
      "image_url": null
    },
    {
      "platform": "blinkit",
      "price": 58.0,
      "availability": true,
      "error": null,
      "product_url": "https://...",
      "image_url": null
    },
    {
      "platform": "zepto",
      "price": null,
      "availability": false,
      "error": "Product not found",
      "product_url": null,
      "image_url": null
    }
  ]
}
```

### Get Default Products
```
GET /products
```

Returns the list of default products available for comparison.

### Health Check
```
GET /health
```

Returns the health status of the API.

## API Documentation

Once the server is running, you can access:
- Interactive API docs: `http://localhost:8000/docs`
- Alternative docs: `http://localhost:8000/redoc`

## Default Products

The following products are available by default:
- Milk
- Bread
- Eggs
- Rice
- Tomatoes
- Onions

## Caching

The API uses a file-based caching system. Cached data expires after 24 hours. Cache files are stored in:
```
/Users/cheshtagupta17/Data - Cheshta/Projects/Shopping Made Easy/data/cache/
```

## Notes

- The scrapers use Playwright to navigate and extract data from the platforms
- Location is automatically set to Pune (pincode: 411001)
- If a product is not found on a platform, it will be marked as unavailable with an error message
- The scrapers handle errors gracefully and return appropriate error messages
