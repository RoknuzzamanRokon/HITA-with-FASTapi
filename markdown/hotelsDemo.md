# Hotels Demo Documentation

## Overview

The Hotels Demo system provides a simplified demonstration environment for hotel data management within the ITT Hotel API (HITA). This system allows administrators and super users to create, read, and manage demo hotel records for testing, development, and demonstration purposes.

## Architecture

### Core Components

- **Demo Router**: `/v1.0/hotels/demo` prefix
- **Demo Database Table**: Separate `demo_hotel` table
- **Admin-Only Creation**: Hotel creation restricted to admin users
- **Public Reading**: Hotel data accessible to all authenticated users
- **Simplified Schema**: Streamlined hotel data structure
- **CRUD Operations**: Create, read, and list operations

### Security Model

- **Super User**: Full access to create and read demo hotels
- **Admin User**: Full access to create and read demo hotels
- **General User**: Read-only access to demo hotels

### Route Prefix

```
/v1.0/hotels/demo
```

## Data Model

### Demo Hotel Schema

```python
class HotelCreateDemo(BaseModel):
    ittid: str                    # ITT unique identifier (max 50 chars)
    name: str                     # Hotel name (max 255 chars)
    latitude: Optional[str]       # Geographic latitude (max 50 chars)
    longitude: Optional[str]      # Geographic longitude (max 50 chars)
    rating: Optional[str]         # Hotel rating (max 10 chars)
    address_line1: Optional[str]  # Primary address (max 255 chars)
    address_line2: Optional[str]  # Secondary address (max 255 chars)
    city_name: Optional[str]      # City name (max 100 chars)
    state_name: Optional[str]     # State/province name (max 100 chars)
    state_code: Optional[str]     # State/province code (max 10 chars)
    country_name: Optional[str]   # Country name (max 100 chars)
    country_code: Optional[str]   # ISO country code (max 10 chars)
    postal_code: Optional[str]    # Postal/ZIP code (max 20 chars)
    city_code: Optional[str]      # City code (max 50 chars)
    city_location_id: Optional[str] # City location ID (max 50 chars)
    master_city_name: Optional[str] # Master city name (max 100 chars)
    location_ids: Optional[str]   # Location identifiers (max 255 chars)
```

### Database Model

