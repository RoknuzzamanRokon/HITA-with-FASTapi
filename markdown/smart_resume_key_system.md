# Smart Resume Key System for Hotel Pagination

## Overview

The `/v1.0/content/get_all_hotel_info` endpoint now uses **smart resume key logic** that automatically detects first vs subsequent requests:

- **First Request**: No resume_key needed (automatically detected)
- **Subsequent Requests**: Must provide valid resume_key from previous response
- **Database Count**: Shows actual total using `SELECT COUNT(ittid) FROM hotels`

## 🧠 Smart Detection Logic

### Automatic Request Type Detection

```python
# Smart detection - no manual flags needed
is_first_request = not resume_key  # If no resume_key provided, treat as first request

if resume_key:
    is_first_request = False
    print("📄 Subsequent request detected with resume_key")
else:
    is_first_request = True
    print("📄 First request detected (no resume_key provided)")
```

### Request Flow

1. **First Request**: `GET /v1.0/content/get_all_hotel_info?limit=50`
2. **Subsequent Requests**: `GET /v1.0/content/get_all_hotel_info?resume_key=12345_abc...&limit=50`

## 📊 Enhanced Response Format

### Complete Response Structure

```json
{
  "resume_key": "12346_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890AbCdEfGhIjKl",
  "page": 1,
  "limit": 50,
  "total_hotel": 15000,
  "accessible_hotel_count": 15000,
  "hotels": [...],
  "pagination_info": {
    "current_page_count": 50,
    "has_next_page": true,
    "user_role": "super_user",
    "point_deduction_applied": false,
    "is_first_request": true,
    "resume_key_required_for_next": true
  },
  "usage_instructions": {
    "first_request": "No resume_key needed for the first request",
    "subsequent_requests": "Must provide valid resume_key from previous response for next pages",
    "resume_key_format": "{hotel_id}_{50_character_random_string}",
    "note": "resume_key is automatically required for subsequent requests"
  }
}
```

### Key Response Fields

- **`total_hotel`**: Actual database count using `SELECT COUNT(ittid) FROM hotels`
- **`accessible_hotel_count`**: Hotels the current user can access
- **`is_first_request`**: Boolean indicating if this was detected as first request
- **`resume_key_required_for_next`**: Boolean indicating if next request needs resume_key

## 🔍 Database Count Implementation

### Actual Count Query

```python
# 📊 Get ACTUAL total hotel count using: SELECT COUNT(ittid) FROM hotels
total_hotel = db.query(func.count(Hotel.ittid)).scalar()
```

### User-Specific Accessible Count

```python
if allowed_providers is not None:
    # Count only hotels accessible to general user
    accessible_hotel_ids = db.query(ProviderMapping.ittid).filter(
        ProviderMapping.provider_name.in_(allowed_providers)
    ).distinct().all()
    accessible_hotel_count = db.query(Hotel).filter(Hotel.ittid.in_(accessible_hotel_ids)).count()
else:
    # Super/admin users can access all hotels
    accessible_hotel_count = total_hotel
```

## ✅ Valid Usage Patterns

### First Request (No Resume Key)

```bash
# Automatically detected as first request
GET /v1.0/content/get_all_hotel_info?limit=50

# Response includes resume_key for next request
{
  "resume_key": "12345_abc...",
  "pagination_info": {
    "is_first_request": true,
    "has_next_page": true
  }
}
```

### Subsequent Requests (With Resume Key)

```bash
# Must provide resume_key from previous response
GET /v1.0/content/get_all_hotel_info?resume_key=12345_abc...&limit=50

# Response includes next resume_key or null if last page
{
  "resume_key": "12346_def...",
  "pagination_info": {
    "is_first_request": false,
    "has_next_page": true
  }
}
```

### Last Page Detection

```bash
# When no more pages available
{
  "resume_key": null,
  "pagination_info": {
    "has_next_page": false
  }
}
```

## ❌ Invalid Usage (Rejected with 400 Error)

### Invalid Resume Key Formats

```bash
GET /v1.0/content/get_all_hotel_info?resume_key=invalid_format
# ERROR: Invalid resume key format. Expected format: 'id_randomstring'

GET /v1.0/content/get_all_hotel_info?resume_key=123_short
# ERROR: Invalid random part length. Expected 50 characters, got 5

GET /v1.0/content/get_all_hotel_info?resume_key=999999_abc...
# ERROR: Resume key references non-existent hotel record (ID: 999999)
```

## 🔒 Security & Access Control

### User Role Behavior

| User Role    | Point Deduction | Database Count | Accessible Count        | Resume Key Access     |
| ------------ | --------------- | -------------- | ----------------------- | --------------------- |
| Super User   | ❌ **EXEMPT**   | Full count     | Same as total           | All valid resume keys |
| Admin User   | ❌ **EXEMPT**   | Full count     | Same as total           | All valid resume keys |
| General User | ✅ **APPLIES**  | Full count     | Filtered by permissions | Permitted hotels only |

### Permission Validation

- **General Users**: Resume keys validated against user's provider permissions
- **Super/Admin Users**: All valid resume keys accepted
- **Cross-User Protection**: Resume keys validate hotel accessibility per user

## 🧪 Testing

### Test Script

Use `test_smart_resume_key.py` to verify the smart logic:

```bash
cd backend
python test_smart_resume_key.py
```

### Test Scenarios

1. **Smart Detection**

   - ✅ First request without resume_key should work
   - ✅ Subsequent request with resume_key should work
   - ❌ Invalid resume_key should fail

