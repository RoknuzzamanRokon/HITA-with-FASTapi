"""
Cache management endpoints for monitoring and controlling cache
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, Annotated
import logging
from datetime import datetime

from middleware.cache_invalidation import CacheManager, CacheWarmupService
from cache_config import cache, CacheKeys
from routes.auth import get_current_user
from models import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/cache",
    tags=["Cache Management"])

@router.get("/health")
async def cache_health_check() -> Dict[str, Any]:
    """Check cache health and status"""
    
    try:
        cache_info = CacheManager.get_cache_info()
        return {
            "success": True,
            "cache_info": cache_info
        }
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache health check failed: {str(e)}"
        )

@router.get("/health/detailed")
async def detailed_cache_health_check() -> Dict[str, Any]:
    """Comprehensive cache health check with detailed metrics"""
    
    try:
        # Get basic cache info
        cache_info = CacheManager.get_cache_info()
        
        # Get detailed cache statistics
        detailed_stats = {}
        
        if cache.is_available:
            try:
                # Get Redis info
                redis_info = cache.redis_client.info()
                
                # Get cache key counts by type
                key_counts = {
                    'user_stats_keys': len(cache.redis_client.keys(f"{CacheKeys.USER_STATS}*")),
                    'user_list_keys': len(cache.redis_client.keys(f"{CacheKeys.USER_LIST}*")),
                    'user_details_keys': len(cache.redis_client.keys(f"{CacheKeys.USER_DETAILS}*")),
                    'dashboard_stats_keys': len(cache.redis_client.keys(f"{CacheKeys.DASHBOARD_STATS}*")),
                    'total_keys': len(cache.redis_client.keys("*"))
                }
                
                # Get memory usage
                memory_info = {
                    'used_memory': redis_info.get('used_memory_human', 'N/A'),
                    'used_memory_peak': redis_info.get('used_memory_peak_human', 'N/A'),
                    'memory_fragmentation_ratio': redis_info.get('mem_fragmentation_ratio', 'N/A')
                }
                
                # Get connection info
                connection_info = {
                    'connected_clients': redis_info.get('connected_clients', 'N/A'),
                    'total_connections_received': redis_info.get('total_connections_received', 'N/A'),
                    'uptime_in_seconds': redis_info.get('uptime_in_seconds', 'N/A')
                }
                
                # Get performance metrics
                performance_info = {
                    'keyspace_hits': redis_info.get('keyspace_hits', 0),
                    'keyspace_misses': redis_info.get('keyspace_misses', 0),
                    'hit_rate': 0
                }
                
                # Calculate hit rate
                total_requests = performance_info['keyspace_hits'] + performance_info['keyspace_misses']
                if total_requests > 0:
                    performance_info['hit_rate'] = round(
                        (performance_info['keyspace_hits'] / total_requests) * 100, 2
                    )
                
                detailed_stats = {
                    'key_counts': key_counts,
                    'memory_usage': memory_info,
                    'connections': connection_info,
                    'performance': performance_info,
                    'redis_version': redis_info.get('redis_version', 'N/A'),
                    'redis_mode': redis_info.get('redis_mode', 'N/A')
                }
                
            except Exception as redis_error:
                logger.warning(f"Could not get detailed Redis stats: {redis_error}")
                detailed_stats = {'error': f'Could not retrieve detailed stats: {str(redis_error)}'}
        else:
            detailed_stats = {'error': 'Cache is not available'}
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "cache_info": cache_info,
            "detailed_statistics": detailed_stats
        }
        
    except Exception as e:
        logger.error(f"Detailed cache health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detailed cache health check failed: {str(e)}"
        )

@router.post("/clear")
async def clear_all_caches(current_user: Annotated[User, Depends(get_current_user)]) -> Dict[str, Any]:
    """Clear all user-related caches (Admin only)"""
    
    # Check if user has admin privileges
    if current_user.role not in ['super_user', 'admin_user']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can clear caches"
        )
    
    try:
        CacheManager.clear_all_user_caches()
        
        logger.info(f"All caches cleared by user: {current_user.id}")
        
        return {
            "success": True,
            "message": "All user caches cleared successfully"
        }
        
    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear caches: {str(e)}"
        )

@router.post("/clear/user/{user_id}")
async def clear_user_cache(
    user_id: str, 
    current_user: Annotated[User, Depends(get_current_user)]
) -> Dict[str, Any]:
    """Clear cache for specific user (Admin only)"""
    
    # Check if user has admin privileges
    if current_user.role not in ['super_user', 'admin_user']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can clear user caches"
        )
    
    try:
        CacheKeys.invalidate_user_caches(user_id)
        
        logger.info(f"User cache cleared for {user_id} by user: {current_user.id}")
        
        return {
            "success": True,
            "message": f"Cache cleared for user {user_id}"
        }
        
    except Exception as e:
        logger.error(f"User cache clear failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear user cache: {str(e)}"
        )

@router.post("/warm")
async def warm_caches(current_user: Annotated[User, Depends(get_current_user)]) -> Dict[str, Any]:
    """Warm up essential caches (Admin only)"""
    
    # Check if user has admin privileges
    if current_user.role not in ['super_user', 'admin_user']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can warm caches"
        )
    
    try:
        await CacheWarmupService.warm_essential_caches()
        
        logger.info(f"Caches warmed by user: {current_user.id}")
        
        return {
            "success": True,
            "message": "Essential caches warmed successfully"
        }
        
    except Exception as e:
        logger.error(f"Cache warming failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to warm caches: {str(e)}"
        )

@router.get("/stats")
async def cache_statistics(current_user: Annotated[User, Depends(get_current_user)]) -> Dict[str, Any]:
    """Get cache statistics and performance metrics (Admin only)"""
    
    # Check if user has admin privileges
    if current_user.role not in ['super_user', 'admin_user']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can view cache statistics"
        )
    
    try:
        cache_info = CacheManager.get_cache_info()
        
        # Get cache key counts
        key_counts = {}
        if cache.is_available:
            try:
                key_counts = {
                    'user_stats_keys': len(cache.redis_client.keys(f"{CacheKeys.USER_STATS}*")),
                    'user_list_keys': len(cache.redis_client.keys(f"{CacheKeys.USER_LIST}*")),
                    'user_details_keys': len(cache.redis_client.keys(f"{CacheKeys.USER_DETAILS}*")),
                    'dashboard_stats_keys': len(cache.redis_client.keys(f"{CacheKeys.DASHBOARD_STATS}*")),
                    'total_keys': len(cache.redis_client.keys("*"))
                }
            except Exception as e:
                logger.warning(f"Could not get key counts: {e}")
                key_counts = {'error': 'Could not retrieve key counts'}
        
        return {
            "success": True,
            "cache_info": cache_info,
            "key_counts": key_counts
        }
        
    except Exception as e:
        logger.error(f"Cache statistics failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache statistics: {str(e)}"
        )

@router.get("/test")
async def test_cache_operations() -> Dict[str, Any]:
    """Test basic cache operations"""
    
    try:
        test_key = "cache_test_key"
        test_value = {"test": "data", "timestamp": "2025-01-01T00:00:00"}
        
        # Test set
        set_result = cache.set(test_key, test_value, 60)
        
        # Test get
        get_result = cache.get(test_key)
        
        # Test exists
        exists_result = cache.exists(test_key)
        
        # Test delete
        delete_result = cache.delete(test_key)
        
        # Test get after delete
        get_after_delete = cache.get(test_key)
        
        return {
            "success": True,
            "test_results": {
                "cache_available": cache.is_available,
                "set_operation": set_result,
                "get_operation": get_result == test_value,
                "exists_operation": exists_result,
                "delete_operation": delete_result,
                "get_after_delete": get_after_delete is None
            }
        }
        
    except Exception as e:
        logger.error(f"Cache test failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "cache_available": cache.is_available
        }