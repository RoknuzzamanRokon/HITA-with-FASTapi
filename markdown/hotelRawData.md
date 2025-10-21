# Hotel Raw Data Documentation

## Overview

The Hotel Raw Data system provides secure access to unprocessed hotel content data directly from supplier sources. This system allows administrators and super users to access the original, unmodified hotel data as received from various suppliers, enabling data analysis, debugging, and content verification.

## Architecture

### Core Components

- **Raw Data Router**: `/v1.0/hotel` prefix
- **File-Based Storage**: JSON files organized by supplier
- **Admin-Only Access**: Restricted to super users and admin users
- **Audit Logging**: Comprehensive access tracking
- **Security Controls**: High-level security monitoring
- **Supplier Organization**: Data organized by supplier code

### Security Model

- **Super User**: Full access to all supplier raw data
- **Admin User**: Full access to all supplier raw data
- **General User**: No access to raw data endpoints

### Route Prefix

```
/v1.0/hotel
```

## Data Storage Structure

### Directory Organization

```
RAW_BASE_DIR/
├── hotelbeds/
│   ├── 12345.json
│   ├── 12346.json
│   └── ...
├── tbo/
│   ├── 67890.json
│   ├── 67891.json
│   └── ...
├── expedia/
│   ├── 11111.json
│   ├── 11112.json
│   └── ...
└── booking/
    ├── 22222.json
    ├── 22223.json
    └── ...
```

### File Naming Convention

- **Format**: `{hotel_id}.json`
- **Location**: `{RAW_BASE_DIR}/{supplier_code}/{hotel_id}.json`
- **Encoding**: UTF-8
- **Format**: JSON

### Configuration Paths

```python
# Local Development
RAW_BASE_DIR = r"D:\content_for_hotel_json\cdn_row_collection"
RATE_BASE_DIR = r"D:\content_for_hotel_json\with_rate"

# Production Server
RAW_BASE_DIR = r"/var/www/Storage-Contents/Hotel-Supplier-Raw-Contents"
RATE_BASE_DIR = r"/var/www/Storage-Contents/Hotel-Supplier-Rates"
```

## Raw Data Endpoint

### Get Supplier Raw Data

#### Endpoint

```http
POST /v1.0/hotel/supplier
Authorization: Bearer <admin_token>
```

#### Request Body

```json
{
  "supplier_code": "hotelbeds",
  "hotel_id": "12345"
}
```

#### Parameters

| Parameter       | Type   | Required | Description                                    |
| --------------- | ------ | -------- | ---------------------------------------------- |
| `supplier_code` | string | Yes      | Supplier identifier (e.g., "hotelbeds", "tbo") |
| `hotel_id`      | string | Yes      | Hotel ID as provided by the supplier           |

#### Response (Success)

```json
{
  "hotel_id": "12345",
  "supplier": "hotelbeds",
  "name": "Grand Hotel Barcelona",
  "description": "Luxury hotel in the heart of Barcelona",
  "address": {
    "street": "Carrer de Pelai, 14",
    "city": "Barcelona",
    "country": "Spain",
    "postal_code": "08001"
  },
  "coordinates": {
    "latitude": 41.3851,
    "longitude": 2.1734
  },
  "amenities": ["WiFi", "Pool", "Spa", "Restaurant", "Gym"],
  "room_types": [
    {
      "room_id": "STD001",
      "name": "Standard Room",
      "description": "Comfortable standard room with city view",
      "max_occupancy": 2,
      "bed_type": "Queen",
      "amenities": ["WiFi", "TV", "Air Conditioning"]
    }
  ],
  "images": [
    {
      "url": "https://supplier.com/images/hotel1.jpg",
      "type": "exterior",
      "description": "Hotel exterior view"
    }
  ],
  "policies": {
    "check_in": "15:00",
    "check_out": "11:00",
    "cancellation": "Free cancellation up to 24 hours before arrival"
  },
  "contact": {
    "phone": "+34 93 123 4567",
    "email": "info@grandhotelbarcelona.com",
    "website": "https://www.grandhotelbarcelona.com"
  },
  "last_updated": "2024-12-17T15:30:00Z",
  "supplier_metadata": {
    "source_system": "hotelbeds_api",
    "data_version": "v2.1",
    "extraction_date": "2024-12-17T10:00:00Z"
  }
}
```

#### Response (File Not Found)

```json
{
  "detail": "File not found"
}
```

#### Response (Invalid JSON)

```json
{
  "detail": "Invalid JSON file"
}
```

#### Response (Access Denied)

```json
{
  "detail": "Access denied. Only super users and admin users can access supplier data."
}
```

## Security and Access Control

### Authentication Requirements

- **JWT Token**: Valid authentication token required
- **Role Verification**: Super user or admin user role required
- **High Security Level**: Classified as high-security operation

### Access Control Implementation

