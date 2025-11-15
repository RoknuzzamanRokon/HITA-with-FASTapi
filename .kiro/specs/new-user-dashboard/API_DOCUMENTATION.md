# New User Dashboard API Documentation

## Overview

The `/v1.0/dashboard/new-user` endpoint has been fully documented with comprehensive OpenAPI specifications and Pydantic response models.

## OpenAPI Documentation Features

### 1. Endpoint Metadata

- **Path**: `/v1.0/dashboard/new-user`
- **Method**: GET
- **Summary**: Get New User Dashboard
- **Tags**: Dashboard
- **Authentication**: JWT Bearer Token (required)

### 2. Comprehensive Description

The endpoint documentation includes:

- Feature overview and purpose
- Key features list
- Dashboard sections breakdown
- Time-series data format specifications
- Performance characteristics
- Access control requirements

### 3. Response Model

A complete Pydantic response model (`NewUserDashboardResponse`) has been created with:

- Nested schema definitions for all response sections
- Field-level descriptions and examples
- Type validation and constraints
- Complete example response JSON

### 4. Response Status Codes

Documented responses for all scenarios:

- **200 OK**: Successful response with complete dashboard data
- **401 Unauthorized**: Invalid or missing JWT token
- **500 Internal Server Error**: Database or system errors
- **504 Gateway Timeout**: Request exceeded 30-second timeout

### 5. Example Responses

Each status code includes:

- Detailed description of when it occurs
- Complete example JSON response
- Error message formats

## Pydantic Response Models

### Schema Hierarchy

```
NewUserDashboardResponse
├── AccountInfo
│   ├── OnboardingProgress
│   │   └── PendingStep[]
├── UserResources
│   ├── SupplierResources
│   └── PointResources
├── PlatformOverview
│   ├── AvailableSupplier[]
│   └── AvailablePackage[]
├── ActivityMetrics
│   ├── UserLoginMetrics
│   │   └── TimeSeriesDataPoint[]
│   └── APIRequestMetrics
│       └── TimeSeriesDataPoint[]
├── PlatformTrends
│   ├── TrendData (user_registrations)
│   │   └── TimeSeriesDataPoint[]
│   └── TrendData (hotel_updates)
│       └── TimeSeriesDataPoint[]
├── Recommendations
│   └── RecommendationStep[]
└── DashboardMetadata
```

### Key Schema Components

#### TimeSeriesDataPoint

```python
{
    "date": "2024-11-15",  # YYYY-MM-DD format
    "value": 5              # Integer value
}
```

#### OnboardingProgress

```python
{
    "completion_percentage": 33,  # 0-100
    "completed_steps": ["account_created"],
    "pending_steps": [
        {
            "action": "supplier_assignment",
            "description": "Contact administrator...",
            "estimated_time": "1-2 business days"
        }
    ]
}
```

#### TrendData

```python
{
    "title": "New User Registrations",
    "unit": "users",
    "data_type": "count",
    "time_series": [
        {"date": "2024-11-15", "value": 2}
    ]
}
```

## Time-Series Data Format

All time-series data follows a consistent structure:

### Format Specifications

- **Date Format**: YYYY-MM-DD (ISO 8601 date only)
- **Granularity**: Daily
- **Period**: 30 days
- **Missing Dates**: Filled with zero values
- **Sorting**: Chronological (oldest to newest)

### Example Time-Series

```json
{
  "time_series": [
    { "date": "2024-10-16", "value": 0 },
    { "date": "2024-10-17", "value": 1 },
    { "date": "2024-10-18", "value": 0 },
    { "date": "2024-11-14", "value": 2 },
    { "date": "2024-11-15", "value": 2 }
  ]
}
```

## Accessing the Documentation

### Swagger UI

1. Start the FastAPI application
2. Navigate to `http://localhost:8000/docs`
3. Find the "Dashboard" section
4. Expand the `/v1.0/dashboard/new-user` endpoint
5. View:
   - Complete endpoint description
   - Request parameters
   - Response schemas with examples
   - Try it out functionality

### ReDoc

1. Navigate to `http://localhost:8000/redoc`
2. Find "Dashboard" in the navigation
3. View detailed documentation with:
   - Schema definitions
   - Example responses
   - Field descriptions

## Response Field Documentation

### account_info

- **user_id**: User unique identifier
- **username**: Username
- **email**: User email address
- **account_status**: Current status (pending_activation, active, suspended)
- **created_at**: Account creation timestamp (ISO 8601)
- **days_since_registration**: Days since account was created
- **onboarding_progress**: Detailed onboarding progress tracking

### user_resources

- **suppliers**: Supplier permission status
  - **active_count**: Number of active supplier permissions
  - **total_available**: Total suppliers in the system
  - **assigned_suppliers**: List of assigned supplier names
  - **pending_assignment**: Whether assignment is pending
- **points**: Point allocation status
  - **current_balance**: Current point balance
  - **total_allocated**: Total points ever allocated
  - **package_type**: Point package type (if any)
  - **pending_allocation**: Whether allocation is pending

### platform_overview

- **total_users**: Total registered users
- **total_hotels**: Total hotels in the system
- **total_mappings**: Total provider mappings
- **available_suppliers**: List of available suppliers with hotel counts
- **available_packages**: List of available point packages with descriptions

### activity_metrics

- **user_logins**: User login activity
  - **total_count**: Total login count
  - **last_login**: Last login timestamp
  - **time_series**: 30-day login time-series data
- **api_requests**: User API request activity
  - **total_count**: Total API request count
  - **time_series**: 30-day API request time-series data

### platform_trends

- **user_registrations**: Platform user registration trends
  - **title**: "New User Registrations"
  - **unit**: "users"
  - **data_type**: "count"
  - **time_series**: 30-day registration time-series data
- **hotel_updates**: Platform hotel update trends
  - **title**: "Hotel Data Updates"
  - **unit**: "hotels"
  - **data_type**: "count"
  - **time_series**: 30-day update time-series data

### recommendations

- **next_steps**: List of recommended actions
  - **priority**: Priority order (1 = highest)
  - **action**: Action title
  - **description**: Detailed description
  - **contact_info**: Contact information
  - **estimated_time**: Estimated completion time
- **estimated_activation_time**: Overall activation time estimate

### metadata

- **timestamp**: Response generation timestamp (ISO 8601)
- **cache_status**: Cache status (cached/fresh)
- **data_freshness**: Component-level freshness timestamps

## Testing the Documentation

The endpoint has been tested with:

- ✅ Valid authentication scenarios
- ✅ Error scenarios (401, 500, 504)
- ✅ Response structure validation
- ✅ Time-series data format validation
- ✅ New user scenarios (0 suppliers, 0 points)

## Requirements Coverage

This documentation implementation satisfies:

- **Requirement 6.1**: Endpoint appears in OpenAPI schema with clear descriptions
- **Requirement 6.2**: All response fields documented with descriptions and examples
- **Requirement 6.5**: Time-series data format fully documented
- **All Requirements**: Complete endpoint documentation covering all features

## Next Steps

To view the documentation:

1. Ensure the FastAPI application is running
2. Visit `/docs` for interactive Swagger UI
3. Visit `/redoc` for detailed ReDoc documentation
4. Use the "Try it out" feature to test the endpoint with authentication
