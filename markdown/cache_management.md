# Cache Management Documentation

## Overview

The ITT Hotel API (HITA) implements a comprehensive Redis-based caching system designed to optimize performance, reduce database load, and provide efficient data access patterns. The cache management system includes automatic invalidation, cache warming, monitoring, and administrative controls.

## Architecture

### Core Components

- **Redis Cache**: Primary caching backend with connection pooling
- **Cache Configuration**: Centralized configuration and TTL management
- **Cache Invalidation Middleware**: Automatic cache invalidation on data changes
- **Cache Warmup Service**: Proactive cache population
- **Cache Management API**: Administrative endpoints for cache control
- **Cached Services**: Service layer with integrated caching

### Cache Configuration

```python
class CacheConfig:
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

    # TTL Settings (seconds)
    USER_STATS_TTL = 300        # 5 minutes
    USER_LIST_TTL = 60          # 1 minute
    USER_DETAILS_TTL = 180      # 3 minutes
    DASHBOARD_STATS_TTL = 600   # 10 minutes
    SUPERADMIN_USER_LIST_TTL = 900  # 15 minutes
```

## Cache Types and Keys

### Cache Key Patterns

- **User Statistics**: `user_stats:*`
- **User Lists**: `user_list:*`
- **User Details**: `user_details:{user_id}`
- **Dashboard Statistics**: `dashboard_stats:*`
- **Superadmin User Lists**: `superadmin_user_list:*`

### TTL (Time To Live) Strategy

| Cache Type       | TTL        | Reason                                    |
| ---------------- | ---------- | ----------------------------------------- |
| User Stats       | 5 minutes  | Moderate update frequency                 |
| User Lists       | 1 minute   | Frequently changing data                  |
| User Details     | 3 minutes  | Balance between freshness and performance |
| Dashboard Stats  | 10 minutes | Expensive queries, less frequent updates  |
| Superadmin Lists | 15 minutes | Enhanced caching for admin operations     |

## Management Endpoints

### Health Monitoring

#### Basic Health Check

```http
GET /v1.0/cache/health
```

**Response:**

```json
{
  "success": true,
  "cache_info": {
    "status": "available",
    "redis_version": "7.0.5",
    "used_memory": "2.5M",
    "connected_clients": 3,
    "hit_rate": 85.2
  }
}
```

#### Detailed Health Check

```http
GET /v1.0/cache/health/detailed
```

**Response:**

```json
{
  "success": true,
  "timestamp": "2024-12-17T15:30:00Z",
  "cache_info": {
    "status": "available",
    "redis_version": "7.0.5",
    "used_memory": "2.5M",
    "connected_clients": 3,
    "hit_rate": 85.2
  },
  "detailed_statistics": {
    "key_counts": {
      "user_stats_keys": 45,
      "user_list_keys": 12,
      "user_details_keys": 234,
      "dashboard_stats_keys": 8,
      "total_keys": 299
    },
    "memory_usage": {
      "used_memory": "2.5M",
      "used_memory_peak": "3.1M",
      "memory_fragmentation_ratio": 1.15
    },
    "connections": {
      "connected_clients": 3,
      "total_connections_received": 1247,
      "uptime_in_seconds": 86400
    },
    "performance": {
      "keyspace_hits": 8542,
      "keyspace_misses": 1458,
      "hit_rate": 85.42
    },
    "redis_version": "7.0.5",
    "redis_mode": "standalone"
  }
}
```

### Cache Operations

#### Clear All Caches (Admin Only)

```http
POST /v1.0/cache/clear
Authorization: Bearer <admin_token>
```

**Response:**

```json
{
  "success": true,
  "message": "All user caches cleared successfully"
}
```

#### Clear User-Specific Cache (Admin Only)

```http
POST /v1.0/cache/clear/user/{user_id}
Authorization: Bearer <admin_token>
```

**Response:**

```json
{
  "success": true,
  "message": "Cache cleared for user 5779356081"
}
```

#### Warm Up Caches (Admin Only)

```http
POST /v1.0/cache/warm
Authorization: Bearer <admin_token>
```

**Response:**

```json
{
  "success": true,
  "message": "Essential caches warmed successfully"
}
```

#### Get Cache Statistics (Admin Only)

```http
GET /v1.0/cache/stats
Authorization: Bearer <admin_token>
```

**Response:**

```json
{
  "success": true,
  "cache_info": {
    "status": "available",
    "redis_version": "7.0.5",
    "hit_rate": 85.2
  },
  "key_counts": {
    "user_stats_keys": 45,
    "user_list_keys": 12,
    "user_details_keys": 234,
    "dashboard_stats_keys": 8,
    "total_keys": 299
  }
}
```