```python
class DemoHotel(Base):
    __tablename__ = "demo_hotel"

    id = Column(Integer, primary_key=True, index=True)
    ittid = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    # ... all other fields from schema
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

## Demo Hotel Endpoints

### Create Demo Hotel

#### Endpoint

```http
POST /v1.0/hotels/demo/input
Authorization: Bearer <admin_token>
```

#### Request Body

```json
{
  "ittid": "DEMO001",
  "name": "Grand Demo Hotel",
  "latitude": "40.712776",
  "longitude": "-74.005974",
  "rating": "5",
  "address_line1": "123 Demo Street",
  "address_line2": "Suite 456",
  "city_name": "Demo City",
  "state_name": "Demo State",
  "state_code": "DS",
  "country_name": "Demo Country",
  "country_code": "DC",
  "postal_code": "12345",
  "city_code": "DEMO",
  "city_location_id": "LOC001",
  "master_city_name": "Demo Metropolitan Area",
  "location_ids": "LOC001,LOC002,LOC003"
}
```

#### Response (Success)

```json
{
  "id": 1,
  "ittid": "DEMO001",
  "name": "Grand Demo Hotel",
  "latitude": "40.712776",
  "longitude": "-74.005974",
  "rating": "5",
  "address_line1": "123 Demo Street",
  "address_line2": "Suite 456",
  "city_name": "Demo City",
  "state_name": "Demo State",
  "state_code": "DS",
  "country_name": "Demo Country",
  "country_code": "DC",
  "postal_code": "12345",
  "city_code": "DEMO",
  "city_location_id": "LOC001",
  "master_city_name": "Demo Metropolitan Area",
  "location_ids": "LOC001,LOC002,LOC003"
}
```

#### Response (Duplicate ITTID)

```json
{
  "detail": "A hotel with the same 'ittid' already exists."
}
```

#### Response (Access Denied)

```json
{
  "detail": "Access denied. Only super_user or admin_user can perform this action."
}
```

### Get All Demo Hotels

#### Endpoint

```http
GET /v1.0/hotels/demo/getAll?skip=0&limit=10
Authorization: Bearer <token>
```

#### Parameters

| Parameter | Type | Default | Description                         |
| --------- | ---- | ------- | ----------------------------------- |
| `skip`    | int  | 0       | Number of records to skip           |
| `limit`   | int  | 10      | Maximum number of records to return |

#### Response

```json
[
  {
    "id": 1,
    "ittid": "DEMO001",
    "name": "Grand Demo Hotel",
    "latitude": "40.712776",
    "longitude": "-74.005974",
    "rating": "5",
    "address_line1": "123 Demo Street",
    "address_line2": "Suite 456",
    "city_name": "Demo City",
    "state_name": "Demo State",
    "state_code": "DS",
    "country_name": "Demo Country",
    "country_code": "DC",
    "postal_code": "12345",
    "city_code": "DEMO",
    "city_location_id": "LOC001",
    "master_city_name": "Demo Metropolitan Area",
    "location_ids": "LOC001,LOC002,LOC003"
  },
  {
    "id": 2,
    "ittid": "DEMO002",
    "name": "Demo Resort & Spa",
    "latitude": "25.7617",
    "longitude": "-80.1918",
    "rating": "4",
    "address_line1": "456 Resort Boulevard",
    "city_name": "Miami",
    "state_name": "Florida",
    "state_code": "FL",
    "country_name": "United States",
    "country_code": "US",
    "postal_code": "33101"
  }
]
```

### Get Specific Demo Hotel

#### Endpoint

```http
GET /v1.0/hotels/demo/getAHotel/{hotel_id}
Authorization: Bearer <token>
```

#### Parameters

| Parameter  | Type | Location | Description            |
| ---------- | ---- | -------- | ---------------------- |
| `hotel_id` | int  | path     | Demo hotel database ID |

#### Request Example

```http
GET /v1.0/hotels/demo/getAHotel/1
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Response (Success)

```json
{
  "id": 1,
  "ittid": "DEMO001",
  "name": "Grand Demo Hotel",
  "latitude": "40.712776",
  "longitude": "-74.005974",
  "rating": "5",
  "address_line1": "123 Demo Street",
  "address_line2": "Suite 456",
  "city_name": "Demo City",
  "state_name": "Demo State",
  "state_code": "DS",
  "country_name": "Demo Country",
  "country_code": "DC",
  "postal_code": "12345",
  "city_code": "DEMO",
  "city_location_id": "LOC001",
  "master_city_name": "Demo Metropolitan Area",
  "location_ids": "LOC001,LOC002,LOC003"
}
```

#### Response (Not Found)

```json
{
  "detail": "Hotel not found"
}
```

## Security and Access Control

### Authentication Requirements

- **JWT Token**: Valid authentication token required for all endpoints
- **Role-Based Access**: Different access levels for different operations

### Access Control Matrix

| Operation           | Super User | Admin User | General User |
| ------------------- | ---------- | ---------- | ------------ |
| Create Hotel        | ✅         | ✅         | ❌           |
| Read All Hotels     | ✅         | ✅         | ✅           |
| Read Specific Hotel | ✅         | ✅         | ✅           |

### Permission Implementation

```python
# Admin-only creation
require_role(["super_user", "admin_user"], current_user)

# Authenticated read access
current_user: models.User = Depends(get_current_user)
```

## Data Validation

### Required Fields

- **ittid**: Unique identifier (required, max 50 characters)
- **name**: Hotel name (required, max 255 characters)

### Optional Fields

All other fields are optional with specific length constraints:

