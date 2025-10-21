# ML Mapping API - cURL Examples

## 1. Health Check

```bash
curl -X GET "http://localhost:8000/v1.0/ml_mapping/health" \
  -H "Content-Type: application/json"
```

## 2. Get Supported Suppliers

```bash
curl -X GET "http://localhost:8000/v1.0/ml_mapping/supported_suppliers" \
  -H "Content-Type: application/json"
```

## 3. Find Match Data (Single Hotel)

```bash
curl -X POST "http://localhost:8000/v1.0/ml_mapping/find_match_data" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier_name": "agoda",
    "hotel_id": "297844"
  }'
```

## 4. Batch Find Match Data (Multiple Hotels)

```bash
curl -X POST "http://localhost:8000/v1.0/ml_mapping/batch_find_match_data" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier_name": "agoda",
    "hotel_ids": ["297844", "64845042"]
  }'
```

## Expected Response Format

### Single Hotel Response:

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

### Batch Response:

```json
{
  "successful_mappings": [
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
  ],
  "failed_mappings": [],
  "summary": {
    "total_hotels": 1,
    "successful": 1,
    "failed": 0
  }
}
```

## Error Responses

### 404 - Hotel Not Found:

```json
{
  "detail": "No matching hotel found for agoda:invalid_id"
}
```

### 500 - Internal Server Error:

```json
{
  "detail": "Internal server error: [error message]"
}
```

## Testing with Python requests:

```python
import requests

# Single hotel mapping
response = requests.post(
    "http://localhost:8000/v1.0/ml_mapping/find_match_data",
    json={"supplier_name": "agoda", "hotel_id": "297844"}
)
print(response.json())
```
