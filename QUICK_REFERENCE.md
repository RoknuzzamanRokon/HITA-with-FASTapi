# Quick Reference: Export API Key Authentication

## What Changed?

All `/v1.0/export` endpoints now **require API key authentication** via the `X-API-Key` header.

## New Validation Endpoint

### Check if your API key is valid:

```bash
GET /v1.0/export/my-validation
Header: X-API-Key: your_api_key_here
```

**Success Response:**

```json
{
  "valid": true,
  "message": "API key is valid and active",
  "user": { ... },
  "access": {
    "export_endpoints": true,
    "message": "You have access to all /v1.0/export endpoints"
  }
}
```

## All Export Endpoints Now Require API Key

| Endpoint                         | Method | Purpose                 |
| -------------------------------- | ------ | ----------------------- |
| `/v1.0/export/my-validation`     | GET    | Validate API key        |
| `/v1.0/export/hotels`            | POST   | Export hotel data       |
| `/v1.0/export/mappings`          | POST   | Export mappings         |
| `/v1.0/export/supplier-summary`  | POST   | Export supplier summary |
| `/v1.0/export/status/{job_id}`   | GET    | Check export status     |
| `/v1.0/export/download/{job_id}` | GET    | Download export file    |
| `/v1.0/export/cancel/{job_id}`   | DELETE | Cancel export job       |

## How to Use

### Python Example:

```python
import requests

API_KEY = "ak_your_api_key_here"
headers = {"X-API-Key": API_KEY}

# Validate API key
response = requests.get(
    "http://localhost:8000/v1.0/export/my-validation",
    headers=headers
)

# Export hotels
response = requests.post(
    "http://localhost:8000/v1.0/export/hotels",
    headers={**headers, "Content-Type": "application/json"},
    json={"format": "csv", "filters": {"suppliers": ["agoda"]}}
)
```

### cURL Example:

```bash
# Validate API key
curl -X GET "http://localhost:8000/v1.0/export/my-validation" \
  -H "X-API-Key: ak_your_api_key_here"

# Export hotels
curl -X POST "http://localhost:8000/v1.0/export/hotels" \
  -H "X-API-Key: ak_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"format":"csv","filters":{"suppliers":["agoda"]}}'
```

### JavaScript/Fetch Example:

```javascript
const API_KEY = "ak_your_api_key_here";

// Validate API key
fetch("http://localhost:8000/v1.0/export/my-validation", {
  headers: { "X-API-Key": API_KEY },
})
  .then((res) => res.json())
  .then((data) => console.log(data));

// Export hotels
fetch("http://localhost:8000/v1.0/export/hotels", {
  method: "POST",
  headers: {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    format: "csv",
    filters: { suppliers: ["agoda"] },
  }),
})
  .then((res) => res.json())
  .then((data) => console.log(data));
```

## Error Responses

| Status | Error                    | Meaning                                |
| ------ | ------------------------ | -------------------------------------- |
| 401    | "API Key required"       | No X-API-Key header provided           |
| 401    | "Invalid API Key"        | API key doesn't exist or user inactive |
| 401    | "API Key has expired..." | API key expiration date has passed     |

## Getting an API Key

1. **Self-registered users:** Contact your administrator
2. **Admin users:** Use `POST /v1.0/auth/regenerate_api_key`
3. **Super users:** Can generate keys for others via `POST /v1.0/auth/generate_api_key/{user_id}`

## Testing

Run the test script:

```bash
# Edit test_export_api_key.py and set your API_KEY
python test_export_api_key.py
```

## Important Notes

- ⚠️ **Breaking Change:** JWT tokens no longer work for export endpoints
- ✓ API keys can have expiration dates
- ✓ All API key usage is logged for security
- ✓ Use the validation endpoint to check your API key before making requests