- **Geographic**: latitude, longitude (max 50 characters each)
- **Address**: address_line1, address_line2 (max 255 characters each)
- **Location**: city_name, state_name, country_name (max 100 characters each)
- **Codes**: state_code, country_code, city_code (various length limits)

### Validation Rules

- **ITTID Uniqueness**: No duplicate ITTID values allowed
- **Length Constraints**: All fields have maximum length limits
- **Data Types**: All fields are strings for flexibility
- **Null Handling**: Optional fields can be null or empty

## Use Cases

### Development and Testing

- **API Testing**: Test hotel-related functionality without affecting production data
- **Integration Testing**: Verify API integrations with sample data
- **Performance Testing**: Load testing with controlled demo data
- **Feature Development**: Develop new features using demo environment

### Demonstrations and Training

- **Client Demos**: Show API capabilities with sample hotel data
- **Training Sessions**: Train users on API functionality
- **Documentation Examples**: Provide realistic examples in documentation
- **Proof of Concept**: Demonstrate system capabilities to stakeholders

### Data Modeling and Validation

- **Schema Testing**: Validate data models and structures
- **Field Testing**: Test field constraints and validation rules
- **Data Migration**: Test data migration procedures
- **Quality Assurance**: Verify data handling and processing

## Error Handling

### Common Error Scenarios

#### Duplicate ITTID

- **Cause**: Attempting to create hotel with existing ITTID
- **Response**: HTTP 400 with duplicate error message
- **Resolution**: Use unique ITTID or update existing record

#### Access Denied

- **Cause**: General user attempting to create hotel
- **Response**: HTTP 403 with access denied message
- **Resolution**: Use admin or super user account

#### Hotel Not Found

- **Cause**: Requesting non-existent hotel ID
- **Response**: HTTP 404 with not found message
- **Resolution**: Verify hotel ID exists in demo database

#### Validation Errors

- **Cause**: Invalid data format or length constraints
- **Response**: HTTP 400 with validation error details
- **Resolution**: Correct data format and field lengths

### Error Response Format

```json
{
  "detail": "Error description"
}
```

## Performance Considerations

### Database Optimization

- **Indexed Fields**: Primary key and ITTID are indexed
- **Pagination**: Built-in skip/limit pagination support
- **Efficient Queries**: Simple queries for fast response times
- **Separate Table**: Demo data isolated from production data

### Scalability Factors

- **Lightweight Schema**: Simplified data structure for performance
- **Minimal Dependencies**: Reduced complexity for faster operations
- **Caching Potential**: Simple data structure suitable for caching
- **Resource Efficiency**: Low resource usage for demo operations

## Integration Examples

### Create Demo Hotel

```python
import requests

# Create a new demo hotel
hotel_data = {
    "ittid": "DEMO001",
    "name": "Grand Demo Hotel",
    "latitude": "40.712776",
    "longitude": "-74.005974",
    "rating": "5",
    "address_line1": "123 Demo Street",
    "city_name": "Demo City",
    "country_name": "Demo Country"
}

response = requests.post(
    f"{base_url}/v1.0/hotels/demo/input",
    headers={"Authorization": f"Bearer {admin_token}"},
    json=hotel_data
)

if response.status_code == 201:
    created_hotel = response.json()
    print(f"Created hotel: {created_hotel['name']} (ID: {created_hotel['id']})")
else:
    print(f"Error: {response.json()['detail']}")
```

### Retrieve Demo Hotels

```python
# Get all demo hotels with pagination
response = requests.get(
    f"{base_url}/v1.0/hotels/demo/getAll?skip=0&limit=5",
    headers={"Authorization": f"Bearer {token}"}
)

if response.status_code == 200:
    hotels = response.json()
    print(f"Retrieved {len(hotels)} demo hotels")
    for hotel in hotels:
        print(f"- {hotel['name']} ({hotel['ittid']})")
```

### Get Specific Demo Hotel

