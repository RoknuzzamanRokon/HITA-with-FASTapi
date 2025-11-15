# Design Document

## Overview

This design document outlines the implementation of a comprehensive dashboard feature for newly registered users in the HITA system who have not yet been assigned supplier permissions or point allocations. The dashboard will provide meaningful metrics, onboarding guidance, and system information through a new API endpoint that returns data optimized for graph visualization and user engagement.

The solution extends the existing `routes/dashboard.py` module with a new endpoint specifically designed for users with zero suppliers and zero points, while maintaining consistency with the existing dashboard architecture.

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│   Frontend      │
│   Dashboard     │
└────────┬────────┘
         │ HTTP GET /v1.0/dashboard/new-user
         ▼
┌─────────────────┐
│  FastAPI Route  │
│  dashboard.py   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Database Layer │
│  SQLAlchemy ORM │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  SQLite/MySQL   │
│  Database       │
└─────────────────┘
```

### Component Interaction Flow

1. **Authentication Layer**: User authenticates via JWT token (existing `get_current_active_user` dependency)
2. **Route Handler**: New endpoint `/new-user` processes the request
3. **Data Aggregation**: Queries multiple tables to gather user-specific and system-wide metrics
4. **Caching Layer**: Implements Redis caching for system-wide metrics (5-minute TTL) and user-specific data (1-minute TTL)
5. **Response Formatting**: Returns JSON with time-series data formatted for graph rendering
6. **Audit Logging**: Logs dashboard access for security monitoring

## Components and Interfaces

### 1. New API Endpoint

**Endpoint**: `GET /v1.0/dashboard/new-user`

**Authentication**: Requires valid JWT token (any authenticated user)

**Access Control**: Available to all authenticated users (no admin restriction)

**Response Schema**:

```python
{
    "account_info": {
        "user_id": str,
        "username": str,
        "email": str,
        "account_status": str,  # "pending_activation", "active", "suspended"
        "created_at": str,  # ISO 8601 format
        "days_since_registration": int,
        "onboarding_progress": {
            "completion_percentage": int,  # 0-100
            "completed_steps": List[str],
            "pending_steps": List[Dict[str, Any]]  # includes action, description, estimated_time
        }
    },
    "user_resources": {
        "suppliers": {
            "active_count": int,  # Will be 0 for new users
            "total_available": int,
            "assigned_suppliers": List[str],  # Empty for new users
            "pending_assignment": bool
        },
        "points": {
            "current_balance": int,  # Will be 0 for new users
            "total_allocated": int,  # Will be 0 for new users
            "package_type": Optional[str],  # None for new users
            "pending_allocation": bool
        }
    },
    "platform_overview": {
        "total_users": int,
        "total_hotels": int,
        "total_mappings": int,
        "available_suppliers": List[Dict[str, Any]],  # name, description, hotel_count
        "available_packages": List[Dict[str, Any]]  # type, description, example_points
    },
    "activity_metrics": {
        "user_logins": {
            "total_count": int,
            "last_login": Optional[str],
            "time_series": List[Dict[str, Any]]  # 30-day daily data
        },
        "api_requests": {
            "total_count": int,  # Will be 0 for new users
            "time_series": List[Dict[str, Any]]  # 30-day daily data with zeros
        }
    },
    "platform_trends": {
        "user_registrations": {
            "title": str,
            "unit": str,
            "data_type": str,
            "time_series": List[Dict[str, Any]]  # 30-day daily data
        },
        "hotel_updates": {
            "title": str,
            "unit": str,
            "data_type": str,
            "time_series": List[Dict[str, Any]]  # 30-day daily data
        }
    },
    "recommendations": {
        "next_steps": List[Dict[str, Any]],  # priority, action, description, contact_info
        "estimated_activation_time": str
    },
    "metadata": {
        "timestamp": str,
        "cache_status": str,  # "cached" or "fresh"
        "data_freshness": Dict[str, str]  # component: last_updated timestamp
    }
}
```

### 2. Helper Functions

#### `get_user_account_info(db: Session, user: User) -> Dict`

- Retrieves user account details
- Calculates days since registration
- Determines account status based on suppliers and points

#### `calculate_onboarding_progress(user: User, db: Session) -> Dict`

- Checks completion of onboarding steps:
  - Account created ✓
  - Email verified (if applicable)
  - Supplier permissions assigned
  - Points allocated
  - First API request made
- Returns completion percentage and pending actions

#### `get_available_suppliers(db: Session) -> List[Dict]`

- Queries `SupplierSummary` table for all available suppliers
- Returns supplier names, hotel counts, and descriptions
- Cached for 5 minutes

#### `get_available_packages() -> List[Dict]`

- Returns static information about point package types
- Includes: admin_user_package, one_year_package, one_month_package, per_request_point, guest_point
- Provides example point allocations for each package

#### `get_user_login_time_series(db: Session, user_id: str, days: int = 30) -> List[Dict]`

- Queries `UserActivityLog` for login events
- Groups by date and counts logins per day
- Fills missing dates with zero values
- Returns chronologically sorted time-series data

#### `get_platform_registration_trends(db: Session, days: int = 30) -> List[Dict]`

- Queries `User` table for registration dates
- Groups by date and counts new registrations
- Fills missing dates with zero values
- Cached for 5 minutes

#### `get_hotel_update_trends(db: Session, days: int = 30) -> List[Dict]`

- Queries `Hotel` table for update timestamps
- Groups by date and counts updates
- Fills missing dates with zero values
- Cached for 5 minutes

#### `generate_recommendations(user: User, db: Session) -> Dict`

- Analyzes user's current state
- Generates prioritized list of next steps
- Provides contact information for admin support
- Estimates time to full activation

#### `fill_time_series_gaps(data: List[Dict], days: int) -> List[Dict]`

- Utility function to ensure continuous time-series data
- Fills missing dates with zero values
- Ensures consistent date format (YYYY-MM-DD)
- Sorts chronologically

### 3. Caching Strategy

**Redis Cache Keys**:

- `dashboard:new_user:system_metrics` - System-wide metrics (5-minute TTL)
- `dashboard:new_user:suppliers` - Available suppliers list (5-minute TTL)
- `dashboard:new_user:user:{user_id}` - User-specific data (1-minute TTL)

**Cache Implementation**:

```python
from fastapi_cache.decorator import cache

