# ML Mapping API Documentation

## Overview

The ML Mapping API provides intelligent hotel matching capabilities using advanced fuzzy matching algorithms. It connects supplier hotel data with internal hotel databases to find the best matches based on hotel names, locations, and other attributes.

## Base URL

```
/v1.0/ml_mapping
```

## Endpoints

### 1. Find Match Data

**POST** `/find_match_data`

Finds a matching hotel in the internal database for a given supplier hotel.

**Request Body:**

```json
{
  "supplier_name": "agoda",
  "hotel_id": "297844"
}
```

**Response:**

```json
[
  {
    "find_hotel": {
      "Id": 693171,
      "ittid": 10693171,
      "supplier_name": "agoda",
      "hotel_id": "297844",
      "api_data": {
        "name": "Express Inn The Business Luxury Hotel",
        "city": "Nashik",
        "country": "India"
      },
      "matched_data": {
        "name": "Express Inn The Business Luxury Hotel",
        "city": "NASHIK",
        "country": "India"
      },
      "matching_info": {
        "confidence_score": 1.0,
        "threshold_used": 0.6,
        "total_candidates": 72531
      }
    }
  }
]
```

### 2. Batch Find Match Data

**POST** `/batch_find_match_data`

Processes multiple hotels in a single request for better efficiency.

**Request Body:**

```json
{
  "supplier_name": "agoda",
  "hotel_ids": ["297844", "64845042"]
}
```

**Response:**

```json
{
  "successful_mappings": [...],
  "failed_mappings": [...],
  "summary": {
    "total_hotels": 2,
    "successful": 1,
    "failed": 1
  }
}
```

### 3. Health Check

**GET** `/health`

Returns the health status of the ML mapping service.

**Response:**

```json
{
  "status": "healthy",
  "service": "ML Hotel Mapping",
  "hotel_mapper_available": true,
  "version": "1.0"
}
```

### 4. Supported Suppliers

**GET** `/supported_suppliers`

Returns a list of supported hotel suppliers.

**Response:**

```json
{
  "supported_suppliers": [
    {
      "name": "agoda",
      "description": "Agoda hotel supplier",
      "status": "active"
    }
  ],
  "total_count": 1
}
```

## Features

### Advanced Matching Algorithm

- **Multi-factor scoring**: Combines hotel name, city, and country similarity
- **Fuzzy matching**: Uses multiple algorithms including substring and word-level matching
- **Dynamic weighting**: Adjusts scoring based on available data quality
- **Performance optimization**: Pre-filters by country when possible
- **Adaptive thresholds**: Different confidence levels based on data completeness

### Error Handling

- Comprehensive exception handling with detailed error messages
- Graceful degradation when external APIs are unavailable
- Timeout protection for external API calls
- Input validation and sanitization

### Performance Features

- **Batch processing**: Handle multiple hotels efficiently
- **Caching**: Results can be cached for improved performance
- **Logging**: Detailed logging for debugging and monitoring
- **Metrics**: Confidence scores and matching statistics

## Response Fields

### find_hotel Object

- **Id**: Internal hotel ID
- **ittid**: Internal hotel tracking ID
- **supplier_name**: Source supplier name
- **hotel_id**: Original supplier hotel ID

### api_data Object

- **name**: Hotel name from supplier API
- **city**: City from supplier API
- **country**: Country from supplier API

### matched_data Object

- **name**: Matched hotel name from internal database
- **city**: Matched city from internal database
- **country**: Matched country from internal database

### matching_info Object

- **confidence_score**: Matching confidence (0.0 to 1.0)
- **threshold_used**: Minimum threshold applied
- **total_candidates**: Number of hotels considered

## Error Codes

- **200**: Success
- **404**: No matching hotel found
- **422**: Invalid request data
- **500**: Internal server error

## Usage Examples

### Python

```python
import requests

# Single hotel
response = requests.post(
    "http://localhost:8000/v1.0/ml_mapping/find_match_data",
    json={"supplier_name": "agoda", "hotel_id": "297844"}
)

# Batch processing
response = requests.post(
    "http://localhost:8000/v1.0/ml_mapping/batch_find_match_data",
    json={
        "supplier_name": "agoda",
        "hotel_ids": ["297844", "64845042"]
    }
)
```

### JavaScript

```javascript
// Single hotel
const response = await fetch("/v1.0/ml_mapping/find_match_data", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    supplier_name: "agoda",
    hotel_id: "297844",
  }),
});

const result = await response.json();
```

## Configuration

The API uses the following configuration:

- **CSV Data Source**: `backend/static/hotelcontent/itt_hotel_basic_info.csv`
- **External API**: `https://mappingapi.innsightmap.com`
- **Timeout**: 30 seconds for external API calls
- **Default Threshold**: 0.6 (with location data) or 0.7 (name only)

## Dependencies

- FastAPI
- Pandas
- Requests
- Pydantic
- Python 3.7+

## Installation

1. Ensure all dependencies are installed
2. Place the CSV data file in the correct location
3. Import the router in your main FastAPI application
4. The API will be available at `/v1.0/ml_mapping/`
