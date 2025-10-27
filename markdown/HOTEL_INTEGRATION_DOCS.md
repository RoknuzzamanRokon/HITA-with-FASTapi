# Hotel Integration API Documentation

This document provides comprehensive documentation for the Hotel Integration API endpoints in `hotelIntegration.py`.

## Overview

The Hotel Integration API provides endpoints for managing hotel data, provider mappings, and supplier integrations. All endpoints include comprehensive error handling, role-based access control, and detailed logging.

## Endpoints

### 1. Create Hotel with Complete Details

**Endpoint:** `POST /v1.0/hotels/input_hotel_all_details`

**Description:** Creates a comprehensive hotel record with all associated data including locations, provider mappings, contacts, and chain information.

**Access Control:** Super User and Admin User only

**Features:**

- Complete hotel record creation with all related entities
- Transactional integrity with automatic rollback on errors
- Comprehensive validation and error handling
- Automatic ITTID generation and relationship management

**Request Body:** `HotelCreate` schema with nested objects for:

- Basic hotel information (name, address, rating, etc.)
- Location data (city, state, country, coordinates)
- Provider mappings (supplier integrations and IDs)
- Contact information (phone, email, website, fax)
- Chain information (hotel chain affiliations)

**Response:** `HotelRead` - Created hotel record with generated ITTID and timestamps

**Error Codes:**

- `400`: Invalid hotel data or validation errors
- `401`: User not authenticated
- `403`: Insufficient privileges (non-admin users)
- `409`: Duplicate hotel data or constraint violations
- `500`: Database errors or system failures

---

### 2. Add Provider Mapping to Existing Hotel

**Endpoint:** `POST /v1.0/hotels/add_provider_all_details_with_ittid`

**Description:** Creates a new provider mapping for an existing hotel, enabling integration with external hotel suppliers and booking systems.

**Access Control:** Super User and Admin User only

**Features:**

- Provider mapping creation for existing hotels
- Duplicate detection and prevention
- Hotel existence validation
- Comprehensive error handling and logging

**Request Body:**

```json
{
  "ittid": "ITT123456",
  "provider_name": "booking",
  "provider_id": "hotel_12345",
  "system_type": "OTA",
  "giata_code": "67890"
}
```

**Response:**

```json
{
    "message": "Provider mapping added successfully",
    "provider_mapping": { ... },
    "operation_type": "created",
    "timestamp": "2024-01-15T10:30:00Z",
    "hotel_name": "Example Hotel"
}
```

**Error Codes:**

- `400`: Invalid provider data or validation errors
- `401`: User not authenticated
- `403`: Insufficient privileges (non-admin users)
- `404`: Hotel with specified ITTID not found
- `409`: Duplicate provider mapping (handled gracefully)
- `500`: Database errors or system failures

---

### 3. Get Supplier Information

**Endpoint:** `GET /v1.0/hotels/get_supplier_info?supplier={supplier_name}`

**Description:** Retrieves comprehensive information about a specific supplier including total hotel count and access permissions.

**Access Control:** Role-based access with permission validation

**Features:**

- Supplier-specific hotel count and statistics
- Role-based access control with permission validation
- Comprehensive supplier information and metadata
- User permission tracking and validation

**Query Parameters:**

- `supplier` (required): Supplier/provider name to get information for

**Response:**

```json
{
  "supplier_name": "booking",
  "total_hotel": 15420,
  "user_role": "general_user",
  "access_granted": true,
  "access_type": "permission_granted",
  "supplier_metadata": {
    "system_types": ["OTA"],
    "has_hotels": true,
    "last_checked": "2024-01-15T10:30:00Z"
  }
}
```

**Error Codes:**

- `400`: Missing or invalid supplier parameter
- `401`: User not authenticated
- `403`: Insufficient permissions or no access to specified supplier
- `404`: Supplier not found in the system
- `500`: Database errors or system failures

---

### 4. Get User's Accessible Suppliers

**Endpoint:** `GET /v1.0/hotels/get_user_accessible_suppliers`

**Description:** Retrieves a comprehensive list of suppliers/providers that the current user has access to, along with hotel counts and access type information.

**Access Control:** All authenticated users (results filtered by role)

**Features:**

- Role-based supplier access listing
- Comprehensive supplier information with hotel counts
- Access type classification and permissions tracking
- Supplier availability and system status information

**Response:**

```json
{
  "user_id": "user123",
  "user_role": "general_user",
  "accessible_suppliers": [
    {
      "supplier_name": "booking",
      "total_hotels": 15420,
      "access_type": "permission_granted",
      "system_types": ["OTA"],
      "availability_status": "active"
    }
  ],
  "total_accessible_suppliers": 1,
  "access_summary": {
    "total_suppliers_in_system": 5,
    "accessible_suppliers": 1,
    "access_type": "permission_granted",
    "permission_based": true
  },
  "supplier_analytics": {
    "total_hotels_accessible": 15420,
    "active_suppliers": 1,
    "inactive_suppliers": 0,
    "access_coverage_percentage": 20.0
  }
}
```

**Error Codes:**

- `401`: User not authenticated
- `403`: User role not recognized or insufficient permissions
- `500`: Database errors or system failures

## Access Control Matrix

| Role         | Create Hotel   | Add Provider   | Get Supplier Info | Get Accessible Suppliers |
| ------------ | -------------- | -------------- | ----------------- | ------------------------ |
| SUPER_USER   | ✅ Full Access | ✅ Full Access | ✅ All Suppliers  | ✅ All Suppliers         |
| ADMIN_USER   | ✅ Full Access | ✅ Full Access | ✅ All Suppliers  | ✅ All Suppliers         |
| GENERAL_USER | ❌ No Access   | ❌ No Access   | ✅ Permitted Only | ✅ Permitted Only        |

## Error Handling

All endpoints include comprehensive error handling with:

### Try-Catch Blocks

- Database operation error handling
- Input validation error handling
- Authentication and authorization error handling
- Unexpected error handling with logging

### HTTP Status Codes

- `200`: Success
- `201`: Created successfully
- `400`: Bad Request - Invalid input data
- `401`: Unauthorized - Authentication required
- `403`: Forbidden - Insufficient permissions
- `404`: Not Found - Resource not found
- `409`: Conflict - Duplicate data or constraint violations
- `500`: Internal Server Error - System or database errors

### Error Response Format

```json
{
  "detail": "Descriptive error message",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Logging

All endpoints include comprehensive logging:

- Request logging with user identification
- Operation success/failure logging
- Error logging with stack traces
- Performance and access pattern logging

## Database Operations

### Transactional Integrity

- All multi-table operations use database transactions
- Automatic rollback on any failure
- Foreign key relationship management
- Constraint validation and duplicate prevention

### Performance Optimization

- Optimized queries with proper indexing
- Efficient joins and aggregations
- Minimal database calls for bulk operations
- Caching-friendly response structures

## Testing

Use the provided test script to verify endpoint visibility:

```bash
python test_hotel_integration_docs.py
```

This script tests:

- OpenAPI schema endpoint visibility
- Swagger UI accessibility (/docs)
- ReDoc accessibility (/redoc)

## Documentation Visibility

All endpoints are now visible in:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

The endpoints were previously hidden with `include_in_schema=False` but this has been removed to ensure full documentation visibility.

## Security Considerations

- Role-based access control on all endpoints
- Input validation and sanitization
- SQL injection prevention through ORM
- Comprehensive audit logging
- Error message sanitization to prevent information disclosure
