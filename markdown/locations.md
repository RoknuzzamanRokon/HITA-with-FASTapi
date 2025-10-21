# Locations Documentation

## Overview

The Locations system provides comprehensive geographic and location data management for the ITT Hotel API (HITA). It offers endpoints to retrieve, search, and filter location information including cities, countries, states, and detailed location data associated with hotels.

## Architecture

### Core Components

- **Locations Router**: `/v1.0/locations` prefix
- **Geographic Data Access**: Cities, countries, and location details
- **Search and Filtering**: Advanced location search capabilities
- **Public Access**: No authentication required for location data
- **Pagination Support**: Efficient handling of large datasets
- **Data Aggregation**: Unique city and country listings

### Route Prefix

```
/v1.0/locations
```

## Data Models

### Location Detail Response

```python
class LocationDetailResponse(BaseModel):
    id: int                           # Location database ID
    ittid: str                        # ITT hotel identifier
    city_name: Optional[str]          # City name
    state_name: Optional[str]         # State/province name
    state_code: Optional[str]         # State/province code
    country_name: Optional[str]       # Country name
    country_code: Optional[str]       # ISO country code
    master_city_name: Optional[str]   # Master city name
    city_code: Optional[str]          # City code
    city_location_id: Optional[str]   # City location identifier
```

### Response Models

```python
class CityResponse(BaseModel):
    city_name: str

class CountryResponse(BaseModel):
    country_name: str

class CountryCodeResponse(BaseModel):
    country_code: str

class CityWithCountryResponse(BaseModel):
    city_name: str
    country_name: str
```

## Location Endpoints

### Get All Cities

#### Endpoint

```http
GET /v1.0/locations/cities
```

#### Response

```json
[
  {
    "city_name": "New York"
  },
  {
    "city_name": "London"
  },
  {
    "city_name": "Paris"
  },
  {
    "city_name": "Tokyo"
  },
  {
    "city_name": "Barcelona"
  }
]
```

#### Features

- **Unique Cities**: Returns only distinct city names
- **Null Filtering**: Excludes null and empty city names
- **Alphabetical Order**: Cities returned in database order
- **No Authentication**: Public access endpoint

### Get All Countries

#### Endpoint

```http
GET /v1.0/locations/countries
```

#### Response

```json
[
  {
    "country_name": "United States"
  },
  {
    "country_name": "United Kingdom"
  },
  {
    "country_name": "France"
  },
  {
    "country_name": "Japan"
  },
  {
    "country_name": "Spain"
  }
]
```

#### Features

- **Unique Countries**: Returns only distinct country names
- **Data Validation**: Excludes null and empty values
- **Complete Coverage**: All countries with hotel locations
- **Public Access**: No authentication required

### Get All Country Codes

#### Endpoint

```http
GET /v1.0/locations/country-codes
```

#### Response

```json
[
  {
    "country_code": "US"
  },
  {
    "country_code": "GB"
  },
  {
    "country_code": "FR"
  },
  {
    "country_code": "JP"
  },
  {
    "country_code": "ES"
  }
]
```

#### Features

- **ISO Country Codes**: Standard two-letter country codes
- **Unique Values**: Distinct country codes only
- **Data Integrity**: Validated and cleaned codes
- **Integration Ready**: Perfect for dropdown lists and forms

### Get Cities with Countries

#### Endpoint

```http
GET /v1.0/locations/cities-with-countries
```

#### Response

```json
[
  {
    "city_name": "New York",
    "country_name": "United States"
  },
  {
    "city_name": "London",
    "country_name": "United Kingdom"
  },
  {
    "city_name": "Paris",
    "country_name": "France"
  },
  {
    "city_name": "Tokyo",
    "country_name": "Japan"
  },
  {
    "city_name": "Barcelona",
    "country_name": "Spain"
  }
]
```

#### Features

- **City-Country Pairs**: Complete city and country combinations
- **Unique Combinations**: Distinct city-country pairs only
- **Data Completeness**: Only includes records with both city and country
- **Geographic Context**: Provides full geographic context for cities

### Search Locations

#### Endpoint

```http
GET /v1.0/locations/search
```

#### Parameters

| Parameter      | Type   | Required | Description                            |
| -------------- | ------ | -------- | -------------------------------------- |
| `city`         | string | No       | Filter by city name (partial match)    |
| `country`      | string | No       | Filter by country name (partial match) |
| `country_code` | string | No       | Filter by country code (partial match) |
| `state`        | string | No       | Filter by state name (partial match)   |
| `limit`        | int    | No       | Maximum results (1-1000, default: 100) |
| `offset`       | int    | No       | Pagination offset (default: 0)         |

#### Request Examples

