# Location API Documentation

## Overview

The Location API provides endpoints to retrieve and search location data from the hotel database. It supports various query types including cities, countries, country codes, and combined city-country information.

## Base URL

```
/v1.0/locations
```

## Endpoints

### 1. Get All Unique Cities

**GET** `/cities`

Returns all unique city names from the locations table.

**Response:**

```json
[
  {
    "city_name": "New York"
  },
  {
    "city_name": "London"
  }
]
```

### 2. Get All Unique Countries

**GET** `/countries`

Returns all unique country names from the locations table.

**Response:**

```json
[
  {
    "country_name": "United States"
  },
  {
    "country_name": "United Kingdom"
  }
]
```

### 3. Get All Unique Country Codes

**GET** `/country-codes`

Returns all unique country codes from the locations table.

**Response:**

```json
[
  {
    "country_code": "US"
  },
  {
    "country_code": "GB"
  }
]
```

### 4. Get Cities with Countries

**GET** `/cities-with-countries`

Returns all unique city-country combinations.

**Response:**

```json
[
  {
    "city_name": "New York",
    "country_name": "United States"
  },
  {
    "city_name": "London",
    "country_name": "United Kingdom"
  }
]
```

### 5. Search Locations

**GET** `/search`

Advanced search with multiple filter options and pagination.

**Query Parameters:**

- `city` (optional): Filter by city name (case-insensitive, partial match)
- `country` (optional): Filter by country name (case-insensitive, partial match)
- `country_code` (optional): Filter by country code (case-insensitive, partial match)
- `state` (optional): Filter by state name (case-insensitive, partial match)
- `limit` (optional): Number of results to return (1-1000, default: 100)
- `offset` (optional): Number of results to skip (default: 0)

**Example Requests:**

```
GET /search?city=New York
GET /search?country=United States
GET /search?country_code=US
GET /search?city=New&country=United States&limit=50&offset=0
```

**Response:**

```json
{
  "total": 150,
  "limit": 100,
  "offset": 0,
  "locations": [
    {
      "id": 1,
      "ittid": "HTL001",
      "city_name": "New York",
      "state_name": "New York",
      "state_code": "NY",
      "country_name": "United States",
      "country_code": "US",
      "master_city_name": "New York City",
      "city_code": "NYC",
      "city_location_id": "LOC001"
    }
  ]
}
```

### 6. Get Location by ID

**GET** `/{location_id}`

Returns a specific location by its ID.

**Path Parameters:**

- `location_id`: Integer ID of the location

**Response:**

```json
{
  "id": 1,
  "ittid": "HTL001",
  "city_name": "New York",
  "state_name": "New York",
  "state_code": "NY",
  "country_name": "United States",
  "country_code": "US",
  "master_city_name": "New York City",
  "city_code": "NYC",
  "city_location_id": "LOC001"
}
```

## Data Models

### LocationDetailResponse

```python
{
  "id": int,
  "ittid": str,
  "city_name": str | null,
  "state_name": str | null,
  "state_code": str | null,
  "country_name": str | null,
  "country_code": str | null,
  "master_city_name": str | null,
  "city_code": str | null,
  "city_location_id": str | null
}
```

### CityResponse

```python
{
  "city_name": str
}
```

### CountryResponse

```python
{
  "country_name": str
}
```

### CountryCodeResponse

```python
{
  "country_code": str
}
```

### CityWithCountryResponse

```python
{
  "city_name": str,
  "country_name": str
}
```

## Error Responses

### 404 Not Found

```json
{
  "detail": "Location not found"
}
```

### 500 Internal Server Error

```json
{
  "detail": "Error fetching locations: [error message]"
}
```

## Usage Examples

### Get all cities

```bash
curl -X GET "http://localhost:8000/v1.0/locations/cities"
```

### Get all countries

```bash
curl -X GET "http://localhost:8000/v1.0/locations/countries"
```

### Get all country codes

```bash
curl -X GET "http://localhost:8000/v1.0/locations/country-codes"
```

### Search for locations in a specific city

```bash
curl -X GET "http://localhost:8000/v1.0/locations/search?city=New%20York"
```

### Search for locations in a specific country

```bash
curl -X GET "http://localhost:8000/v1.0/locations/search?country=United%20States"
```

### Search with pagination

```bash
curl -X GET "http://localhost:8000/v1.0/locations/search?limit=10&offset=20"
```

### Get specific location by ID

```bash
curl -X GET "http://localhost:8000/v1.0/locations/1"
```

## Testing

Run the test suite with:

```bash
python -m pytest test_locations.py -v
```

The test file includes comprehensive tests for:

- All endpoint functionality
- Data validation
- Error handling
- Pagination
- Case-insensitive search
- Partial matching

## Features

- **Unique Results**: All list endpoints return unique values only
- **Case-Insensitive Search**: Search queries are case-insensitive
- **Partial Matching**: Search supports partial string matching
- **Pagination**: Search endpoint supports limit/offset pagination
- **Comprehensive Filtering**: Multiple filter options can be combined
- **Error Handling**: Proper HTTP status codes and error messages
- **Data Validation**: Input validation using Pydantic models

## Integration

To integrate this router into your FastAPI application, add it to your main.py:

```python
from routes.locations import router as locations_router

app.include_router(locations_router)
```

Make sure the Location model and database connection are properly configured before using these endpoints.
