# Hotel Content Management Documentation

## Overview

The Hotel Content Management system provides comprehensive access to hotel data, provider mappings, and location information through the ITT Hotel API (HITA). It includes intelligent point-based access control, provider permission management, and advanced pagination with resume keys for efficient data retrieval.

## Architecture

### Core Components

- **Hotel Content Router**: `/v1.0/content` prefix
- **Provider Mapping System**: Multi-provider hotel mapping
- **Point-Based Access Control**: Usage-based billing for general users
- **Permission Management**: Provider-specific access control
- **Resume Key Pagination**: Efficient large dataset pagination
- **Country Data Integration**: Static JSON country data
- **Search and Autocomplete**: Hotel name search functionality

### Security Model

- **Super User**: Full access, no point deduction
- **Admin User**: Full access, no point deduction
- **General User**: Point-based access with provider permissions

## Hotel Data Endpoints

### Get Basic Country Information

#### Endpoint

```http
POST /v1.0/content/get_basic_country_info
Authorization: Bearer <token>
```

#### Request Body

```json
{
  "supplier": "hotelbeds",
  "country_iso": "US"
}
```

#### Response

```json
{
  "success": true,
  "supplier": "hotelbeds",
  "country_iso": "US",
  "total_hotel": 1250,
  "data": [
    {
      "hotel_id": "12345",
      "name": "Grand Hotel",
      "city": "New York",
      "country": "United States"
    }
  ]
}
```

### Get Hotel Data by Provider Name and ID

#### Endpoint

```http
POST /v1.0/content/get_hotel_data_provider_name_and_id
Authorization: Bearer <token>
```

#### Request Body

```json
{
  "provider_hotel_identity": [
    {
      "provider_id": "12345",
      "provider_name": "hotelbeds"
    }
  ]
}
```

#### Response

```json
[
  {
    "hotel": {
      "ittid": "10000001",
      "id": 1,
      "name": "Grand Hotel New York",
      "property_type": "Hotel",
      "longitude": "-74.005974",
      "latitude": "40.712776",
      "address_line1": "123 Broadway",
      "address_line2": "Suite 456",
      "postal_code": "10001",
      "rating": "5",
      "primary_photo": "https://example.com/photo.jpg",
      "map_status": "confirmed",
      "updated_at": "2024-12-17T15:30:00Z",
      "created_at": "2024-12-17T10:00:00Z"
    },
    "provider_mappings": [
      {
        "id": 1,
        "provider_id": "12345",
        "provider_name": "hotelbeds",
        "system_type": "GDS",
        "giata_code": "67890",
        "vervotech_id": "VT123"
      }
    ],
    "locations": [
      {
        "id": 1,
        "city_name": "New York",
        "city_code": "NYC",
        "master_city_name": "New York City",
        "state_name": "New York",
        "state_code": "NY",
        "country_name": "United States",
        "country_code": "US"
      }
    ],
    "contacts": [
      {
        "id": 1,
        "contact_type": "phone",
        "value": "+1-555-123-4567"
      }
    ]
  }
]
```

### Get Hotel Mapping Data

#### Endpoint

```http
POST /v1.0/content/get_hotel_mapping_data_using_provider_name_and_id
Authorization: Bearer <token>
```

#### Request Body

```json
{
  "provider_hotel_identity": [
    {
      "provider_id": "12345",
      "provider_name": "hotelbeds"
    }
  ]
}
```

#### Response

```json
[
  {
    "provider_mappings": [
      {
        "ittid": "10000001",
        "provider_mapping_id": 1,
        "provider_id": "12345",
        "provider_name": "hotelbeds",
        "system_type": "GDS",
        "created_at": "2024-12-17T10:00:00Z"
      }
    ]
  }
]
```

### Get Hotels by ITTID List

#### Endpoint

```http
POST /v1.0/content/get_hotel_with_ittid
Authorization: Bearer <token>
```

#### Request Body

```json
{
  "ittid": ["10000001", "10000002", "10000003"]
}
```

#### Response

```json
[
  {
    "ittid": "10000001",
    "provider_mappings": [
      {
        "id": 1,
        "provider_id": "12345",
        "provider_name": "hotelbeds",
        "system_type": "GDS",
        "vervotech_id": "VT123",
        "giata_code": "67890"
      }
    ]
  }
]
```

### Get Hotel by Single ITTID

#### Endpoint

