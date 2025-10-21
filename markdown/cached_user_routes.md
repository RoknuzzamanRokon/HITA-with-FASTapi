# Cached User Routes Documentation

## Overview

The Cached User Routes system provides high-performance user management endpoints with intelligent caching strategies. It combines comprehensive user data access with Redis-based caching to optimize database queries and improve response times, especially for administrative operations.

## Architecture

### Core Components

- **Cached User Routes**: FastAPI endpoints with integrated caching
- **Cached User Service**: Service layer with intelligent cache management
- **Role-Based Caching**: Different cache strategies for different user roles
- **Audit Integration**: Comprehensive activity logging
- **Cache Invalidation**: Automatic and manual cache management

### Route Prefix

```
/v1.0/users
```

### Security Model

- **Super User**: Full access to all endpoints and cache management
- **Admin User**: Access to user data and statistics
- **General User**: No access to administrative endpoints

## User Management Endpoints

### Get Paginated User List

#### Endpoint

```http
GET /v1.0/users/list
Authorization: Bearer <admin_token>
```

#### Parameters

| Parameter    | Type    | Default      | Description                    |
| ------------ | ------- | ------------ | ------------------------------ |
| `page`       | int     | 1            | Page number (≥1)               |
| `limit`      | int     | 25           | Items per page (1-100)         |
| `search`     | string  | null         | Search term for username/email |
| `role`       | string  | null         | Filter by user role            |
| `is_active`  | boolean | null         | Filter by active status        |
| `sort_by`    | string  | "created_at" | Sort field                     |
| `sort_order` | string  | "desc"       | Sort order (asc/desc)          |

#### Example Request