@cache(expire=300)  # 5 minutes for system metrics
async def get_cached_system_metrics(db: Session):
    # Implementation
    pass

@cache(expire=60)  # 1 minute for user data
async def get_cached_user_data(db: Session, user_id: str):
    # Implementation
    pass
```

## Data Models

### Existing Models Used

1. **User** (`models.User`)

   - Fields: id, username, email, role, created_at, is_active
   - Relationships: user_points, provider_permissions, activity_logs, sessions

2. **UserPoint** (`models.UserPoint`)

   - Fields: user_id, total_points, current_points, total_used_points
   - Used to check if user has points allocated

3. **UserProviderPermission** (`models.UserProviderPermission`)

   - Fields: user_id, provider_name
   - Used to check if user has supplier permissions

4. **UserActivityLog** (`models.UserActivityLog`)

   - Fields: user_id, action, created_at, details
   - Used for login tracking and activity time-series

5. **Hotel** (`models.Hotel`)

   - Fields: id, ittid, name, updated_at
   - Used for platform statistics

6. **ProviderMapping** (`models.ProviderMapping`)

   - Fields: id, ittid, provider_name
   - Used for mapping statistics

7. **SupplierSummary** (`models.SupplierSummary`)

   - Fields: provider_name, total_hotels, total_mappings, last_updated
   - Used for supplier information

8. **UserSession** (`models.UserSession`)
   - Fields: user_id, created_at, last_activity
   - Used for login tracking

### No New Models Required

All necessary data can be retrieved from existing database tables. No schema changes are needed.

## Error Handling

### Error Scenarios and Responses

1. **Unauthenticated Request**

   - Status Code: 401 Unauthorized
   - Response: `{"detail": "User authentication required"}`

2. **Database Connection Failure**

   - Status Code: 500 Internal Server Error
   - Response: `{"detail": "Database connection error"}`
   - Logging: Error logged with full traceback

3. **Missing Activity Log Table**

   - Graceful degradation: Return empty time-series with zeros
   - Log warning but continue processing
   - Set `data_available: false` in response

4. **Cache Connection Failure**

   - Fallback to direct database queries
   - Log warning but continue processing
   - Set `cache_status: "unavailable"` in response

5. **Query Timeout**
   - Status Code: 504 Gateway Timeout
   - Response: `{"detail": "Request timeout - please try again"}`
   - Timeout set to 30 seconds

### Error Handling Pattern

```python
try:
    # Main logic
    pass
except HTTPException:
    # Re-raise HTTP exceptions without modification
    raise
except OperationalError as e:
    # Database errors
    dashboard_logger.error(f"Database error: {e}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Database error occurred"
    )
except Exception as e:
    # Unexpected errors
    dashboard_logger.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred"
    )
