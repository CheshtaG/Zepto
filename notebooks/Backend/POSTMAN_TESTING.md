# Postman Testing Guide

The FastAPI server is now running at: **http://localhost:8000**

## Available Endpoints

### 1. Health Check
**GET** `http://localhost:8000/health`

**Expected Response:**
```json
{
  "status": "healthy"
}
```

---

### 2. Get Default Products
**GET** `http://localhost:8000/products`

**Expected Response:**
```json
{
  "products": [
    "Milk",
    "Bread",
    "Eggs",
    "Rice",
    "Tomatoes",
    "Onions"
  ]
}
```

---

### 3. Compare Product (Main Endpoint)
**GET** `http://localhost:8000/compare?product=<product_name>`

**Examples:**
- `http://localhost:8000/compare?product=Milk`
- `http://localhost:8000/compare?product=Bread`
- `http://localhost:8000/compare?product=Eggs`

**Expected Response Format:**
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

**Note:** The first request for each product will take longer (30-60 seconds) as it scrapes all three platforms. Subsequent requests will be faster due to caching.

---

## Postman Setup Instructions

### Option 1: Manual Setup
1. Open Postman
2. Create a new GET request
3. Enter the URL: `http://localhost:8000/compare?product=Milk`
4. Click "Send"

### Option 2: Import Collection
You can create a Postman collection with these requests:

1. **Health Check**
   - Method: GET
   - URL: `http://localhost:8000/health`

2. **Get Products**
   - Method: GET
   - URL: `http://localhost:8000/products`

3. **Compare Product**
   - Method: GET
   - URL: `http://localhost:8000/compare?product={{product_name}}`
   - Variables: `product_name` (e.g., "Milk", "Bread", "Eggs")

---

## Testing Tips

1. **Start with Health Check**: Verify the server is running
2. **Test Default Products**: Check the list of available products
3. **Test Product Comparison**: 
   - Try: `Milk`, `Bread`, `Eggs`
   - First request will be slow (scraping)
   - Second request will be fast (cached)
4. **Test Error Handling**: Try a product that doesn't exist to see error messages

---

## Interactive API Documentation

You can also test the API using FastAPI's built-in documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

These provide an interactive interface to test all endpoints.

---

## Troubleshooting

- **Server not responding**: Check if the server is running in the background
- **Timeout errors**: The first scrape takes time (30-60 seconds). Be patient.
- **Product not found**: This is expected if the product doesn't exist on a platform
- **Connection refused**: Make sure the server is running on port 8000

---

## Cache Information

- Cache files are stored in: `/Users/cheshtagupta17/Data - Cheshta/Projects/Shopping Made Easy/data/cache/`
- Cache expires after 24 hours
- To clear cache, delete files from the cache directory