```http
GET /v1.0/content/get_hotel_with_ittid/{ittid}
Authorization: Bearer <token>
```

#### Response

```json
{
  "hotel": {
    "ittid": "10000001",
    "id": 1,
    "name": "Grand Hotel New York",
    "property_type": "Hotel",
    "longitude": "-74.005974",
    "latitude": "40.712776",
    "address_line1": "123 Broadway",
    "address_line2": "Suite 456",
    "postal_code": "10001",
    "rating": "5",
    "primary_photo": "https://example.com/photo.jpg",
    "map_status": "confirmed",
    "updated_at": "2024-12-17T15:30:00Z",
    "created_at": "2024-12-17T10:00:00Z"
  },
  "provider_mappings": [
    {
      "id": 1,
      "provider_id": "12345",
      "provider_name": "hotelbeds",
      "system_type": "GDS",
      "giata_code": "67890",
      "vervotech_id": "VT123"
    }
  ],
  "locations": [
    {
      "id": 1,
      "city_name": "New York",
      "city_code": "NYC",
      "master_city_name": "New York City",
      "state_name": "New York",
      "state_code": "NY",
      "country_name": "United States",
      "country_code": "US"
    }
  ],
  "chains": [
    {
      "id": 1,
      "chain_name": "Grand Hotels International",
      "chain_code": "GHI"
    }
  ],
  "contacts": [
    {
      "id": 1,
      "contact_type": "phone",
      "value": "+1-555-123-4567"
    }
  ],
  "supplier_info": {
    "total_active_suppliers": 3,
    "accessible_suppliers": 2,
    "supplier_names": ["hotelbeds", "tbo"]
  }
}
```

## Pagination and Bulk Data Access

### Get All Hotel Information (Paginated)

#### Endpoint

```http
GET /v1.0/content/get_all_hotel_info
Authorization: Bearer <token>
```

#### Parameters

| Parameter       | Type    | Default | Description                |
| --------------- | ------- | ------- | -------------------------- |
| `page`          | int     | 1       | Page number (≥1)           |
| `limit`         | int     | 50      | Items per page (1-1000)    |
| `resume_key`    | string  | null    | Resume key for pagination  |
| `first_request` | boolean | false   | Set true for first request |

#### First Request

```http
GET /v1.0/content/get_all_hotel_info?page=1&limit=50&first_request=true
Authorization: Bearer <token>
```

#### Subsequent Requests

```http
GET /v1.0/content/get_all_hotel_info?page=2&limit=50&resume_key=123_abcdef...
Authorization: Bearer <token>
```

#### Response

