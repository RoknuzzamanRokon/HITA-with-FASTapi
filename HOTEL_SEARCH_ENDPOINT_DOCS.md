# Hotel Search by Location Endpoint

## Endpoint

`POST /v1.0/locations/search-hotel-with-location`

## Description

Searches for hotels within a specified radius from given coordinates. The endpoint reads hotel data from JSON files stored in `static/countryJson/{supplier}/{country_code}.json` and filters hotels based on geographic distance using the Haversine formula.

## Request Body

```json
{
  "lat": "25.2048493",
  "lon": "55.2707828",
  "radious": "10",
  "supplier": ["agoda"],
  "country_code": "AI"
}
```

### Parameters

| Field        | Type          | Required | Description                                   |
| ------------ | ------------- | -------- | --------------------------------------------- |
| lat          | string        | Yes      | Latitude of the search center point           |
| lon          | string        | Yes      | Longitude of the search center point          |
| radious      | string        | Yes      | Search radius in kilometers                   |
| supplier     | array[string] | Yes      | List of suppliers to search (e.g., ["agoda"]) |
| country_code | string        | Yes      | ISO country code (e.g., "AI" for Anguilla)    |

## Response Format

```json
{
  "total_hotels": 20,
  "hotels": [
    {
      "a": 18.17,
      "b": -63.1423,
      "name": "Sheriva Luxury Villas and Suites",
      "addr": "Maundays Bay Rd",
      "type": "Villa",
      "photo": "https://i.travelapi.com/lodging/2000000/1710000/1703300/1703222/ccab36d9_z.jpg",
      "star": 4.0,
      "vervotech": "15392205",
      "giata": "291678",
      "agoda": ["55395643"]
    }
  ]
}
```

### Response Fields

| Field              | Type          | Description                                    |
| ------------------ | ------------- | ---------------------------------------------- |
| total_hotels       | integer       | Total number of hotels found within the radius |
| hotels             | array         | Array of hotel objects                         |
| hotels[].a         | float         | Hotel latitude                                 |
| hotels[].b         | float         | Hotel longitude                                |
| hotels[].name      | string        | Hotel name                                     |
| hotels[].addr      | string        | Hotel address                                  |
| hotels[].type      | string        | Property type (e.g., Villa, Resort, Hotel)     |
| hotels[].photo     | string        | URL to hotel photo                             |
| hotels[].star      | float         | Star rating                                    |
| hotels[].vervotech | string        | Vervotech ID                                   |
| hotels[].giata     | string        | GIATA ID (optional)                            |
| hotels[].agoda     | array[string] | Agoda hotel IDs (when supplier is agoda)       |

## How It Works

1. **Input Validation**: Converts string coordinates and radius to float values
2. **File Lookup**: For each supplier, looks for the JSON file at `static/countryJson/{supplier}/{country_code}.json`
3. **Distance Calculation**: Uses the Haversine formula to calculate the distance between the search point and each hotel
4. **Filtering**: Only includes hotels within the specified radius
5. **Data Transformation**: Converts the source JSON format to the required output format:
   - `lat` → `a`
   - `lon` → `b`
   - `ptype` → `type`
   - Adds supplier-specific IDs dynamically

## Example Usage

### Using cURL

```bash
curl -X POST "http://localhost:8000/v1.0/locations/search-hotel-with-location" \
  -H "Content-Type: application/json" \
  -d '{
    "lat": "18.17",
    "lon": "-63.14",
    "radious": "10",
    "supplier": ["agoda"],
    "country_code": "AI"
  }'
```

### Using Python

```python
import requests

url = "http://localhost:8000/v1.0/locations/search-hotel-with-location"
data = {
    "lat": "18.17",
    "lon": "-63.14",
    "radious": "10",
    "supplier": ["agoda"],
    "country_code": "AI"
}

response = requests.post(url, json=data)
print(response.json())
```

## Error Responses

### 400 Bad Request

Invalid input parameters (e.g., non-numeric lat/lon/radius)

```json
{
  "detail": "Invalid input parameters: could not convert string to float: 'invalid'"
}
```

### 404 Not Found

Hotel data file not found for the specified country/supplier combination

```json
{
  "detail": "Hotel data not found for the specified country/supplier"
}
```

### 500 Internal Server Error

Unexpected error during processing

```json
{
  "detail": "Error searching hotels: [error message]"
}
```

## Notes

- The endpoint uses the Haversine formula for accurate distance calculation on a sphere
- Distance is calculated in kilometers
- Multiple suppliers can be searched simultaneously
- If a JSON file doesn't exist for a supplier/country combination, it's silently skipped
- Hotels without lat/lon coordinates are automatically excluded