```python
# Get a specific demo hotel by ID
hotel_id = 1
response = requests.get(
    f"{base_url}/v1.0/hotels/demo/getAHotel/{hotel_id}",
    headers={"Authorization": f"Bearer {token}"}
)

if response.status_code == 200:
    hotel = response.json()
    print(f"Hotel: {hotel['name']}")
    print(f"Location: {hotel['city_name']}, {hotel['country_name']}")
    print(f"Rating: {hotel['rating']}")
else:
    print(f"Hotel not found: {response.json()['detail']}")
```

### Bulk Demo Data Creation

```python
# Create multiple demo hotels
demo_hotels = [
    {
        "ittid": "DEMO001",
        "name": "Grand Demo Hotel",
        "city_name": "New York",
        "country_name": "United States",
        "rating": "5"
    },
    {
        "ittid": "DEMO002",
        "name": "Demo Resort & Spa",
        "city_name": "Miami",
        "country_name": "United States",
        "rating": "4"
    },
    {
        "ittid": "DEMO003",
        "name": "Demo Business Hotel",
        "city_name": "Chicago",
        "country_name": "United States",
        "rating": "3"
    }
]

created_hotels = []
for hotel_data in demo_hotels:
    response = requests.post(
        f"{base_url}/v1.0/hotels/demo/input",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=hotel_data
    )

    if response.status_code == 201:
        created_hotels.append(response.json())
        print(f"Created: {hotel_data['name']}")
    else:
        print(f"Failed to create {hotel_data['name']}: {response.json()['detail']}")

print(f"Successfully created {len(created_hotels)} demo hotels")
```

## Best Practices

### Demo Data Management

1. **Unique ITTIDs**: Use clear, descriptive ITTID patterns (e.g., DEMO001, DEMO002)
2. **Realistic Data**: Use realistic but clearly identifiable demo data
3. **Consistent Naming**: Follow consistent naming conventions for demo hotels
4. **Regular Cleanup**: Periodically clean up outdated demo data
5. **Documentation**: Document demo data for team reference

### Development Usage

1. **Isolated Environment**: Keep demo data separate from production
2. **Version Control**: Track demo data changes in version control
3. **Test Coverage**: Use demo data for comprehensive testing
4. **Performance Testing**: Test with various demo data volumes
5. **Error Scenarios**: Create demo data for error condition testing

### Security Considerations

1. **Access Control**: Maintain proper access controls for demo creation
2. **Data Sensitivity**: Ensure demo data doesn't contain sensitive information
3. **Regular Audits**: Review demo data access and usage patterns
4. **Clean Credentials**: Use clean, non-production credentials for demos
5. **Environment Separation**: Clearly separate demo from production environments

## Monitoring and Maintenance

### Usage Monitoring

- **Creation Patterns**: Track demo hotel creation frequency
- **Access Patterns**: Monitor demo data access patterns
- **Error Rates**: Track errors in demo operations
- **Performance Metrics**: Monitor demo endpoint performance

### Data Maintenance

- **Regular Cleanup**: Remove outdated or unused demo data
- **Data Validation**: Verify demo data integrity
- **Schema Updates**: Keep demo schema in sync with production
- **Backup Procedures**: Backup important demo datasets

## Future Enhancements

### Potential Improvements

- **Update Operations**: Add PUT/PATCH endpoints for demo hotel updates
- **Delete Operations**: Add DELETE endpoint for demo hotel removal
- **Search Functionality**: Add search and filtering capabilities
- **Bulk Operations**: Support for bulk create/update/delete operations
- **Data Templates**: Predefined demo hotel templates

### Advanced Features

- **Demo Scenarios**: Predefined demo scenarios for different use cases
- **Data Relationships**: Support for related demo data (rooms, amenities)
- **Export/Import**: Export and import demo datasets
- **Automated Generation**: Automated demo data generation
- **Demo Analytics**: Analytics and reporting for demo data usage