```json
{
  "resume_key": "456_ghijkl1234567890abcdef1234567890abcdef1234567890",
  "page": 1,
  "limit": 50,
  "total_hotel": 15420,
  "accessible_hotel_count": 12350,
  "hotels": [
    {
      "ittid": "10000001",
      "name": "Grand Hotel New York",
      "property_type": "Hotel",
      "rating": "5",
      "address_line1": "123 Broadway",
      "address_line2": "Suite 456",
      "postal_code": "10001",
      "map_status": "confirmed",
      "geocode": {
        "latitude": "40.712776",
        "longitude": "-74.005974"
      },
      "updated_at": "2024-12-17T15:30:00Z",
      "created_at": "2024-12-17T10:00:00Z"
    }
  ],
  "pagination_info": {
    "current_page_count": 50,
    "has_next_page": true,
    "user_role": "general_user",
    "point_deduction_applied": true,
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

### Get Hotels by Supplier

#### Endpoint

```http
GET /v1.0/content/get_all_hotel_only_supplier/
Authorization: Bearer <token>
```

#### Parameters

| Parameter        | Type   | Default  | Description               |
| ---------------- | ------ | -------- | ------------------------- |
| `provider_name`  | string | required | Provider name filter      |
| `limit_per_page` | int    | 50       | Items per page (1-500)    |
| `resume_key`     | string | null     | Resume key for pagination |

#### Response

```json
{
  "resume_key": "789_mnopqr1234567890abcdef1234567890abcdef1234567890",
  "limit_per_page": 50,
  "total_hotel": 5420,
  "hotels": [
    {
      "ittid": "10000001",
      "name": "Grand Hotel New York",
      "property_type": "Hotel",
      "rating": "5",
      "address_line1": "123 Broadway",
      "geocode": {
        "latitude": "40.712776",
        "longitude": "-74.005974"
      },
      "updated_at": "2024-12-17T15:30:00Z"
    }
  ],
  "pagination_info": {
    "current_page_count": 50,
    "has_next_page": true,
    "provider_filter": "hotelbeds"
  }
}
```

### Get Updated Provider Information

#### Endpoint

```http
GET /v1.0/content/get_update_provider_info
Authorization: Bearer <token>
```

#### Parameters

| Parameter        | Type   | Description               |
| ---------------- | ------ | ------------------------- |
| `from_date`      | string | Start date (YYYY-MM-DD)   |
| `to_date`        | string | End date (YYYY-MM-DD)     |
| `limit_per_page` | int    | Items per page            |
| `resume_key`     | string | Resume key for pagination |

#### Response

```json
{
  "resume_key": "101112_stuvwx1234567890abcdef1234567890abcdef123456",
  "from_date": "2024-12-01",
  "to_date": "2024-12-17",
  "limit_per_page": 50,
  "total_updates": 234,
  "updates": [
    {
      "ittid": "10000001",
      "provider_name": "hotelbeds",
      "provider_id": "12345",
      "update_type": "content_update",
      "updated_at": "2024-12-17T15:30:00Z"
    }
  ]
}
```

## Search and Discovery

### Search Hotel by Name

#### Endpoint

```http
POST /v1.0/content/search_with_hotel_name
Authorization: Bearer <token>
```

#### Request Body

```json
{
  "hotel_name": "Grand Hotel New York"
}
```

#### Response

```json
{
  "ittid": "10000001",
  "name": "Grand Hotel New York",
  "addressline1": "123 Broadway",
  "addressline2": "Suite 456",
  "city": "New York",
  "country": "United States",
  "latitude": "40.712776",
  "longitude": "-74.005974",
  "postalcode": "10001",
  "chainname": "Grand Hotels International",
  "propertytype": "Hotel"
}
```

### Hotel Name Autocomplete

#### Endpoint

```http
GET /v1.0/content/autocomplete?query=Grand
Authorization: Bearer <token>
```

#### Response

```json
{
  "results": [
    "Grand Hotel New York",
    "Grand Plaza Hotel",
    "Grand Central Hotel",
    "Grand Hyatt",
    "Grand Marriott"
  ]
}
```

## Point-Based Access Control

### Point Deduction Rules

- **General Users**: Points deducted for successful requests
- **Admin/Super Users**: No point deduction
- **Failed Requests**: No point deduction

### Point Deduction Triggers

- Successful hotel data retrieval
- Provider mapping access
- Bulk data requests
- Search operations (for general users)

### Permission Validation

```python
# General users must have provider permissions
if current_user.role == UserRole.GENERAL_USER:
    allowed_providers = [
        p.provider_name
        for p in db.query(UserProviderPermission)
                  .filter(UserProviderPermission.user_id == current_user.id)
                  .all()
    ]
    if not allowed_providers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have any permission for this request."
        )
```

## Resume Key Pagination System

### Resume Key Format

```
{hotel_id}_{50_character_random_string}
```

### Validation Rules

1. **Format Validation**: Must contain exactly one underscore separator
2. **ID Validation**: First part must be valid integer hotel ID
3. **Random String**: Must be exactly 50 alphanumeric characters
4. **Database Validation**: Hotel ID must exist in database
5. **Permission Validation**: User must have access to referenced hotel

### Usage Pattern

```python
# First request - no resume_key needed
GET /v1.0/content/get_all_hotel_info?page=1&limit=50

# Subsequent requests - resume_key required
GET /v1.0/content/get_all_hotel_info?page=2&limit=50&resume_key=123_abc...

# Resume key generation
last_hotel_id = hotels[-1].id
rand_str = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))
next_resume_key = f"{last_hotel_id}_{rand_str}"
```

## Data Models

### Hotel Model

```python
class Hotel:
    ittid: str              # ITT unique identifier
    id: int                 # Database primary key
    name: str               # Hotel name
    property_type: str      # Hotel, Resort, Apartment, etc.
    longitude: str          # Geographic longitude
    latitude: str           # Geographic latitude
    address_line1: str      # Primary address
    address_line2: str      # Secondary address
    postal_code: str        # Postal/ZIP code
    rating: str             # Hotel rating
    primary_photo: str      # Main photo URL
    map_status: str         # Mapping status
    created_at: datetime    # Creation timestamp
    updated_at: datetime    # Last update timestamp