2. **Database Count Accuracy**

   - ✅ `total_hotel` should show actual database count
   - ✅ `accessible_hotel_count` should reflect user permissions
   - ✅ Superuser counts should match (total = accessible)

3. **Complete Pagination Flow**
   - ✅ Start without resume_key
   - ✅ Continue with resume_keys from responses
   - ✅ Handle last page (null resume_key)

## 📋 API Client Implementation

### JavaScript Example

```javascript
async function getAllHotels() {
  let allHotels = [];
  let resumeKey = null;
  let isFirstRequest = true;

  do {
    // Build URL based on request type
    let url = "/v1.0/content/get_all_hotel_info?limit=50";
    if (!isFirstRequest && resumeKey) {
      url += `&resume_key=${resumeKey}`;
    }

    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    const data = await response.json();

    // Process hotels
    allHotels.push(...data.hotels);

    // Update for next iteration
    resumeKey = data.resume_key;
    isFirstRequest = false;

    console.log(
      `Page completed: ${data.pagination_info.current_page_count} hotels`
    );
    console.log(
      `Total in DB: ${data.total_hotel}, Accessible: ${data.accessible_hotel_count}`
    );
  } while (resumeKey); // Continue while resume_key is not null

  return allHotels;
}
```

### Python Example

```python
import requests

def get_all_hotels(token):
    all_hotels = []
    resume_key = None
    is_first_request = True

    while True:
        # Build parameters
        params = {'limit': 50}
        if not is_first_request and resume_key:
            params['resume_key'] = resume_key

        # Make request
        response = requests.get(
            'http://localhost:8000/v1.0/content/get_all_hotel_info',
            headers={'Authorization': f'Bearer {token}'},
            params=params
        )

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

        data = response.json()

        # Process hotels
        all_hotels.extend(data['hotels'])

        # Check for next page
        resume_key = data.get('resume_key')
        is_first_request = False

        print(f"Page completed: {len(data['hotels'])} hotels")
        print(f"Total in DB: {data['total_hotel']}, Accessible: {data['accessible_hotel_count']}")

        if not resume_key:
            break  # Last page reached

    return all_hotels
```

## 🔧 Migration from Previous Version

### Changes Required

1. **Remove `first_request` Parameter**: No longer needed
2. **Update First Request**: Remove `first_request=true` parameter
3. **Keep Resume Key Logic**: Continue using resume_keys for subsequent requests

### Before (Old)

```bash
# First request
GET /v1.0/content/get_all_hotel_info?first_request=true&limit=50

# Subsequent requests
GET /v1.0/content/get_all_hotel_info?resume_key=12345_abc...&limit=50
```

### After (New)

```bash
# First request (automatically detected)
GET /v1.0/content/get_all_hotel_info?limit=50

# Subsequent requests (same as before)
GET /v1.0/content/get_all_hotel_info?resume_key=12345_abc...&limit=50
```

## 🚨 Error Handling

### Common Error Responses

```json
{
  "detail": "Invalid resume_key: Invalid resume key format. Expected format: 'id_randomstring'. Please use a valid resume_key from a previous response or omit it to start from the beginning."
}
```

### Error Handling in Clients

```javascript
try {
  const response = await fetch(url);
  const data = await response.json();

  if (!response.ok) {
    if (response.status === 400 && data.detail.includes("Invalid resume_key")) {
      // Resume key is invalid, restart pagination
      console.log("Invalid resume key, restarting pagination");
      return getAllHotels(); // Restart from beginning
    }
    throw new Error(data.detail);
  }

  return data;
} catch (error) {
  console.error("Pagination error:", error);
  throw error;
}
```

## 📊 Performance Benefits

### Advantages

- **Simpler API**: No need to specify `first_request=true`
- **Automatic Detection**: Smart logic handles request type detection
- **Accurate Counts**: Real database counts for monitoring and analytics
- **Maintained Security**: All validation and access control preserved

### Database Efficiency

- **Single Count Query**: `SELECT COUNT(ittid) FROM hotels` for accurate totals
- **Efficient Pagination**: Cursor-based pagination remains optimal
- **Permission Filtering**: Efficient filtering for general users

## 🔍 Monitoring & Analytics

### Key Metrics

- **Total Hotels**: Actual database count for capacity planning
- **Accessible Hotels**: User-specific counts for access analysis
- **Pagination Patterns**: Track how users navigate through data
- **Performance**: Monitor response times and cache hit rates

### Logging Examples

```
📄 First request detected (no resume_key provided)
📄 Subsequent request detected with resume_key: 12345_abc...
📊 Returning 50 hotels out of 15000 accessible hotels (Total in DB: 15000)
📄 Generated resume_key for next page: 12346_[50-char-random]
🔓 Point deduction skipped for UserRole.SUPER_USER: admin@example.com
```

## Summary

The smart resume key system provides:

- ✅ **Automatic Detection**: No manual flags needed for first requests
- ✅ **Simplified API**: Cleaner interface for API consumers
- ✅ **Accurate Counts**: Real database totals using `SELECT COUNT(ittid) FROM hotels`
- ✅ **Maintained Security**: All validation and access control preserved
- ✅ **Point Exemption**: Super/admin users remain exempt from point deductions
- ✅ **Smart Logic**: Automatically handles first vs subsequent request detection

This system provides the best user experience while maintaining security, performance, and accurate data reporting.
