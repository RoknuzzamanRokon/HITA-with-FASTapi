"""
Cache invalidation middleware for automatic cache management
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
import logging
import re
from typing import Set

from cache_config import CacheKeys

logger = logging.getLogger(__name__)

class CacheInvalidationMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically invalidate caches on data changes"""
    
    # URL patterns that should trigger cache invalidation
    INVALIDATION_PATTERNS = {
        # User CRUD operations
        r'/v1\.0/user/create.*': ['user_stats', 'user_list', 'dashboard_stats'],
        r'/v1\.0/user/update.*': ['user_stats', 'user_list', 'dashboard_stats', 'user_details'],
        r'/v1\.0/user/delete.*': ['user_stats', 'user_list', 'dashboard_stats', 'user_details'],
        r'/v1\.0/user/.+/activate': ['user_stats', 'user_list', 'dashboard_stats', 'user_details'],
        r'/v1\.0/user/.+/deactivate': ['user_stats', 'user_list', 'dashboard_stats', 'user_details'],
        
        # Point operations
        r'/v1\.0/points/.*': ['user_stats', 'user_list', 'dashboard_stats', 'user_details'],
        
        # Permission operations
        r'/v1\.0/permissions/.*': ['user_details'],
    }
    
    # HTTP methods that should trigger invalidation
    INVALIDATION_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
    
    async def dispatch(self, request: Request, call_next):
        """Process request and invalidate caches if needed"""
        
        response = await call_next(request)
        
        # Only invalidate on successful operations
        if (response.status_code < 400 and 
            request.method in self.INVALIDATION_METHODS):
            
            await self._invalidate_caches_for_request(request, response)
        
        return response
    
    async def _invalidate_caches_for_request(self, request: Request, response: Response):
        """Invalidate caches based on request pattern"""
        
        url_path = request.url.path
        cache_types_to_invalidate: Set[str] = set()
        
        # Check which cache types should be invalidated
        for pattern, cache_types in self.INVALIDATION_PATTERNS.items():
            if re.match(pattern, url_path):
                cache_types_to_invalidate.update(cache_types)
        
        if cache_types_to_invalidate:
            logger.info(f"Invalidating caches for {url_path}: {cache_types_to_invalidate}")
            
            # Extract user ID from URL if present
            user_id = self._extract_user_id_from_url(url_path)
            
            # Invalidate specific cache types
            for cache_type in cache_types_to_invalidate:
                await self._invalidate_cache_type(cache_type, user_id)
    
    def _extract_user_id_from_url(self, url_path: str) -> str:
        """Extract user ID from URL path"""
        # Pattern to match user ID in URLs like /v1.0/user/{user_id}/...
        user_id_pattern = r'/v1\.0/user/([^/]+)/'
        match = re.search(user_id_pattern, url_path)
        return match.group(1) if match else None
    
    async def _invalidate_cache_type(self, cache_type: str, user_id: str = None):
        """Invalidate specific cache type"""
        
        try:
            if cache_type == 'user_stats':
                from cache_config import invalidate_cache_pattern
                invalidate_cache_pattern(f"{CacheKeys.USER_STATS}*")
                
            elif cache_type == 'user_list':
                from cache_config import invalidate_cache_pattern
                invalidate_cache_pattern(f"{CacheKeys.USER_LIST}*")
                
            elif cache_type == 'dashboard_stats':
                from cache_config import invalidate_cache_pattern
                invalidate_cache_pattern(f"{CacheKeys.DASHBOARD_STATS}*")
                
            elif cache_type == 'user_details':
                from cache_config import invalidate_cache_pattern
                if user_id:
                    invalidate_cache_pattern(f"{CacheKeys.USER_DETAILS}:{user_id}")
                else:
                    invalidate_cache_pattern(f"{CacheKeys.USER_DETAILS}*")
                    
        except Exception as e:
            logger.error(f"Error invalidating cache type {cache_type}: {e}")

class CacheWarmupService:
    """Service for warming up caches"""
    
    @staticmethod
    async def warm_essential_caches():
        """Warm up essential caches on application startup"""
        
        try:
            from services.cached_user_service import CachedUserService
            from database import SessionLocal
            
            # Create database session
            db = SessionLocal()
            
            try:
                # Initialize cached user service
                cached_service = CachedUserService(db)
                
                # Warm up caches
                cached_service.warm_cache()
                
                logger.info("Essential caches warmed up successfully")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Cache warmup failed: {e}")
    
    @staticmethod
    async def schedule_cache_refresh():
        """Schedule periodic cache refresh (can be called by a scheduler)"""
        
        try:
            from services.cached_user_service import CachedUserService
            from database import SessionLocal
            
            # Create database session
            db = SessionLocal()
            
            try:
                # Initialize cached user service
                cached_service = CachedUserService(db)
                
                # Refresh dashboard statistics (most expensive query)
                cached_service.get_dashboard_statistics()
                
                # Refresh user statistics
                cached_service.get_user_statistics()
                
                logger.info("Scheduled cache refresh completed")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Scheduled cache refresh failed: {e}")

# Cache management utilities
class CacheManager:
    """Utility class for cache management operations"""
    
    @staticmethod
    def clear_all_user_caches():
        """Clear all user-related caches"""
        from cache_config import invalidate_cache_pattern
        
        patterns = [
            f"{CacheKeys.USER_STATS}*",
            f"{CacheKeys.USER_LIST}*",
            f"{CacheKeys.USER_DETAILS}*",
            f"{CacheKeys.DASHBOARD_STATS}*"
        ]
        
        for pattern in patterns:
            invalidate_cache_pattern(pattern)
        
        logger.info("All user caches cleared")
    
    @staticmethod
    def get_cache_info():
        """Get cache status and information"""
        from cache_config import cache
        
        if not cache.is_available:
            return {
                'status': 'unavailable',
                'message': 'Redis cache is not available'
            }
        
        try:
            # Get Redis info
            info = cache.redis_client.info()
            
            return {
                'status': 'available',
                'redis_version': info.get('redis_version'),
                'used_memory': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'total_commands_processed': info.get('total_commands_processed'),
                'keyspace_hits': info.get('keyspace_hits'),
                'keyspace_misses': info.get('keyspace_misses'),
                'hit_rate': round(
                    info.get('keyspace_hits', 0) / 
                    max(info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0), 1) * 100, 
                    2
                )
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Error getting cache info: {e}'
            }