```python
# Security check
if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied. Only super users and admin users can access supplier data."
    )
```

### Audit Logging

Every access to raw data is logged with:

- **Activity Type**: API_ACCESS
- **User Information**: User ID and role
- **Request Details**: Supplier code and hotel ID
- **Security Level**: HIGH
- **Timestamp**: Request timestamp
- **IP Address**: Request origin

```python
audit_logger.log_activity(
    activity_type=ActivityType.API_ACCESS,
    user_id=current_user.id,
    details={
        "endpoint": "/v1.0/hotel/supplier",
        "action": "access_supplier_data",
        "supplier_code": request_body.supplier_code,
        "hotel_id": request_body.hotel_id
    },
    request=request,
    security_level=SecurityLevel.HIGH,
    success=True
)
```

## Data Format and Structure

### Raw Data Characteristics

- **Unprocessed Content**: Original data as received from suppliers
- **Supplier-Specific Format**: Each supplier may have different data structures
- **Complete Information**: All available data fields from the supplier
- **Metadata Included**: Extraction timestamps and version information

### Common Data Fields

While each supplier has unique formats, common fields include:

#### Hotel Information

- **Basic Details**: Name, description, category/rating
- **Location**: Address, coordinates, geographic information
- **Contact**: Phone, email, website information
- **Policies**: Check-in/out times, cancellation policies

#### Room Information

- **Room Types**: Different room categories and descriptions
- **Occupancy**: Maximum guests per room
- **Amenities**: Room-specific features and services
- **Bed Configuration**: Bed types and quantities

#### Facility Information

- **Hotel Amenities**: Pool, spa, restaurant, gym, etc.
- **Services**: Concierge, room service, business center
- **Accessibility**: Wheelchair access, special needs facilities

#### Media Content

- **Images**: Hotel and room photos with descriptions
- **Virtual Tours**: 360-degree views and virtual walkthroughs
- **Videos**: Promotional and informational videos

### Supplier-Specific Variations

#### Hotelbeds Format

```json
{
  "hotel": {
    "code": "12345",
    "name": "Grand Hotel",
    "categoryCode": "5EST",
    "coordinates": {
      "latitude": 41.3851,
      "longitude": 2.1734
    },
    "facilities": [
      {
        "facilityCode": 1,
        "facilityGroupCode": 10,
        "order": 1,
        "number": 1
      }
    ]
  }
}
```

#### TBO Format

```json
{
  "HotelDetails": {
    "HotelCode": "67890",
    "HotelName": "Luxury Resort",
    "StarRating": 5,
    "Location": {
      "Latitude": "25.2048",
      "Longitude": "55.2708"
    },
    "Amenities": [
      {
        "AmenityCode": "WIFI",
        "AmenityName": "Free WiFi"
      }
    ]
  }
}
```

## Use Cases

### Data Analysis and Research

- **Content Comparison**: Compare data across different suppliers
- **Data Quality Assessment**: Identify inconsistencies and gaps
- **Market Research**: Analyze supplier coverage and content depth
- **Competitive Analysis**: Compare supplier offerings

### Debugging and Troubleshooting

- **Data Mapping Issues**: Investigate mapping problems
- **Content Discrepancies**: Resolve data inconsistencies
- **Integration Problems**: Debug supplier integration issues
- **Quality Assurance**: Verify data processing accuracy

### Content Management

- **Data Enrichment**: Enhance processed data with raw content
- **Missing Information**: Fill gaps in processed data
- **Content Validation**: Verify processed data accuracy
- **Supplier Relationship**: Understand supplier data capabilities

## Error Handling

### Common Error Scenarios

#### File Not Found

- **Cause**: Hotel ID doesn't exist for the specified supplier
- **Response**: HTTP 404 with "File not found" message
- **Resolution**: Verify hotel ID and supplier code combination

#### Invalid JSON Format

- **Cause**: Corrupted or malformed JSON file
- **Response**: HTTP 500 with "Invalid JSON file" message
- **Resolution**: Check file integrity and re-download from supplier

#### Access Denied

- **Cause**: User lacks required permissions
- **Response**: HTTP 403 with access denied message
- **Resolution**: Ensure user has admin or super user role

#### File System Errors

- **Cause**: Disk space, permissions, or network issues
- **Response**: HTTP 500 with system error message
- **Resolution**: Check file system and server configuration

### Error Response Format

```json
{
  "detail": "Error description"
}
```

## Performance Considerations

### File Access Optimization

- **Direct File Reading**: Efficient file system access
- **UTF-8 Encoding**: Proper character encoding handling
- **Memory Management**: Efficient JSON parsing
- **Caching Strategy**: Consider caching frequently accessed files

### Scalability Factors

- **File System Performance**: SSD storage recommended
- **Network Latency**: Local storage preferred over network storage
- **Concurrent Access**: Handle multiple simultaneous requests
- **File Size Management**: Monitor and manage large JSON files