```http
GET /v1.0/users/list?page=1&limit=25&search=john&role=general_user&is_active=true&sort_by=username&sort_order=asc
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Response

```json
{
  "success": true,
  "data": {
    "users": [
      {
        "id": "5779356081",
        "username": "john_doe",
        "email": "john@example.com",
        "role": "general_user",
        "is_active": true,
        "created_at": "2024-12-17T10:30:00Z",
        "updated_at": "2024-12-17T15:45:00Z",
        "created_by": "admin_user",
        "point_balance": 150,
        "total_points": 300,
        "paid_status": "Paid",
        "total_requests": 25,
        "activity_status": "Active",
        "active_suppliers": ["hotelbeds", "tbo"],
        "last_login": "2024-12-17T14:20:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 25,
      "total": 150,
      "total_pages": 6,
      "has_next": true,
      "has_prev": false
    },
    "statistics": {
      "total_users": 150,
      "super_users": 2,
      "admin_users": 5,
      "general_users": 143,
      "active_users": 140,
      "inactive_users": 10
    },
    "cache_info": {
      "cached": true,
      "cache_key": "superadmin_user_list:page_1:limit_25:filters_123456",
      "retrieved_at": "2024-12-17T15:30:00Z"
    }
  }
}
```

### Get User Statistics

#### Endpoint

```http
GET /v1.0/users/statistics
Authorization: Bearer <admin_token>
```

#### Response

```json
{
  "success": true,
  "data": {
    "total_users": 150,
    "super_users": 2,
    "admin_users": 5,
    "general_users": 143,
    "active_users": 140,
    "inactive_users": 10,
    "total_points_distributed": 45000,
    "current_points_balance": 12500,
    "recent_signups": 8,
    "last_updated": "2024-12-17T15:30:00Z"
  }
}
```

### Get User Details

#### Endpoint

```http
GET /v1.0/users/{user_id}/details
Authorization: Bearer <admin_token>
```

#### Response

```json
{
  "success": true,
  "data": {
    "id": "5779356081",
    "username": "john_doe",
    "email": "john@example.com",
    "role": "general_user",
    "is_active": true,
    "created_at": "2024-12-17T10:30:00Z",
    "updated_at": "2024-12-17T15:45:00Z",
    "created_by": "admin_user",
    "point_balance": 150,
    "total_points": 300,
    "used_points": 150,
    "provider_permissions": [
      {
        "provider_name": "hotelbeds",
        "id": "perm_123"
      }
    ],
    "recent_transactions": [
      {
        "id": "trans_456",
        "points": 50,
        "transaction_type": "transfer",
        "created_at": "2024-12-17T14:00:00Z",
        "giver_id": "admin_001",
        "receiver_id": "5779356081"
      }
    ],
    "recent_activities": [
      {
        "id": "act_789",
        "action": "login_success",
        "details": { "ip": "192.168.1.100" },
        "created_at": "2024-12-17T14:20:00Z",
        "ip_address": "192.168.1.100"
      }
    ],
    "active_sessions": 2,
    "last_activity": "2024-12-17T15:30:00Z"
  }
}
```

### Get Dashboard Statistics

#### Endpoint

```http
GET /v1.0/users/dashboard/statistics
Authorization: Bearer <admin_token>
```

#### Response

```json
{
  "success": true,
  "data": {
    "total_users": 150,
    "super_users": 2,
    "admin_users": 5,
    "general_users": 143,
    "active_users": 140,
    "inactive_users": 10,
    "total_points_distributed": 45000,
    "current_points_balance": 12500,
    "recent_signups": 8,
    "point_distribution": [
      {
        "role": "super_user",
        "total_points": 5000,
        "user_count": 2
      },
      {
        "role": "admin_user",
        "total_points": 15000,
        "user_count": 5
      },
      {
        "role": "general_user",
        "total_points": 25000,
        "user_count": 143
      }
    ],
    "activity_trends": [
      {
        "date": "2024-12-17",
        "transaction_count": 45,
        "points_transferred": 2250
      }
    ],
    "top_active_users": [
      {
        "id": "5779356081",
        "username": "john_doe",
        "email": "john@example.com",
        "transaction_count": 25
      }
    ]
  }
}
```

## Cache Management Endpoints

### Invalidate User Cache (Admin Only)

#### Endpoint

```http
POST /v1.0/users/{user_id}/invalidate_cache
Authorization: Bearer <admin_token>
```

#### Response

```json
{
  "success": true,
  "message": "Cache invalidated for user 5779356081"
}
```

### Warm User Cache (Super User Only)

#### Endpoint

```http
POST /v1.0/users/cache/warm
Authorization: Bearer <super_user_token>
```

#### Response

```json
{
  "success": true,
  "message": "Cache warming completed successfully",
  "warmed_at": "2024-12-17T15:30:00Z"
}
```

### Get Cache Status (Super User Only)

#### Endpoint

```http
GET /v1.0/users/cache/status
Authorization: Bearer <super_user_token>
```

#### Response

```json
{
  "success": true,
  "data": {
    "cache_available": true,
    "cache_keys_status": {
      "superadmin_user_list:page_1:limit_25:filters_0": {
        "exists": true,
        "has_data": true
      },
      "user_stats:get_user_statistics:": {
        "exists": true,
        "has_data": true
      },
      "dashboard_stats:get_dashboard_statistics:": {
        "exists": true,
        "has_data": true
      }
    },
    "superadmin_cache_ready": true
  },
  "checked_at": "2024-12-17T15:30:00Z"
}
```

### Cache Health Check

#### Endpoint

```http
GET /v1.0/users/health/cache
```

#### Response

```json
{
  "success": true,
  "cache_status": {
    "available": true,
    "operations": {
      "set": true,
      "get": true,
      "delete": true
    }
  }
}
```

## Caching Strategy

### Cache Types and TTL

| Cache Type              | TTL        | Usage                       |
| ----------------------- | ---------- | --------------------------- |
| User Statistics         | 5 minutes  | Frequently accessed stats   |
| User List (Regular)     | 1 minute   | Standard user lists         |
| User List (Super Admin) | 15 minutes | Enhanced caching for admins |
| User Details            | 3 minutes  | Individual user information |
| Dashboard Statistics    | 10 minutes | Complex aggregated data     |

### Cache Key Patterns

#### User List Keys

```
# Regular admin users
user_list:page_1:limit_25:filters_123456

# Super admin users (enhanced caching)
superadmin_user_list:page_1:limit_25:filters_123456
```

#### User Details Keys

```
user_details:5779356081
```

#### Statistics Keys

```
user_stats:get_user_statistics:
dashboard_stats:get_dashboard_statistics:
```

### Enhanced Super Admin Caching

Super admin users receive enhanced caching with:

- **Longer TTL**: 15 minutes vs 1 minute for regular admins
- **Dedicated Cache Keys**: Separate cache namespace
- **Proactive Warming**: Automatic cache population
- **Extended Coverage**: Multiple pages pre-cached

```python
# Enhanced cache key for super admin
if current_user_role == 'super_user':
    cache_key = CacheKeys.superadmin_user_list_key(page, limit, filters)
    cache_ttl = CacheConfig.SUPERADMIN_USER_LIST_TTL  # 15 minutes
else:
    cache_key = CacheKeys.user_list_key(page, limit, filters)
    cache_ttl = CacheConfig.USER_LIST_TTL  # 1 minute
```

## Service Layer Implementation

### Cached User Service

#### Core Methods

```python
class CachedUserService:
    def get_user_statistics(self) -> Dict[str, Any]
    def get_users_paginated(self, **kwargs) -> Dict[str, Any]
    def get_user_details(self, user_id: str) -> Optional[Dict[str, Any]]
    def get_dashboard_statistics(self) -> Dict[str, Any]
    def invalidate_user_caches(self, user_id: str = None)
    def warm_cache(self, for_superadmin: bool = True)
    def get_cache_status(self) -> Dict[str, Any]
```

#### Cache Decorator Usage

```python
@cached(ttl=CacheConfig.USER_STATS_TTL, key_prefix=CacheKeys.USER_STATS)
def get_user_statistics(self) -> Dict[str, Any]:
    """Get user statistics with caching"""
    # Database query implementation
```

### Data Enrichment

Each user record includes:

- **Basic Information**: ID, username, email, role, status
- **Point Information**: Current balance, total points, used points
- **Activity Status**: Recent activity, transaction count
- **Provider Permissions**: Active supplier integrations
- **Session Information**: Active sessions, last login
- **Audit Trail**: Recent activities and transactions

## Security and Audit

### Access Control

- **Role-Based Access**: Different endpoints for different roles
- **Token Validation**: All endpoints require valid JWT tokens
- **Permission Checks**: Explicit role verification on each endpoint

### Audit Logging

```python
# Automatic audit logging for all operations
audit_logger.log_activity(
    activity_type=ActivityType.API_ACCESS,
    user_id=current_user.id,
    details={
        "endpoint": "/v1.0/users/list",
        "action": "view_user_list",
        "page": page,
        "limit": limit,
        "search": search,
        "role_filter": role
    },
    security_level=SecurityLevel.MEDIUM,
    success=True
)
```

### Security Features

- **Input Validation**: Query parameter validation and sanitization
- **Rate Limiting**: Implicit through caching
- **Error Handling**: Secure error responses without data leakage
- **Logging**: Comprehensive operation logging

## Performance Optimization

### Cache Hit Optimization

- **Intelligent Key Generation**: Consistent cache key patterns
- **Filter-Based Caching**: Cache keys include filter parameters
- **Role-Based Strategies**: Different caching for different user roles
- **Proactive Warming**: Pre-populate frequently accessed data

### Database Query Optimization

- **Efficient Joins**: Optimized database queries with proper joins
- **Pagination**: Limit data transfer with proper pagination
- **Selective Loading**: Load only required data fields
- **Aggregation**: Use database aggregation for statistics

### Memory Management

- **TTL Strategy**: Appropriate cache expiration times
- **Selective Caching**: Cache only valuable data
- **Cache Size Monitoring**: Track cache memory usage
- **Automatic Cleanup**: Expired cache removal

## Error Handling

### Common Error Scenarios

#### Access Denied

```json
{
  "detail": "Access denied. Only super users and admin users can view user list."
}
```

#### User Not Found

```json
{
  "detail": "User with ID 5779356081 not found"
}
```

#### Cache Operation Failed

```json
{
  "success": false,
  "error": "Cache operation failed: Redis connection timeout",
  "cache_status": {
    "available": false,
    "operations": {
      "set": false,
      "get": false,
      "delete": false
    }
  }
}
```

### Graceful Degradation

- **Cache Unavailable**: Fall back to direct database queries
- **Partial Cache Failure**: Continue operation with reduced performance
- **Database Errors**: Proper error handling and user feedback
- **Timeout Handling**: Reasonable timeout limits for operations

## Monitoring and Metrics

### Performance Metrics

- **Cache Hit Rate**: Percentage of cache hits vs database queries
- **Response Times**: Endpoint response time monitoring
- **Database Load**: Query count and execution time
- **Memory Usage**: Cache memory consumption

### Operational Metrics

- **User Activity**: Active user counts and patterns
- **API Usage**: Endpoint usage statistics
- **Error Rates**: Error frequency and types
- **Cache Effectiveness**: Cache performance analysis

### Logging

```python
# Cache hit logging
logger.info(f"🚀 Cache hit for superadmin user list: {cache_key}")

# Cache miss logging
logger.info(f"💾 Fetching user list from database for caching: page={page}")

# Cache warming logging
logger.info("🔥 Warming superadmin cache...")
```

## Best Practices

### Caching Strategy

1. **Cache Expensive Queries**: Focus on database-intensive operations
2. **Role-Based Optimization**: Different strategies for different user types
3. **Proactive Warming**: Pre-populate frequently accessed data
4. **Intelligent Invalidation**: Clear relevant caches on data changes
5. **Monitor Performance**: Track cache effectiveness and adjust TTL

### Development Guidelines

1. **Consistent Key Patterns**: Use standardized cache key formats
2. **Error Handling**: Always handle cache failures gracefully
3. **Security First**: Validate permissions before cache operations
4. **Audit Everything**: Log all administrative operations
5. **Test Thoroughly**: Test both cache hit and miss scenarios

### Operational Guidelines

1. **Monitor Cache Health**: Regular cache status checks
2. **Capacity Planning**: Monitor memory usage and growth
3. **Performance Tuning**: Adjust TTL based on usage patterns
4. **Regular Maintenance**: Periodic cache cleanup and optimization
5. **Documentation**: Keep cache strategies well documented
