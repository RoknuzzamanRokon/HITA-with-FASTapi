# Export API Key Authentication Changes

## Summary

All `/v1.0/export` endpoints now require a valid API key for authentication. JWT token authentication is no longer accepted for export endpoints.

## Changes Made

### 1. New Validation Endpoint

**Endpoint:** `GET /v1.0/export/my-validation`

This endpoint allows users to validate their API key before making export requests.

**Request:**

```bash
curl -X GET "http://localhost:8000/v1.0/export/my-validation" \
  -H "X-API-Key: your_api_key_here"
```

**Response (Success):**

```json
{
  "valid": true,
  "message": "API key is valid and active",
  "user": {
    "id": "abc123",
    "username": "john_doe",
    "email": "john@example.com",
    "role": "ADMIN_USER",
    "api_key_expires_at": "2025-12-31T23:59:59"
  },
  "access": {
    "export_endpoints": true,
    "message": "You have access to all /v1.0/export endpoints"
  }
}
```

**Response (Invalid API Key):**

```json
{
  "detail": "Invalid API Key"
}
```

### 2. Updated Export Endpoints

All export endpoints now require API key authentication:

- `POST /v1.0/export/hotels` - Export hotel data
- `POST /v1.0/export/mappings` - Export provider mappings
- `POST /v1.0/export/supplier-summary` - Export supplier summary
- `GET /v1.0/export/status/{job_id}` - Check export job status
- `GET /v1.0/export/download/{job_id}` - Download completed export
- `DELETE /v1.0/export/cancel/{job_id}` - Cancel export job

### 3. Authentication Requirements

**Before:**

- Endpoints accepted both JWT tokens (Bearer) and API keys

**After:**

- Endpoints **only** accept API keys via `X-API-Key` header
- JWT tokens are no longer valid for export endpoints

## How to Use

### Step 1: Validate Your API Key

```bash
curl -X GET "http://localhost:8000/v1.0/export/my-validation" \
  -H "X-API-Key: ak_your_api_key_here"
```

### Step 2: Use Export Endpoints

```bash
# Example: Export hotels
curl -X POST "http://localhost:8000/v1.0/export/hotels" \
  -H "X-API-Key: ak_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "csv",
    "filters": {
      "suppliers": ["agoda", "booking"]
    }
  }'
```

### Step 3: Check Status

```bash
curl -X GET "http://localhost:8000/v1.0/export/status/{job_id}" \
  -H "X-API-Key: ak_your_api_key_here"
```

### Step 4: Download Export

```bash
curl -X GET "http://localhost:8000/v1.0/export/download/{job_id}" \
  -H "X-API-Key: ak_your_api_key_here" \
  --output export.csv
```

## API Key Management

### Getting an API Key

- **Self-registered users:** Do NOT receive API keys automatically
- **Admin-created users:** Receive API keys automatically
- **Contact your administrator** to get an API key if you don't have one

### Generating/Regenerating API Keys

- Admin users can regenerate their own API key: `POST /v1.0/auth/regenerate_api_key`
- Super users can generate API keys for other users: `POST /v1.0/auth/generate_api_key/{user_id}`

### API Key Expiration

- API keys can have expiration dates
- Expired API keys will return: `"API Key has expired. Please contact your administrator for a new key."`
- Check expiration via the validation endpoint

## Error Responses

### 401 Unauthorized - Missing API Key

```json
{
  "detail": "API Key required"
}
```

### 401 Unauthorized - Invalid API Key

```json
{
  "detail": "Invalid API Key"
}
```

### 401 Unauthorized - Expired API Key

```json
{
  "detail": "API Key has expired. Please contact your administrator for a new key."
}
```

## Security Benefits

1. **Dedicated Authentication:** Export endpoints now have dedicated API key authentication
2. **Expiration Support:** API keys can expire, enhancing security
3. **Validation Endpoint:** Users can pre-validate their API keys
4. **Audit Trail:** All API key usage is logged for security monitoring
5. **Consistent Access Control:** All export endpoints use the same authentication method

## Migration Guide

If you were using JWT tokens for export endpoints:

1. **Obtain an API key** from your administrator
2. **Update your code** to use `X-API-Key` header instead of `Authorization: Bearer`
3. **Test the validation endpoint** to ensure your API key works
4. **Update your scripts/applications** to use the new authentication method

### Before (JWT Token):

```python
headers = {
    "Authorization": f"Bearer {jwt_token}",
    "Content-Type": "application/json"
}
```

### After (API Key):

```python
headers = {
    "X-API-Key": api_key,
    "Content-Type": "application/json"
}
```

## Technical Details

### Implementation

- All export endpoints now use `authenticate_api_key` dependency from `routes/auth.py`
- The `authenticate_api_key` function validates:
  - API key exists in `X-API-Key` header
  - API key matches a user in the database
  - User account is active
  - API key has not expired (if expiration is set)

### Files Modified

- `routes/export.py` - Updated all endpoint dependencies and added validation endpoint

### Backward Compatibility

- **Breaking Change:** JWT tokens no longer work for export endpoints
- All clients must update to use API keys
