# User Management Caching System

This document describes the caching implementation for the user management system, designed to improve performance and reduce database load.

## Overview

The caching system uses Redis as the backend cache store and provides:

- Automatic caching of frequently accessed data
- Cache invalidation on data changes
- Cache warming for essential data
- Performance monitoring and management

## Architecture

### Components

1. **Cache Configuration** (`cache_config.py`)

   - Redis connection management
   - Cache key builders and utilities
   - Caching decorators

2. **Cached User Service** (`services/cached_user_service.py`)

   - Enhanced user service with caching
   - Cached methods for user statistics, lists, and details
   - Cache warming functionality

3. **Cache Invalidation Middleware** (`middleware/cache_invalidation.py`)

   - Automatic cache invalidation on data changes
   - URL pattern-based invalidation rules
   - Cache warming service

4. **Cache Management Routes** (`routes/cache_management.py`)
   - Admin endpoints for cache control
   - Health checks and statistics
   - Manual cache operations

## Configuration

### Environment Variables

Add these to your `.env` file:

```env
# Redis Cache Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
```

### Cache TTL Settings

Default TTL (Time To Live) values:

- User Statistics: 5 minutes (300 seconds)
- User Lists: 1 minute (60 seconds)
- User Details: 3 minutes (180 seconds)
- Dashboard Statistics: 10 minutes (600 seconds)

## Usage

### Basic Caching

```python
from cache_config import cached

@cached(ttl=300, key_prefix="user_data")
def get_user_data(user_id):
    # This function result will be cached for 5 minutes
    return expensive_database_query(user_id)
```

### Using Cached User Service

```python
from services.cached_user_service import CachedUserService

# Initialize service
cached_service = CachedUserService(db)

# Get cached user statistics
stats = cached_service.get_user_statistics()

# Get cached user list
users = cached_service.get_users_paginated(page=1, limit=25)

# Get cached user details
user_details = cached_service.get_user_details(user_id)
```

### Manual Cache Management

```python
from cache_config import cache, CacheKeys

# Set cache value
cache.set("my_key", {"data": "value"}, ttl=300)

# Get cache value
value = cache.get("my_key")

# Delete cache key
cache.delete("my_key")

# Invalidate user caches
CacheKeys.invalidate_user_caches(user_id)
```

## Cache Keys

The system uses structured cache keys:

- `user_stats:*` - User statistics
- `user_list:*` - Paginated user lists
- `user_details:{user_id}` - Individual user details
- `dashboard_stats:*` - Dashboard statistics

## Cache Invalidation

### Automatic Invalidation

The middleware automatically invalidates caches when:

- Users are created, updated, or deleted
- User status changes (activate/deactivate)
- Point transactions occur
- Permission changes are made

### Manual Invalidation

Admin users can manually invalidate caches through:

- API endpoints (`/cache/clear`, `/cache/clear/user/{user_id}`)
- Service methods (`invalidate_user_caches()`)

## Performance Benefits

### Expected Performance Improvements

1. **User Statistics**: 80-90% faster (from ~200ms to ~20ms)
2. **User Lists**: 70-80% faster (from ~150ms to ~30ms)
3. **User Details**: 60-70% faster (from ~100ms to ~30ms)
4. **Dashboard Statistics**: 85-95% faster (from ~500ms to ~25ms)

### Database Load Reduction

- Reduces database queries by 60-80% for read operations
- Eliminates expensive aggregation queries during peak usage
- Improves overall system responsiveness

## Monitoring

### Health Checks

```bash
# Check cache health
GET /cache/health

# Get cache statistics
GET /cache/stats

# Test cache operations
GET /cache/test
```

### Cache Statistics

Monitor cache performance through:

- Hit/miss ratios
- Memory usage
- Key counts
- Response times

## Cache Warming

### Automatic Warming

Essential caches are warmed on application startup:

- User statistics
- Dashboard statistics
- First page of users

### Manual Warming

```bash
# Warm essential caches
POST /cache/warm
```

### Scheduled Warming

Set up periodic cache refresh (recommended every 5-10 minutes):

```python
from middleware.cache_invalidation import CacheWarmupService

# Schedule this to run periodically
await CacheWarmupService.schedule_cache_refresh()
```

## Fallback Behavior

The system gracefully handles cache unavailability:

- Falls back to database queries if Redis is unavailable
- Logs warnings but continues normal operation
- No impact on application functionality

## Best Practices

### Do's

- Use appropriate TTL values for different data types
- Monitor cache hit ratios
- Warm caches for frequently accessed data
- Invalidate caches when data changes

### Don'ts

- Don't cache user-sensitive data without proper security
- Don't set TTL too high for frequently changing data
- Don't ignore cache health monitoring
- Don't cache large objects unnecessarily

## Troubleshooting

### Common Issues

1. **Cache Not Working**

   - Check Redis connection
   - Verify environment variables
   - Check Redis server status

2. **Stale Data**

   - Verify cache invalidation rules
   - Check TTL settings
   - Manual cache clearing if needed

3. **Performance Issues**
   - Monitor cache hit ratios
   - Adjust TTL values
   - Check Redis memory usage

### Debug Commands

```python
# Test cache connection
from cache_config import cache
print(f"Cache available: {cache.is_available}")

# Check cache keys
keys = cache.redis_client.keys("*")
print(f"Cache keys: {keys}")

# Get cache info
info = cache.redis_client.info()
print(f"Cache info: {info}")
```

## Testing

Run the cache test suite:

```bash
cd backend
pipenv run python test_cache.py
```

This will test:

- Basic cache operations
- Cached decorators
- User service caching
- Cache warming
- Performance improvements

## Future Enhancements

Potential improvements:

- Distributed caching for multi-instance deployments
- Cache compression for large objects
- Advanced cache warming strategies
- Real-time cache metrics dashboard
- Automatic cache optimization based on usage patterns