#### Test Cache Operations

```http
GET /v1.0/cache/test
```

**Response:**

```json
{
  "success": true,
  "test_results": {
    "cache_available": true,
    "set_operation": true,
    "get_operation": true,
    "exists_operation": true,
    "delete_operation": true,
    "get_after_delete": true
  }
}
```

## Cache Invalidation System

### Automatic Invalidation Middleware

The system includes middleware that automatically invalidates relevant caches when data changes occur.

#### Invalidation Patterns

```python
INVALIDATION_PATTERNS = {
    # User CRUD operations
    r'/v1\.0/user/create.*': ['user_stats', 'user_list', 'dashboard_stats'],
    r'/v1\.0/user/update.*': ['user_stats', 'user_list', 'dashboard_stats', 'user_details'],
    r'/v1\.0/user/delete.*': ['user_stats', 'user_list', 'dashboard_stats', 'user_details'],
    r'/v1\.0/user/.+/activate': ['user_stats', 'user_list', 'dashboard_stats', 'user_details'],

    # Point operations
    r'/v1\.0/points/.*': ['user_stats', 'user_list', 'dashboard_stats', 'user_details'],

    # Permission operations
    r'/v1\.0/permissions/.*': ['user_details'],
}
```

#### Triggering Methods

Cache invalidation is triggered by:

- `POST` - Create operations
- `PUT` - Update operations
- `PATCH` - Partial update operations
- `DELETE` - Delete operations

### Manual Invalidation

```python
# Invalidate specific user caches
CacheKeys.invalidate_user_caches(user_id="5779356081")

# Invalidate all user caches
CacheKeys.invalidate_user_caches()

# Invalidate by pattern
invalidate_cache_pattern("user_stats*")
```

## Cache Warmup Service

### Essential Cache Warmup

```python
class CacheWarmupService:
    @staticmethod
    async def warm_essential_caches():
        """Warm up essential caches on application startup"""

        # Initialize cached services
        cached_service = CachedUserService(db)

        # Warm up caches
        cached_service.warm_cache()
```

### Scheduled Cache Refresh

```python
@staticmethod
async def schedule_cache_refresh():
    """Schedule periodic cache refresh"""

    # Refresh expensive queries
    cached_service.get_dashboard_statistics()
    cached_service.get_user_statistics()
```

## Caching Decorator

### Usage Example

```python
@cached(ttl=300, key_prefix="user_service")
def get_user_details(user_id: str):
    """Get user details with caching"""
    return database_query_for_user(user_id)

# Cache key will be: "user_service:get_user_details:user_id:5779356081"
```

### Cache Key Builder

```python
def cache_key_builder(*args, **kwargs) -> str:
    """Build cache key from arguments"""
    key_parts = []

    # Add positional arguments
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        else:
            key_parts.append(str(hash(str(arg))))

    # Add keyword arguments (sorted for consistency)
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}:{v}")

    return ":".join(key_parts)
```

## Redis Cache Manager

### Core Operations

```python
class RedisCache:
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL"""

    def delete(self, key: str) -> bool:
        """Delete key from cache"""

    def delete_pattern(self, pattern: str) -> bool:
        """Delete all keys matching pattern"""

    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
```

### Connection Management

```python
def _connect(self):
    """Initialize Redis connection with retry logic"""
    try:
        self.redis_client = redis.Redis(
            host=CacheConfig.REDIS_HOST,
            port=CacheConfig.REDIS_PORT,
            db=CacheConfig.REDIS_DB,
            password=CacheConfig.REDIS_PASSWORD,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True
        )

        # Test connection
        self.redis_client.ping()
        self.is_available = True

    except Exception as e:
        logger.warning(f"Redis cache not available: {e}")
        self.is_available = False
```

## Performance Monitoring

### Key Metrics

- **Hit Rate**: Percentage of cache hits vs total requests
- **Memory Usage**: Current and peak memory consumption
- **Key Counts**: Number of keys by type
- **Connection Stats**: Active connections and total processed
- **Performance Stats**: Keyspace hits and misses

### Monitoring Dashboard

```python
def get_cache_info():
    """Get comprehensive cache information"""
    return {
        'status': 'available',
        'redis_version': '7.0.5',
        'used_memory': '2.5M',
        'connected_clients': 3,
        'total_commands_processed': 15420,
        'keyspace_hits': 8542,
        'keyspace_misses': 1458,
        'hit_rate': 85.42
    }
```

## Error Handling and Fallback