```

### Provider Mapping Model

```python
class ProviderMapping:
    id: int                 # Mapping ID
    ittid: str              # ITT hotel identifier
    provider_id: str        # Provider's hotel ID
    provider_name: str      # Provider name (hotelbeds, tbo, etc.)
    system_type: str        # GDS, Direct, API, etc.
    giata_code: str         # GIATA identifier
    vervotech_id: str       # Vervotech identifier
    created_at: datetime    # Creation timestamp
    updated_at: datetime    # Last update timestamp
```

### Location Model

```python
class Location:
    id: int                 # Location ID
    ittid: str              # ITT hotel identifier
    city_name: str          # City name
    city_code: str          # City code
    master_city_name: str   # Master city name
    state_name: str         # State/province name
    state_code: str         # State/province code
    country_name: str       # Country name
    country_code: str       # ISO country code
```

## Error Handling

### Common Error Scenarios

#### Hotel Not Found

```json
{
  "detail": "Hotel with id '10000001' not found."
}
```

#### No Provider Permissions

```json
{
  "detail": "You do not have any permission for this request."
}
```

#### Invalid Resume Key

```json
{
  "detail": "Invalid resume_key: Resume key must start with a valid hotel ID. Please use a valid resume_key from a previous response or omit it to start from the beginning."
}
```

#### No Active Suppliers

```json
{
  "detail": "Cannot active supplier with this ittid '10000001'. No supplier mappings found for this hotel."
}
```

#### Country Data Not Found

```json
{
  "detail": "Country data not found for supplier 'hotelbeds' and country 'XX'"
}
```

### Error Response Format

```json
{
  "detail": "Error message describing the issue"
}
```

## Security Features

### Authentication

- All endpoints require valid JWT tokens
- Role-based access control implementation
- Provider permission validation

### Authorization

- **Super Users**: Full access to all data
- **Admin Users**: Full access, no point deduction
- **General Users**: Provider-restricted access with point deduction

### Data Protection

- Sensitive data filtering based on user permissions
- Provider-specific data access control
- Point-based usage tracking

## Performance Optimization

### Caching Strategy

- Static country data caching
- Provider mapping caching
- Search result caching (10 minutes TTL)

### Database Optimization

- Efficient joins for related data
- Indexed queries for fast lookups
- Pagination with resume keys for large datasets

### Memory Management

- Streaming responses for large datasets
- Efficient datetime serialization
- Optimized query patterns

## Best Practices

### API Usage

1. **Use Resume Keys**: For large dataset pagination
2. **Validate Permissions**: Check provider access before requests
3. **Handle Errors Gracefully**: Implement proper error handling
4. **Monitor Point Usage**: Track point consumption for general users
5. **Cache Results**: Cache frequently accessed data

### Development Guidelines

1. **Consistent Error Handling**: Use standard HTTP status codes
2. **Proper Validation**: Validate all input parameters
3. **Security First**: Always check permissions before data access
4. **Performance Monitoring**: Track query performance and optimization
5. **Documentation**: Keep API documentation updated

### Operational Guidelines

1. **Monitor Usage**: Track API usage patterns and performance
2. **Capacity Planning**: Plan for data growth and scaling
3. **Regular Maintenance**: Update provider mappings and country data
4. **Backup Strategy**: Ensure data backup and recovery procedures
5. **Security Auditing**: Regular security reviews and updates

## Integration Examples

### Basic Hotel Search

```python
# Search for hotel by name
response = requests.post(
    f"{base_url}/v1.0/content/search_with_hotel_name",
    headers={"Authorization": f"Bearer {token}"},
    json={"hotel_name": "Grand Hotel"}
)
```

### Paginated Data Retrieval

```python
# First request
response = requests.get(
    f"{base_url}/v1.0/content/get_all_hotel_info?page=1&limit=50",
    headers={"Authorization": f"Bearer {token}"}
)

# Subsequent requests with resume key
resume_key = response.json()["resume_key"]
next_response = requests.get(
    f"{base_url}/v1.0/content/get_all_hotel_info?page=2&limit=50&resume_key={resume_key}",
    headers={"Authorization": f"Bearer {token}"}
)
```

### Provider-Specific Data Access

```python
# Get hotel data by provider
response = requests.post(
    f"{base_url}/v1.0/content/get_hotel_data_provider_name_and_id",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "provider_hotel_identity": [
            {
                "provider_id": "12345",
                "provider_name": "hotelbeds"
            }
        ]
    }
)
```