```

## Testing Strategy

### Unit Tests

1. **Test User Account Info Retrieval**

   - Test with new user (0 suppliers, 0 points)
   - Test with partially activated user
   - Test with fully activated user

2. **Test Onboarding Progress Calculation**

   - Test 0% completion (just registered)
   - Test 50% completion (some steps done)
   - Test 100% completion (fully activated)

3. **Test Time-Series Data Generation**

   - Test with no data (should return zeros)
   - Test with partial data (should fill gaps)
   - Test with complete data
   - Test date sorting and formatting

4. **Test Recommendations Generation**

   - Test for user with no suppliers
   - Test for user with no points
   - Test for user with neither

5. **Test Cache Behavior**
   - Test cache hit scenario
   - Test cache miss scenario
   - Test cache expiration

### Integration Tests

1. **Test Complete Endpoint Response**

   - Test with authenticated new user
   - Verify all response fields present
   - Verify time-series data format
   - Verify data consistency

2. **Test Database Queries**

   - Test with empty database
   - Test with populated database
   - Test query performance (< 500ms)

3. **Test Error Scenarios**
   - Test with invalid token
   - Test with database unavailable
   - Test with cache unavailable

### Performance Tests

1. **Response Time**

   - Target: < 500ms for 95% of requests
   - Measure with cold cache
   - Measure with warm cache

2. **Concurrent Requests**

   - Test with 100 concurrent users
   - Verify no database connection pool exhaustion

3. **Cache Effectiveness**
   - Measure cache hit rate
   - Target: > 80% cache hit rate for system metrics

## Security Considerations

### Authentication and Authorization

- **JWT Token Required**: All requests must include valid JWT token
- **No Admin Restriction**: Unlike other dashboard endpoints, this is available to all authenticated users
- **User Isolation**: Users can only see their own account data
- **System Metrics**: Platform-wide statistics are anonymized and aggregated

### Audit Logging

All dashboard access attempts are logged with:

- User ID and username
- Timestamp
- IP address (from request headers)
- Response status

### Data Privacy

- **PII Protection**: Email addresses only shown for the requesting user
- **Aggregated Data**: Platform statistics are aggregated and anonymized
- **No Sensitive Data**: No password hashes, API keys, or tokens in responses

### Rate Limiting

- Apply existing rate limiting middleware
- Suggested limit: 60 requests per minute per user
- Prevents abuse and ensures fair resource usage

## Performance Optimization

### Caching Strategy

1. **System-Wide Metrics** (5-minute TTL)

   - Total users count
   - Total hotels count
   - Total mappings count
   - Available suppliers list
   - Platform trends time-series

2. **User-Specific Data** (1-minute TTL)
   - User account info
   - User activity time-series
   - User recommendations

### Database Query Optimization

1. **Use Indexes**

   - Ensure indexes on: `users.created_at`, `user_activity_logs.user_id`, `user_activity_logs.created_at`
   - Existing indexes should be sufficient

2. **Limit Result Sets**

   - Time-series queries limited to 30 days
   - Use `LIMIT` clauses where appropriate

3. **Batch Queries**

   - Combine related queries where possible
   - Use joins instead of multiple queries

4. **Connection Pooling**
   - Leverage existing SQLAlchemy connection pool
   - Pool size: 5, max overflow: 10

### Response Size Optimization

- Time-series data limited to 30 days (max 30 data points)
- Supplier list limited to essential fields
- Use gzip compression for responses (FastAPI default)

## Deployment Considerations

### Environment Variables

No new environment variables required. Uses existing:

- `DB_CONNECTION`: Database connection string
- `SECRET_KEY`: JWT secret key
- Redis connection (default: localhost:6379)

### Database Migrations

No database migrations required. Uses existing tables.

### Backward Compatibility

- New endpoint does not affect existing endpoints
- No breaking changes to existing API
- Fully backward compatible

### Monitoring

- Log all dashboard access attempts
- Monitor response times
- Track cache hit rates
- Alert on error rates > 1%

## Future Enhancements

1. **Personalized Recommendations**

   - ML-based recommendations based on user behavior
   - Industry-specific onboarding paths

2. **Interactive Tutorials**

   - Step-by-step guides for new users
   - Video tutorials and documentation links

3. **Gamification**

   - Achievement badges for completing onboarding steps
   - Progress rewards and incentives

4. **Real-Time Updates**

   - WebSocket support for live dashboard updates
   - Push notifications for important events

5. **Customizable Dashboard**

   - User preferences for dashboard layout
   - Configurable widgets and metrics

6. **Comparative Analytics**
   - Compare user's progress with similar users
   - Benchmark against industry averages