## Security Best Practices

### Data Protection

- **Access Logging**: Comprehensive audit trail
- **Role-Based Access**: Strict permission enforcement
- **Secure Storage**: Protected file system access
- **Data Encryption**: Consider encryption for sensitive data

### Operational Security

- **Regular Audits**: Review access patterns and logs
- **Permission Reviews**: Regular role and access reviews
- **Monitoring**: Monitor for unusual access patterns
- **Backup Security**: Secure backup and recovery procedures

## Integration Examples

### Basic Raw Data Access

```python
import requests

# Access raw hotel data
response = requests.post(
    f"{base_url}/v1.0/hotel/supplier",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={
        "supplier_code": "hotelbeds",
        "hotel_id": "12345"
    }
)

if response.status_code == 200:
    raw_data = response.json()
    print(f"Hotel Name: {raw_data.get('name', 'N/A')}")
    print(f"Supplier: {raw_data.get('supplier', 'N/A')}")
else:
    print(f"Error: {response.json()['detail']}")
```

### Data Analysis Script

```python
# Analyze raw data from multiple suppliers
suppliers = ["hotelbeds", "tbo", "expedia"]
hotel_ids = ["12345", "67890", "11111"]

for supplier in suppliers:
    for hotel_id in hotel_ids:
        try:
            response = requests.post(
                f"{base_url}/v1.0/hotel/supplier",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "supplier_code": supplier,
                    "hotel_id": hotel_id
                }
            )

            if response.status_code == 200:
                raw_data = response.json()
                # Analyze data structure and content
                analyze_hotel_data(raw_data, supplier)
            else:
                print(f"No data for {supplier}:{hotel_id}")

        except Exception as e:
            print(f"Error accessing {supplier}:{hotel_id} - {e}")
```

### Content Validation

```python
# Validate processed data against raw data
def validate_hotel_content(processed_data, supplier_code, hotel_id):
    # Get raw data
    raw_response = requests.post(
        f"{base_url}/v1.0/hotel/supplier",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "supplier_code": supplier_code,
            "hotel_id": hotel_id
        }
    )

    if raw_response.status_code == 200:
        raw_data = raw_response.json()

        # Compare key fields
        validation_results = {
            "name_match": processed_data.get("name") == raw_data.get("name"),
            "address_match": compare_addresses(processed_data, raw_data),
            "amenities_match": compare_amenities(processed_data, raw_data)
        }

        return validation_results
    else:
        return {"error": "Could not retrieve raw data"}
```

## Monitoring and Maintenance

### Access Monitoring

- **Usage Patterns**: Track access frequency and patterns
- **User Activity**: Monitor which users access raw data
- **Popular Content**: Identify frequently accessed hotels
- **Error Rates**: Monitor file access errors

### Data Maintenance

- **File Integrity**: Regular file integrity checks
- **Storage Management**: Monitor disk space usage
- **Data Freshness**: Track data update timestamps
- **Cleanup Procedures**: Remove outdated or corrupted files

### Performance Monitoring

- **Response Times**: Monitor file access performance
- **System Resources**: Track CPU and memory usage
- **Concurrent Access**: Monitor simultaneous request handling
- **Error Tracking**: Log and analyze error patterns

## Best Practices

### Data Access

1. **Verify Permissions**: Always check user permissions before access
2. **Log All Access**: Maintain comprehensive audit logs
3. **Handle Errors Gracefully**: Provide meaningful error messages
4. **Validate Input**: Verify supplier codes and hotel IDs
5. **Monitor Usage**: Track access patterns and performance

### Security

1. **Principle of Least Privilege**: Restrict access to necessary users only
2. **Regular Audits**: Review access logs and permissions regularly
3. **Secure Storage**: Protect raw data files from unauthorized access
4. **Data Classification**: Treat raw data as sensitive information
5. **Incident Response**: Have procedures for security incidents

### Operational

1. **Backup Strategy**: Regular backups of raw data files
2. **Disaster Recovery**: Recovery procedures for data loss
3. **Capacity Planning**: Monitor storage growth and plan capacity
4. **Documentation**: Maintain current documentation
5. **Training**: Train users on proper raw data access procedures

## Future Enhancements

### Potential Improvements

- **Caching Layer**: Implement caching for frequently accessed files
- **Batch Access**: Support for bulk raw data retrieval
- **Data Streaming**: Stream large files for better performance
- **Search Capabilities**: Search within raw data content
- **Version Control**: Track changes in raw data over time

### Advanced Features

- **Data Comparison**: Built-in tools for comparing raw data
- **Content Analysis**: Automated analysis of raw data quality
- **Export Functionality**: Export raw data in different formats
- **Real-time Updates**: Real-time synchronization with suppliers
- **Data Visualization**: Visual representation of raw data structure