```http
# Search by city
GET /v1.0/locations/search?city=New York

# Search by country
GET /v1.0/locations/search?country=United States

# Search by country code
GET /v1.0/locations/search?country_code=US

# Combined search with pagination
GET /v1.0/locations/search?country=United States&state=California&limit=50&offset=0

# Partial matching
GET /v1.0/locations/search?city=San&limit=20
```

#### Response

```json
{
  "total": 156,
  "limit": 100,
  "offset": 0,
  "locations": [
    {
      "id": 1,
      "ittid": "10000001",
      "city_name": "New York",
      "state_name": "New York",
      "state_code": "NY",
      "country_name": "United States",
      "country_code": "US",
      "master_city_name": "New York City",
      "city_code": "NYC",
      "city_location_id": "NYC001"
    },
    {
      "id": 2,
      "ittid": "10000002",
      "city_name": "Los Angeles",
      "state_name": "California",
      "state_code": "CA",
      "country_name": "United States",
      "country_code": "US",
      "master_city_name": "Los Angeles Metropolitan Area",
      "city_code": "LAX",
      "city_location_id": "LAX001"
    }
  ]
}
```

#### Search Features

- **Partial Matching**: Case-insensitive partial string matching
- **Multiple Filters**: Combine multiple search criteria
- **Pagination**: Efficient handling of large result sets
- **Total Count**: Provides total matching records
- **Flexible Queries**: Mix and match different filter parameters

### Get Location by ID

#### Endpoint

```http
GET /v1.0/locations/{location_id}
```

#### Parameters

| Parameter     | Type | Location | Description          |
| ------------- | ---- | -------- | -------------------- |
| `location_id` | int  | path     | Location database ID |

#### Request Example

```http
GET /v1.0/locations/1
```

#### Response (Success)

```json
{
  "id": 1,
  "ittid": "10000001",
  "city_name": "New York",
  "state_name": "New York",
  "state_code": "NY",
  "country_name": "United States",
  "country_code": "US",
  "master_city_name": "New York City",
  "city_code": "NYC",
  "city_location_id": "NYC001"
}
```

#### Response (Not Found)

```json
{
  "detail": "Location not found"
}
```

## Search and Filtering

### Search Capabilities

- **Case-Insensitive**: All text searches are case-insensitive
- **Partial Matching**: Uses SQL ILIKE for partial string matching
- **Multiple Criteria**: Combine different search parameters
- **Null Handling**: Properly handles null and empty values
- **Performance Optimized**: Efficient database queries

### Filter Combinations

```http
# City and country
GET /v1.0/locations/search?city=Paris&country=France

# State and country code
GET /v1.0/locations/search?state=California&country_code=US

# Multiple partial matches
GET /v1.0/locations/search?city=San&state=Cal&country=United

# Pagination with filters
GET /v1.0/locations/search?country=United States&limit=25&offset=50
```

### Search Performance

- **Database Indexes**: Optimized with appropriate database indexes
- **Query Optimization**: Efficient SQL query construction
- **Result Limiting**: Built-in pagination to prevent large result sets
- **Memory Efficiency**: Streaming results for large datasets

## Data Structure and Relationships

### Location Data Fields

- **Primary Key**: `id` - Unique location identifier
- **Hotel Reference**: `ittid` - Links to hotel records
- **Geographic Hierarchy**: Country → State → City structure
- **Codes and Identifiers**: Various location codes for integration
- **Master Data**: Normalized city and location names

### Data Quality Features

- **Null Filtering**: Excludes null and empty values from results
- **Data Validation**: Ensures data integrity and consistency
- **Duplicate Handling**: Distinct queries prevent duplicate results
- **Standardization**: Consistent data formatting and structure

## Error Handling

### Common Error Scenarios

#### Location Not Found

```json
{
  "detail": "Location not found"
}
```

#### Database Error

```json
{
  "detail": "Error fetching locations: Database connection failed"
}
```

#### Invalid Parameters

```json
{
  "detail": "Limit must be between 1 and 1000"
}
```

### Error Response Format

```json
{
  "detail": "Error description"
}
```

## Performance Considerations

### Database Optimization

- **Indexed Queries**: Primary key and foreign key indexes
- **Efficient Filtering**: Optimized WHERE clauses
- **Distinct Operations**: Efficient unique value retrieval
- **Pagination**: Limit and offset for large datasets

### Query Performance

- **Selective Queries**: Only fetch required fields
- **Proper Indexing**: Database indexes on searchable fields
- **Connection Pooling**: Efficient database connection management
- **Result Caching**: Consider caching for frequently accessed data

## Integration Examples

### Get All Cities

```python
import requests

# Retrieve all cities
response = requests.get(f"{base_url}/v1.0/locations/cities")

if response.status_code == 200:
    cities = response.json()
    print(f"Found {len(cities)} cities:")
    for city in cities[:10]:  # Show first 10
        print(f"- {city['city_name']}")
```

