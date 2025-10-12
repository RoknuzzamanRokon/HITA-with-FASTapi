"""
Redis cache configuration and utilities for user management system
"""

import redis
import json
import os
from typing import Any, Optional, Union
from datetime import datetime, timedelta
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class CacheConfig:
    """Redis cache configuration"""
    
    # Default cache settings
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
    
    # Cache TTL settings (in seconds)
    USER_STATS_TTL = 300  # 5 minutes
    USER_LIST_TTL = 60    # 1 minute
    USER_DETAILS_TTL = 180  # 3 minutes
    DASHBOARD_STATS_TTL = 600  # 10 minutes

class RedisCache:
    """Redis cache manager for user management system"""
    
    def __init__(self):
        self.redis_client = None
        self.is_available = False
        self._connect()
    
    def _connect(self):
        """Initialize Redis connection"""
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
            logger.info("Redis cache connected successfully")
            
        except Exception as e:
            logger.warning(f"Redis cache not available: {e}")
            self.is_available = False
            self.redis_client = None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.is_available:
            return None
            
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL"""
        if not self.is_available:
            return False
            
        try:
            serialized_value = json.dumps(value, default=str)
            self.redis_client.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.is_available:
            return False
            
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> bool:
        """Delete all keys matching pattern"""
        if not self.is_available:
            return False
            
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Cache delete pattern error for pattern {pattern}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.is_available:
            return False
            
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

# Global cache instance
cache = RedisCache()

def cache_key_builder(*args, **kwargs) -> str:
    """Build cache key from arguments"""
    key_parts = []
    
    # Add positional arguments
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        else:
            key_parts.append(str(hash(str(arg))))
    
    # Add keyword arguments
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (str, int, float, bool)):
            key_parts.append(f"{k}:{v}")
        else:
            key_parts.append(f"{k}:{hash(str(v))}")
    
    return ":".join(key_parts)

def cached(ttl: int = 300, key_prefix: str = ""):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            cache_key = f"{key_prefix}:{func.__name__}:{cache_key_builder(*args, **kwargs)}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(cache_key, result, ttl)
                logger.debug(f"Cache set for key: {cache_key}")
            
            return result
        return wrapper
    return decorator

def invalidate_cache_pattern(pattern: str):
    """Invalidate all cache keys matching pattern"""
    cache.delete_pattern(pattern)
    logger.info(f"Invalidated cache pattern: {pattern}")

# Cache key patterns for user management
class CacheKeys:
    """Cache key patterns for user management"""
    
    USER_STATS = "user_stats"
    USER_LIST = "user_list"
    USER_DETAILS = "user_details"
    DASHBOARD_STATS = "dashboard_stats"
    
    @staticmethod
    def user_list_key(page: int, limit: int, filters: dict) -> str:
        """Generate cache key for user list"""
        filter_hash = hash(str(sorted(filters.items())))
        return f"{CacheKeys.USER_LIST}:page_{page}:limit_{limit}:filters_{filter_hash}"
    
    @staticmethod
    def user_details_key(user_id: str) -> str:
        """Generate cache key for user details"""
        return f"{CacheKeys.USER_DETAILS}:{user_id}"
    
    @staticmethod
    def invalidate_user_caches(user_id: str = None):
        """Invalidate user-related caches"""
        patterns = [
            f"{CacheKeys.USER_STATS}*",
            f"{CacheKeys.USER_LIST}*",
            f"{CacheKeys.DASHBOARD_STATS}*"
        ]
        
        if user_id:
            patterns.append(f"{CacheKeys.USER_DETAILS}:{user_id}")
        else:
            patterns.append(f"{CacheKeys.USER_DETAILS}*")
        
        for pattern in patterns:
            invalidate_cache_pattern(pattern)