### Graceful Degradation

```python
def get(self, key: str) -> Optional[Any]:
    """Get value from cache with error handling"""
    if not self.is_available:
        return None

    try:
        value = self.redis_client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.error(f"Cache get error for key {key}: {e}")
        return None  # Fallback to database query
```

### Connection Recovery

- Automatic reconnection attempts
- Circuit breaker pattern for failed connections
- Fallback to direct database queries when cache unavailable
- Health check monitoring for connection status

## Security Considerations

### Access Control

- **Admin-Only Operations**: Cache clearing, statistics, and warming
- **Authentication Required**: All management endpoints require valid tokens
- **Role-Based Access**: Different access levels for different operations

### Data Protection

- **Sensitive Data Handling**: Passwords and secrets are never cached
- **Data Serialization**: Safe JSON serialization with error handling
- **TTL Enforcement**: Automatic expiration of cached data

## Best Practices

### Caching Strategy

1. **Cache Expensive Queries**: Focus on database-intensive operations
2. **Appropriate TTL**: Balance between freshness and performance
3. **Cache Invalidation**: Immediate invalidation on data changes
4. **Key Naming**: Consistent and descriptive key patterns
5. **Error Handling**: Graceful fallback when cache unavailable

### Performance Optimization

1. **Connection Pooling**: Efficient Redis connection management
2. **Batch Operations**: Group cache operations when possible
3. **Memory Management**: Monitor and optimize memory usage
4. **Hit Rate Monitoring**: Track cache effectiveness

### Operational Guidelines

1. **Regular Monitoring**: Track cache performance metrics
2. **Capacity Planning**: Monitor memory usage and key counts
3. **Backup Strategy**: Redis persistence configuration
4. **Alerting**: Set up alerts for cache failures

## Troubleshooting

### Common Issues

#### Cache Unavailable

```json
{
  "success": false,
  "error": "Redis cache not available",
  "cache_available": false
}
```

**Solutions:**

- Check Redis server status
- Verify connection configuration
- Review network connectivity
- Check authentication credentials

#### High Memory Usage

**Symptoms:**

- Slow cache operations
- Memory fragmentation warnings
- Connection timeouts

**Solutions:**

- Review TTL settings
- Clear unnecessary caches
- Optimize data serialization
- Consider Redis memory optimization

#### Low Hit Rate

**Symptoms:**

- Hit rate below 70%
- Frequent cache misses
- Poor performance

**Solutions:**

- Review cache invalidation patterns
- Adjust TTL values
- Optimize cache key strategies
- Analyze access patterns

### Diagnostic Commands

```bash
# Check Redis status
redis-cli ping

# Monitor Redis operations
redis-cli monitor

# Get Redis info
redis-cli info

# Check memory usage
redis-cli info memory

# List all keys
redis-cli keys "*"
```

## Configuration Examples

### Development Environment

```python
# Development settings
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None

# Shorter TTL for development
USER_STATS_TTL = 60      # 1 minute
USER_LIST_TTL = 30       # 30 seconds
DASHBOARD_STATS_TTL = 120 # 2 minutes
```

### Production Environment

```python
# Production settings
REDIS_HOST = 'redis-cluster.example.com'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = 'secure-password'

# Longer TTL for production
USER_STATS_TTL = 600     # 10 minutes
USER_LIST_TTL = 300      # 5 minutes
DASHBOARD_STATS_TTL = 1800 # 30 minutes
```

### Docker Configuration

```yaml
version: "3.8"
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    environment:
      - REDIS_PASSWORD=your-secure-password

volumes:
  redis_data:
```

## Integration Examples

### Service Layer Integration

```python
class CachedUserService:
    def __init__(self, db: Session):
        self.db = db
        self.cache = cache

    @cached(ttl=CacheConfig.USER_DETAILS_TTL, key_prefix="user_service")
    def get_user_by_id(self, user_id: str):
        """Get user with caching"""
        return self.db.query(User).filter(User.id == user_id).first()

    def update_user(self, user_id: str, updates: dict):
        """Update user and invalidate cache"""
        # Update database
        user = self.db.query(User).filter(User.id == user_id).first()
        for key, value in updates.items():
            setattr(user, key, value)
        self.db.commit()

        # Invalidate related caches
        CacheKeys.invalidate_user_caches(user_id)

        return user
```

### Middleware Integration

```python
# Add cache invalidation middleware
app.add_middleware(CacheInvalidationMiddleware)

# Add cache warmup on startup
@app.on_event("startup")
async def startup_event():
    await CacheWarmupService.warm_essential_caches()
```