### Search Locations

```python
# Search for locations in California
response = requests.get(
    f"{base_url}/v1.0/locations/search",
    params={
        "state": "California",
        "country_code": "US",
        "limit": 20
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"Found {data['total']} locations in California")
    for location in data['locations']:
        print(f"- {location['city_name']}, {location['state_name']}")
```

### Build Location Dropdown

```python
# Create city-country dropdown data
response = requests.get(f"{base_url}/v1.0/locations/cities-with-countries")

if response.status_code == 200:
    locations = response.json()

    # Create dropdown options
    dropdown_options = []
    for location in locations:
        option = {
            "value": f"{location['city_name']}, {location['country_name']}",
            "label": f"{location['city_name']}, {location['country_name']}"
        }
        dropdown_options.append(option)

    print(f"Created {len(dropdown_options)} dropdown options")
```

### Paginated Location Search

```python
# Paginated search through all US locations
def get_all_us_locations():
    all_locations = []
    offset = 0
    limit = 100

    while True:
        response = requests.get(
            f"{base_url}/v1.0/locations/search",
            params={
                "country_code": "US",
                "limit": limit,
                "offset": offset
            }
        )

        if response.status_code == 200:
            data = response.json()
            all_locations.extend(data['locations'])

            # Check if we've retrieved all records
            if len(data['locations']) < limit:
                break

            offset += limit
        else:
            break

    return all_locations

us_locations = get_all_us_locations()
print(f"Retrieved {len(us_locations)} US locations")
```

## Use Cases

### Frontend Applications

- **Location Dropdowns**: Populate city and country dropdowns
- **Search Autocomplete**: Implement location search autocomplete
- **Geographic Filtering**: Filter hotels by location
- **Map Integration**: Provide location data for mapping services

### Data Analysis

- **Geographic Distribution**: Analyze hotel distribution by location
- **Market Coverage**: Identify coverage gaps in specific regions
- **Location Trends**: Track popular destinations and cities
- **Regional Analysis**: Compare performance across different locations

### Integration Services

- **Third-Party APIs**: Provide location data to external services
- **Data Synchronization**: Sync location data with other systems
- **Reporting Systems**: Generate location-based reports
- **Business Intelligence**: Support BI tools with location data

## Best Practices

### API Usage

1. **Efficient Queries**: Use appropriate filters to limit result sets
2. **Pagination**: Always use pagination for large datasets
3. **Caching**: Cache frequently accessed location data
4. **Error Handling**: Implement proper error handling for all requests
5. **Performance Monitoring**: Monitor query performance and optimize as needed

### Data Management

1. **Data Quality**: Regularly validate and clean location data
2. **Consistency**: Maintain consistent naming conventions
3. **Updates**: Keep location data current and accurate
4. **Backup**: Regular backups of location data
5. **Documentation**: Document location data sources and formats

### Integration Guidelines

1. **Rate Limiting**: Implement appropriate rate limiting
2. **Timeout Handling**: Set reasonable request timeouts
3. **Retry Logic**: Implement retry logic for failed requests
4. **Monitoring**: Monitor API usage and performance
5. **Version Control**: Track API changes and maintain compatibility

## Future Enhancements

### Potential Improvements

- **Geographic Coordinates**: Add latitude/longitude support
- **Hierarchical Data**: Implement location hierarchy (continent → country → state → city)
- **Localization**: Multi-language location names
- **Time Zones**: Add time zone information for locations
- **Population Data**: Include population and demographic data

### Advanced Features

- **Geospatial Queries**: Distance-based location searches
- **Location Clustering**: Group nearby locations
- **Real-time Updates**: Live location data synchronization
- **Analytics Dashboard**: Location usage and performance analytics
- **Export Functionality**: Export location data in various formats

---

## Dashboard Authentication Issue

Regarding the error logs you shared, here's the issue and solution:

### Problem Analysis

The dashboard endpoint is experiencing a double error:

1. **Authentication failure**: Invalid or expired token
2. **Error handling issue**: 403 error being wrapped in 500 error

### Solution

The dashboard route should handle the authentication error properly. Here's the fix for the dashboard.py file:

```python
@router.get("/stats")
async def get_dashboard_stats(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        # Check permissions - this should be inside try block
        require_admin_or_superuser(current_user)

        # ... rest of the dashboard logic

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions (like 403) without wrapping in 500
        raise http_exc
    except Exception as e:
        # Only wrap unexpected errors in 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard statistics: {str(e)}"
        )
```

The key fix is to catch `HTTPException` separately and re-raise it, only wrapping unexpected exceptions in 500 errors.
