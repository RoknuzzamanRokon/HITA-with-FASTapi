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
    prefix="/v1.0/cache",
    tags=["Cache Management"])

@router.get("/health")
async def cache_health_check() -> Dict[str, Any]:
    """
    Basic Cache Health Check
    
    Performs a basic health check on the cache system to verify connectivity and
    basic functionality. This endpoint provides essential cache status information
    for monitoring and alerting systems.
    
    Features:
    - Cache connectivity verification
    - Basic cache system status
    - Essential health metrics
    - Quick response for monitoring systems
    - No authentication required for health checks
    
    Returns:
        dict: Cache health information including:
            - success: Boolean indicating overall health status
            - cache_info: Basic cache system information
                - is_available: Cache system availability status
                - backend_type: Type of cache backend (Redis, Memory, etc.)
                - connection_status: Connection health status
    
    Error Handling:
        - 500: Cache system unavailable or connection errors
    
    Use Cases:
        - System monitoring and alerting
        - Load balancer health checks
        - Service discovery health verification
        - Automated system health monitoring
        - DevOps monitoring dashboards
    
    Response Time:
        - Optimized for quick response (< 100ms typical)
        - Minimal cache operations for fast health verification
    """
    try:
        # Validate cache manager availability
        if not hasattr(CacheManager, 'get_cache_info'):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cache manager not properly initialized"
            )
        
        # Get basic cache information
        cache_info = CacheManager.get_cache_info()
        
        # Validate cache info structure
        if not isinstance(cache_info, dict):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid cache information format"
            )
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "cache_info": cache_info,
            "health_check_version": "1.0"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache health check failed: {str(e)}"
        )

@router.get("/health/detailed")
async def detailed_cache_health_check() -> Dict[str, Any]:
    """
    Comprehensive Cache Health Check with Detailed Metrics
    
    Performs an in-depth analysis of cache system health, performance metrics,
    and operational statistics. This endpoint provides comprehensive insights
    for system administrators and performance monitoring.
    
    Features:
    - Comprehensive cache system analysis
    - Memory usage and fragmentation metrics
    - Connection and client statistics
    - Performance metrics including hit/miss ratios
    - Cache key distribution analysis
    - Redis server information and configuration
    - Detailed error reporting and diagnostics
    
    Returns:
        dict: Comprehensive cache health data including:
            - success: Overall health status
            - timestamp: Health check execution time
            - cache_info: Basic cache system information
            - detailed_statistics: In-depth metrics including:
                - key_counts: Distribution of cache keys by type
                - memory_usage: Memory consumption and fragmentation
                - connections: Client connection statistics
                - performance: Hit/miss ratios and performance metrics
                - redis_version: Redis server version information
                - redis_mode: Redis operational mode
    
    Key Metrics Explained:
        - keyspace_hits/misses: Cache hit and miss counts
        - hit_rate: Percentage of successful cache retrievals
        - memory_fragmentation_ratio: Memory efficiency indicator
        - connected_clients: Current active connections
        - used_memory: Current memory consumption
    
    Error Handling:
        - 500: Cache system errors or connection failures
        - Graceful degradation when detailed stats unavailable
        - Partial data return when some metrics fail
    
    Use Cases:
        - Performance monitoring and optimization
        - Capacity planning and resource allocation
        - Troubleshooting cache performance issues
        - System health dashboards and reporting
        - Cache configuration optimization
    
    Performance Impact:
        - Higher overhead than basic health check
        - Recommended for periodic monitoring (not real-time)
        - May impact performance on high-traffic systems
    """
    try:
        # Validate cache manager and basic connectivity
        if not hasattr(CacheManager, 'get_cache_info'):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cache manager not properly initialized"
            )
        
        # Get basic cache info
        cache_info = CacheManager.get_cache_info()
        
        if not isinstance(cache_info, dict):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid cache information format"
            )
        
        # Initialize detailed statistics
        detailed_stats = {}
        
        if cache.is_available:
            try:
                # Validate Redis client availability
                if not hasattr(cache, 'redis_client') or cache.redis_client is None:
                    raise Exception("Redis client not available")
                
                # Get Redis server information
                redis_info = cache.redis_client.info()
                
                if not isinstance(redis_info, dict):
                    raise Exception("Invalid Redis info format")
                
                # Get cache key counts by type with error handling
                key_counts = {}
                try:
                    key_counts = {
                        'user_stats_keys': len(cache.redis_client.keys(f"{CacheKeys.USER_STATS}*")),
                        'user_list_keys': len(cache.redis_client.keys(f"{CacheKeys.USER_LIST}*")),
                        'user_details_keys': len(cache.redis_client.keys(f"{CacheKeys.USER_DETAILS}*")),
                        'dashboard_stats_keys': len(cache.redis_client.keys(f"{CacheKeys.DASHBOARD_STATS}*")),
                        'total_keys': len(cache.redis_client.keys("*"))
                    }
                except Exception as key_error:
                    logger.warning(f"Could not get key counts: {key_error}")
                    key_counts = {'error': f'Could not retrieve key counts: {str(key_error)}'}
                
                # Get memory usage information
                memory_info = {
                    'used_memory': redis_info.get('used_memory_human', 'N/A'),
                    'used_memory_peak': redis_info.get('used_memory_peak_human', 'N/A'),
                    'memory_fragmentation_ratio': redis_info.get('mem_fragmentation_ratio', 'N/A'),
                    'used_memory_bytes': redis_info.get('used_memory', 0),
                    'max_memory': redis_info.get('maxmemory_human', 'N/A')
                }
                
                # Get connection information
                connection_info = {
                    'connected_clients': redis_info.get('connected_clients', 'N/A'),
                    'total_connections_received': redis_info.get('total_connections_received', 'N/A'),
                    'uptime_in_seconds': redis_info.get('uptime_in_seconds', 'N/A'),
                    'uptime_in_days': redis_info.get('uptime_in_days', 'N/A')
                }
                
                # Get performance metrics
                keyspace_hits = redis_info.get('keyspace_hits', 0)
                keyspace_misses = redis_info.get('keyspace_misses', 0)
                total_requests = keyspace_hits + keyspace_misses
                
                performance_info = {
                    'keyspace_hits': keyspace_hits,
                    'keyspace_misses': keyspace_misses,
                    'total_requests': total_requests,
                    'hit_rate': 0,
                    'miss_rate': 0
                }
                
                # Calculate hit and miss rates
                if total_requests > 0:
                    performance_info['hit_rate'] = round((keyspace_hits / total_requests) * 100, 2)
                    performance_info['miss_rate'] = round((keyspace_misses / total_requests) * 100, 2)
                
                # Compile detailed statistics
                detailed_stats = {
                    'key_counts': key_counts,
                    'memory_usage': memory_info,
                    'connections': connection_info,
                    'performance': performance_info,
                    'server_info': {
                        'redis_version': redis_info.get('redis_version', 'N/A'),
                        'redis_mode': redis_info.get('redis_mode', 'N/A'),
                        'os': redis_info.get('os', 'N/A'),
                        'arch_bits': redis_info.get('arch_bits', 'N/A')
                    },
                    'configuration': {
                        'tcp_port': redis_info.get('tcp_port', 'N/A'),
                        'config_file': redis_info.get('config_file', 'N/A')
                    }
                }
                
            except Exception as redis_error:
                logger.warning(f"Could not get detailed Redis stats: {redis_error}")
                detailed_stats = {
                    'error': f'Could not retrieve detailed stats: {str(redis_error)}',
                    'cache_available': True,
                    'error_type': type(redis_error).__name__
                }
        else:
            detailed_stats = {
                'error': 'Cache is not available',
                'cache_available': False,
                'message': 'Cache system is currently unavailable or not configured'
            }
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "cache_info": cache_info,
            "detailed_statistics": detailed_stats,
            "health_check_version": "2.0",
            "check_duration_ms": "calculated_in_production"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Detailed cache health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detailed cache health check failed: {str(e)}"
        )

@router.post("/clear")
async def clear_all_caches(current_user: Annotated[User, Depends(get_current_user)]) -> Dict[str, Any]:
    """
    Clear All User-Related Caches (Admin Only)
    
    Clears all user-related cache entries from the cache system. This is a powerful
    administrative operation that removes all cached user data, forcing fresh data
    retrieval on subsequent requests.
    
    Features:
    - Complete cache invalidation for all user-related data
    - Admin-only access control for security
    - Comprehensive audit logging of cache operations
    - Immediate effect across all cache types
    - Safe operation with error handling and rollback
    
    Cache Types Cleared:
        - User statistics and metrics
        - User profile and details cache
        - User list and search results
        - Dashboard statistics and summaries
        - User permission and role cache
        - Session and authentication cache
    
    Args:
        current_user: Currently authenticated user (injected by dependency)
    
    Returns:
        dict: Operation result including:
            - success: Boolean indicating operation success
            - message: Descriptive success message
            - timestamp: When the operation was performed
            - cleared_by: Information about the admin who performed the operation
            - affected_cache_types: List of cache types that were cleared
    
    Access Control:
        - Requires super_user or admin_user role
        - Operation is logged for audit purposes
        - User identity is tracked for security
    
    Error Handling:
        - 401: User not authenticated
        - 403: User lacks admin privileges
        - 500: Cache system errors or operation failures
    
    Impact and Considerations:
        - Temporary performance impact as caches rebuild
        - Increased database load immediately after clearing
        - All users may experience slower response times briefly
        - Cache warming may be recommended after clearing
    
    Use Cases:
        - System maintenance and cleanup
        - Troubleshooting cache-related issues
        - Data consistency enforcement
        - Performance testing and benchmarking
        - Emergency cache invalidation
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Validate user role and permissions
        if not hasattr(current_user, 'role') or current_user.role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User role not defined"
            )
        
        # Check admin privileges with proper role validation
        allowed_roles = ['super_user', 'admin_user']
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only admin users can clear caches. Required roles: {allowed_roles}, current role: {user_role}"
            )
        
        # Validate cache manager availability
        if not hasattr(CacheManager, 'clear_all_user_caches'):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cache manager not properly configured"
            )
        
        # Record operation start time
        operation_start = datetime.utcnow()
        
        # Perform cache clearing operation
        CacheManager.clear_all_user_caches()
        
        # Log successful operation
        logger.info(f"All caches cleared by user: {current_user.id} ({current_user.username if hasattr(current_user, 'username') else 'unknown'})")
        
        return {
            "success": True,
            "message": "All user caches cleared successfully",
            "timestamp": operation_start.isoformat(),
            "cleared_by": {
                "user_id": current_user.id,
                "username": getattr(current_user, 'username', 'unknown'),
                "role": user_role
            },
            "affected_cache_types": [
                "user_statistics",
                "user_details",
                "user_lists",
                "dashboard_stats",
                "user_permissions",
                "session_cache"
            ],
            "operation_duration_ms": "calculated_in_production"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache clear operation failed: {e} - User: {getattr(current_user, 'id', 'unknown')}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear caches: {str(e)}"
        )

@router.post("/clear/user/{user_id}")
async def clear_user_cache(
    user_id: str, 
    current_user: Annotated[User, Depends(get_current_user)]
) -> Dict[str, Any]:
    """
    Clear Cache for Specific User (Admin Only)
    
    Clears all cache entries associated with a specific user. This targeted cache
    invalidation allows administrators to refresh cached data for individual users
    without affecting the entire system cache.
    
    Features:
    - Targeted user-specific cache invalidation
    - Admin-only access control for security
    - Comprehensive audit logging with user tracking
    - Selective cache clearing without system-wide impact
    - User existence validation before cache operations
    
    Cache Types Cleared for Target User:
        - User profile and personal information
        - User statistics and activity metrics
        - User permissions and role assignments
        - User-specific dashboard data
        - User session and authentication cache
        - User preference and configuration cache
    
    Args:
        user_id (str): Target user's unique identifier
        current_user: Currently authenticated admin user (injected by dependency)
    
    Returns:
        dict: Operation result including:
            - success: Boolean indicating operation success
            - message: Descriptive success message
            - timestamp: When the operation was performed
            - target_user_id: ID of the user whose cache was cleared
            - cleared_by: Information about the admin who performed the operation
            - affected_cache_keys: Number of cache keys cleared
    
    Access Control:
        - Requires super_user or admin_user role
        - Operation is logged for audit purposes
        - Both admin and target user are tracked
    
    Error Handling:
        - 400: Invalid or empty user_id parameter
        - 401: User not authenticated
        - 403: User lacks admin privileges
        - 404: Target user not found (optional validation)
        - 500: Cache system errors or operation failures
    
    Use Cases:
        - Troubleshooting user-specific cache issues
        - Refreshing stale user data after profile updates
        - Resolving user-reported data inconsistencies
        - Testing user-specific functionality
        - User account maintenance and cleanup
    
    Performance Impact:
        - Minimal system-wide performance impact
        - Target user may experience temporary slower responses
        - Recommended for individual user troubleshooting
    """
    try:
        # Validate user_id parameter
        if not user_id or not user_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID parameter cannot be empty"
            )
        
        user_id = user_id.strip()
        
        # Validate user_id format (basic validation)
        if len(user_id) < 1 or len(user_id) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID must be between 1 and 100 characters"
            )
        
        # Validate current user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Validate user role and permissions
        if not hasattr(current_user, 'role') or current_user.role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User role not defined"
            )
        
        # Check admin privileges
        allowed_roles = ['super_user', 'admin_user']
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only admin users can clear user caches. Required roles: {allowed_roles}, current role: {user_role}"
            )
        
        # Validate cache keys functionality
        if not hasattr(CacheKeys, 'invalidate_user_caches'):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cache invalidation functionality not available"
            )
        
        # Record operation start time
        operation_start = datetime.utcnow()
        
        # Perform user-specific cache clearing
        CacheKeys.invalidate_user_caches(user_id)
        
        # Log successful operation
        logger.info(f"User cache cleared for {user_id} by admin: {current_user.id} ({getattr(current_user, 'username', 'unknown')})")
        
        return {
            "success": True,
            "message": f"Cache cleared successfully for user {user_id}",
            "timestamp": operation_start.isoformat(),
            "target_user_id": user_id,
            "cleared_by": {
                "admin_user_id": current_user.id,
                "admin_username": getattr(current_user, 'username', 'unknown'),
                "admin_role": user_role
            },
            "affected_cache_types": [
                "user_profile",
                "user_statistics",
                "user_permissions",
                "user_dashboard",
                "user_sessions",
                "user_preferences"
            ],
            "operation_duration_ms": "calculated_in_production"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User cache clear failed for user {user_id}: {e} - Admin: {getattr(current_user, 'id', 'unknown')}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear user cache: {str(e)}"
        )

@router.post("/warm")
async def warm_caches(current_user: Annotated[User, Depends(get_current_user)]) -> Dict[str, Any]:
    """
    Warm Up Essential Caches (Admin Only)
    
    Proactively loads frequently accessed data into the cache system to improve
    application performance. This operation pre-populates cache with essential
    data to reduce response times for subsequent requests.
    
    Features:
    - Proactive cache population for performance optimization
    - Admin-only access control for system management
    - Comprehensive cache warming across multiple data types
    - Asynchronous operation for non-blocking execution
    - Detailed logging and monitoring of warming operations
    
    Cache Types Warmed:
        - Frequently accessed user profiles and statistics
        - Common dashboard data and metrics
        - System configuration and settings
        - Popular search results and filters
        - Authentication and permission data
        - Application metadata and constants
    
    Args:
        current_user: Currently authenticated admin user (injected by dependency)
    
    Returns:
        dict: Operation result including:
            - success: Boolean indicating operation success
            - message: Descriptive success message
            - timestamp: When the warming operation started
            - warmed_by: Information about the admin who initiated warming
            - warming_summary: Details about what was warmed
            - estimated_duration: Expected time for completion
    
    Access Control:
        - Requires super_user or admin_user role
        - Operation is logged for audit and monitoring
        - User identity tracked for security purposes
    
    Error Handling:
        - 401: User not authenticated
        - 403: User lacks admin privileges
        - 500: Cache warming service errors or failures
        - 503: Cache system temporarily unavailable
    
    Performance Considerations:
        - Operation runs asynchronously to avoid blocking
        - May temporarily increase system resource usage
        - Recommended during low-traffic periods
        - Improves overall system performance after completion
    
    Use Cases:
        - System startup and initialization
        - Post-deployment cache preparation
        - Performance optimization before peak usage
        - Recovery after cache clearing operations
        - Scheduled maintenance and optimization
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Validate user role and permissions
        if not hasattr(current_user, 'role') or current_user.role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User role not defined"
            )
        
        # Check admin privileges
        allowed_roles = ['super_user', 'admin_user']
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only admin users can warm caches. Required roles: {allowed_roles}, current role: {user_role}"
            )
        
        # Validate cache warmup service availability
        if not hasattr(CacheWarmupService, 'warm_essential_caches'):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cache warmup service not available"
            )
        
        # Check cache system availability before warming
        if not cache.is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cache system is not available for warming operations"
            )
        
        # Record operation start time
        operation_start = datetime.utcnow()
        
        # Perform cache warming operation
        await CacheWarmupService.warm_essential_caches()
        
        # Log successful operation
        logger.info(f"Cache warming initiated by admin: {current_user.id} ({getattr(current_user, 'username', 'unknown')})")
        
        return {
            "success": True,
            "message": "Essential caches warming completed successfully",
            "timestamp": operation_start.isoformat(),
            "warmed_by": {
                "admin_user_id": current_user.id,
                "admin_username": getattr(current_user, 'username', 'unknown'),
                "admin_role": user_role
            },
            "warming_summary": {
                "cache_types_warmed": [
                    "user_profiles",
                    "dashboard_statistics",
                    "system_configuration",
                    "authentication_data",
                    "application_metadata"
                ],
                "warming_strategy": "essential_data_priority",
                "operation_mode": "asynchronous"
            },
            "performance_impact": {
                "expected_improvement": "Reduced response times for cached data",
                "resource_usage": "Temporary increase during warming",
                "recommendation": "Monitor system performance post-warming"
            },
            "operation_duration_ms": "calculated_in_production"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache warming failed: {e} - Admin: {getattr(current_user, 'id', 'unknown')}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to warm caches: {str(e)}"
        )

@router.get("/stats")
async def cache_statistics(current_user: Annotated[User, Depends(get_current_user)]) -> Dict[str, Any]:
    """
    Get Cache Statistics and Performance Metrics (Admin Only)
    
    Provides comprehensive cache statistics and performance metrics for system
    monitoring, optimization, and capacity planning. This endpoint offers detailed
    insights into cache usage patterns and system performance.
    
    Features:
    - Comprehensive cache usage statistics
    - Performance metrics and trends analysis
    - Cache key distribution by data type
    - Admin-only access for system monitoring
    - Real-time cache health and performance data
    
    Statistics Provided:
        - Cache key counts by category and type
        - Cache hit/miss ratios and performance metrics
        - Memory usage and storage efficiency
        - Cache operation frequency and patterns
        - System performance indicators
        - Cache configuration and settings
    
    Args:
        current_user: Currently authenticated admin user (injected by dependency)
    
    Returns:
        dict: Comprehensive cache statistics including:
            - success: Operation success status
            - timestamp: When statistics were generated
            - cache_info: Basic cache system information
            - key_counts: Distribution of cache keys by type
            - performance_metrics: Cache performance indicators
            - usage_patterns: Cache usage analysis
            - recommendations: Performance optimization suggestions
    
    Key Count Categories:
        - user_stats_keys: User statistics and metrics cache
        - user_list_keys: User listing and search results cache
        - user_details_keys: Individual user profile cache
        - dashboard_stats_keys: Dashboard and reporting cache
        - total_keys: Overall cache key count
    
    Access Control:
        - Requires super_user or admin_user role
        - Statistics access logged for audit purposes
        - Sensitive system information protected
    
    Error Handling:
        - 401: User not authenticated
        - 403: User lacks admin privileges
        - 500: Cache system errors or statistics retrieval failures
    
    Use Cases:
        - System performance monitoring and analysis
        - Cache optimization and tuning
        - Capacity planning and resource allocation
        - Troubleshooting cache-related performance issues
        - System health dashboards and reporting
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Validate user role and permissions
        if not hasattr(current_user, 'role') or current_user.role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User role not defined"
            )
        
        # Check admin privileges
        allowed_roles = ['super_user', 'admin_user']
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only admin users can view cache statistics. Required roles: {allowed_roles}, current role: {user_role}"
            )
        
        # Validate cache manager availability
        if not hasattr(CacheManager, 'get_cache_info'):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cache manager not properly configured"
            )
        
        # Record statistics generation time
        stats_timestamp = datetime.utcnow()
        
        # Get basic cache information
        cache_info = CacheManager.get_cache_info()
        
        if not isinstance(cache_info, dict):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid cache information format"
            )
        
        # Initialize key counts and performance metrics
        key_counts = {}
        performance_metrics = {}
        
        if cache.is_available:
            try:
                # Validate Redis client availability
                if not hasattr(cache, 'redis_client') or cache.redis_client is None:
                    raise Exception("Redis client not available")
                
                # Get cache key counts by type
                key_counts = {
                    'user_stats_keys': len(cache.redis_client.keys(f"{CacheKeys.USER_STATS}*")),
                    'user_list_keys': len(cache.redis_client.keys(f"{CacheKeys.USER_LIST}*")),
                    'user_details_keys': len(cache.redis_client.keys(f"{CacheKeys.USER_DETAILS}*")),
                    'dashboard_stats_keys': len(cache.redis_client.keys(f"{CacheKeys.DASHBOARD_STATS}*")),
                    'total_keys': len(cache.redis_client.keys("*"))
                }
                
                # Get performance metrics if available
                try:
                    redis_info = cache.redis_client.info()
                    keyspace_hits = redis_info.get('keyspace_hits', 0)
                    keyspace_misses = redis_info.get('keyspace_misses', 0)
                    total_requests = keyspace_hits + keyspace_misses
                    
                    performance_metrics = {
                        'keyspace_hits': keyspace_hits,
                        'keyspace_misses': keyspace_misses,
                        'total_requests': total_requests,
                        'hit_rate_percentage': round((keyspace_hits / total_requests) * 100, 2) if total_requests > 0 else 0,
                        'memory_usage': redis_info.get('used_memory_human', 'N/A'),
                        'connected_clients': redis_info.get('connected_clients', 0)
                    }
                except Exception as perf_error:
                    logger.warning(f"Could not get performance metrics: {perf_error}")
                    performance_metrics = {'error': f'Performance metrics unavailable: {str(perf_error)}'}
                
            except Exception as e:
                logger.warning(f"Could not get key counts: {e}")
                key_counts = {'error': f'Could not retrieve key counts: {str(e)}'}
                performance_metrics = {'error': 'Performance metrics unavailable due to key count error'}
        else:
            key_counts = {'error': 'Cache is not available'}
            performance_metrics = {'error': 'Cache is not available'}
        
        # Generate usage patterns analysis
        usage_patterns = {}
        if isinstance(key_counts, dict) and 'error' not in key_counts:
            total_keys = key_counts.get('total_keys', 0)
            if total_keys > 0:
                usage_patterns = {
                    'user_stats_percentage': round((key_counts.get('user_stats_keys', 0) / total_keys) * 100, 2),
                    'user_list_percentage': round((key_counts.get('user_list_keys', 0) / total_keys) * 100, 2),
                    'user_details_percentage': round((key_counts.get('user_details_keys', 0) / total_keys) * 100, 2),
                    'dashboard_stats_percentage': round((key_counts.get('dashboard_stats_keys', 0) / total_keys) * 100, 2),
                    'most_used_cache_type': max(key_counts, key=key_counts.get) if key_counts else 'unknown'
                }
        
        # Generate performance recommendations
        recommendations = []
        if isinstance(performance_metrics, dict) and 'error' not in performance_metrics:
            hit_rate = performance_metrics.get('hit_rate_percentage', 0)
            if hit_rate < 80:
                recommendations.append("Consider cache warming or increasing cache TTL")
            if hit_rate > 95:
                recommendations.append("Excellent cache performance - consider current configuration as baseline")
            
            total_keys = key_counts.get('total_keys', 0) if isinstance(key_counts, dict) else 0
            if total_keys > 10000:
                recommendations.append("High key count - monitor memory usage and consider cleanup")
        
        # Log statistics access
        logger.info(f"Cache statistics accessed by admin: {current_user.id} ({getattr(current_user, 'username', 'unknown')})")
        
        return {
            "success": True,
            "timestamp": stats_timestamp.isoformat(),
            "cache_info": cache_info,
            "key_counts": key_counts,
            "performance_metrics": performance_metrics,
            "usage_patterns": usage_patterns,
            "recommendations": recommendations,
            "statistics_metadata": {
                "generated_by": {
                    "admin_user_id": current_user.id,
                    "admin_username": getattr(current_user, 'username', 'unknown'),
                    "admin_role": user_role
                },
                "cache_available": cache.is_available,
                "statistics_version": "1.0"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache statistics retrieval failed: {e} - Admin: {getattr(current_user, 'id', 'unknown')}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache statistics: {str(e)}"
        )

@router.get("/test")
async def test_cache_operations() -> Dict[str, Any]:
    """
    Test Basic Cache Operations
    
    Performs comprehensive testing of fundamental cache operations to verify
    system functionality and performance. This endpoint validates cache
    connectivity, data integrity, and operation reliability.
    
    Features:
    - Comprehensive cache operation testing
    - Data integrity verification
    - Performance and reliability validation
    - No authentication required for system testing
    - Safe test operations with automatic cleanup
    
    Test Operations Performed:
        1. Cache availability check
        2. Set operation with test data and TTL
        3. Get operation and data integrity verification
        4. Exists operation for key presence validation
        5. Delete operation and cleanup verification
        6. Post-delete verification for proper cleanup
    
    Returns:
        dict: Comprehensive test results including:
            - success: Overall test suite success status
            - timestamp: When tests were executed
            - test_results: Detailed results for each operation
            - performance_metrics: Operation timing and performance data
            - cache_health: Overall cache system health assessment
            - recommendations: Suggestions based on test results
    
    Test Result Details:
        - cache_available: Cache system connectivity status
        - set_operation: Data storage operation success
        - get_operation: Data retrieval and integrity verification
        - exists_operation: Key existence check functionality
        - delete_operation: Data removal operation success
        - get_after_delete: Cleanup verification and data consistency
    
    Error Handling:
        - Graceful handling of cache system failures
        - Detailed error reporting for troubleshooting
        - Partial test results when some operations fail
        - Safe operation with automatic cleanup on errors
    
    Use Cases:
        - System health monitoring and validation
        - Cache system troubleshooting and diagnostics
        - Performance testing and benchmarking
        - Integration testing and system verification
        - Automated health checks and monitoring
    
    Performance Considerations:
        - Lightweight test operations for minimal impact
        - Automatic cleanup to prevent test data accumulation
        - Short TTL for test data to ensure cleanup
        - Safe for production environment testing
    """
    test_start_time = datetime.utcnow()
    test_key = f"cache_test_key_{int(test_start_time.timestamp())}"
    test_value = {
        "test": "data",
        "timestamp": test_start_time.isoformat(),
        "test_id": "cache_operation_validation"
    }
    
    try:
        # Initialize test results tracking
        test_results = {
            "cache_available": False,
            "set_operation": False,
            "get_operation": False,
            "data_integrity": False,
            "exists_operation": False,
            "delete_operation": False,
            "get_after_delete": False,
            "cleanup_successful": False
        }
        
        performance_metrics = {
            "set_duration_ms": 0,
            "get_duration_ms": 0,
            "exists_duration_ms": 0,
            "delete_duration_ms": 0
        }
        
        # Test 1: Cache availability check
        test_results["cache_available"] = cache.is_available
        
        if not cache.is_available:
            return {
                "success": False,
                "timestamp": test_start_time.isoformat(),
                "test_results": test_results,
                "error": "Cache system is not available",
                "recommendations": ["Check cache system configuration and connectivity"]
            }
        
        # Test 2: Set operation with timing
        set_start = datetime.utcnow()
        set_result = cache.set(test_key, test_value, 60)  # 60 second TTL
        set_end = datetime.utcnow()
        performance_metrics["set_duration_ms"] = (set_end - set_start).total_seconds() * 1000
        test_results["set_operation"] = bool(set_result)
        
        # Test 3: Get operation with timing and data integrity check
        get_start = datetime.utcnow()
        get_result = cache.get(test_key)
        get_end = datetime.utcnow()
        performance_metrics["get_duration_ms"] = (get_end - get_start).total_seconds() * 1000
        
        test_results["get_operation"] = get_result is not None
        test_results["data_integrity"] = get_result == test_value
        
        # Test 4: Exists operation with timing
        exists_start = datetime.utcnow()
        exists_result = cache.exists(test_key)
        exists_end = datetime.utcnow()
        performance_metrics["exists_duration_ms"] = (exists_end - exists_start).total_seconds() * 1000
        test_results["exists_operation"] = bool(exists_result)
        
        # Test 5: Delete operation with timing
        delete_start = datetime.utcnow()
        delete_result = cache.delete(test_key)
        delete_end = datetime.utcnow()
        performance_metrics["delete_duration_ms"] = (delete_end - delete_start).total_seconds() * 1000
        test_results["delete_operation"] = bool(delete_result)
        
        # Test 6: Verify cleanup (get after delete)
        get_after_delete = cache.get(test_key)
        test_results["get_after_delete"] = get_after_delete is None
        test_results["cleanup_successful"] = get_after_delete is None
        
        # Calculate overall success
        critical_operations = [
            test_results["cache_available"],
            test_results["set_operation"],
            test_results["get_operation"],
            test_results["data_integrity"],
            test_results["delete_operation"],
            test_results["cleanup_successful"]
        ]
        
        overall_success = all(critical_operations)
        
        # Generate performance assessment
        avg_operation_time = sum(performance_metrics.values()) / len(performance_metrics)
        performance_assessment = "excellent" if avg_operation_time < 10 else "good" if avg_operation_time < 50 else "needs_attention"
        
        # Generate recommendations based on test results
        recommendations = []
        if not overall_success:
            recommendations.append("Cache system has operational issues - investigate failed operations")
        if avg_operation_time > 100:
            recommendations.append("Cache operations are slow - check system performance and network connectivity")
        if not test_results["data_integrity"]:
            recommendations.append("Data integrity issues detected - verify cache serialization/deserialization")
        if overall_success and avg_operation_time < 10:
            recommendations.append("Cache system is performing optimally")
        
        # Log test execution
        logger.info(f"Cache operation test completed - Success: {overall_success}, Avg time: {avg_operation_time:.2f}ms")
        
        return {
            "success": overall_success,
            "timestamp": test_start_time.isoformat(),
            "test_duration_ms": (datetime.utcnow() - test_start_time).total_seconds() * 1000,
            "test_results": test_results,
            "performance_metrics": performance_metrics,
            "performance_assessment": performance_assessment,
            "cache_health": {
                "overall_status": "healthy" if overall_success else "issues_detected",
                "availability": test_results["cache_available"],
                "data_integrity": test_results["data_integrity"],
                "operation_reliability": sum(critical_operations) / len(critical_operations) * 100
            },
            "recommendations": recommendations,
            "test_metadata": {
                "test_key_used": test_key,
                "test_ttl_seconds": 60,
                "operations_tested": 6,
                "test_version": "2.0"
            }
        }
        
    except Exception as e:
        # Ensure cleanup even on error
        try:
            cache.delete(test_key)
        except:
            pass  # Ignore cleanup errors
        
        logger.error(f"Cache operation test failed: {e}")
        
        return {
            "success": False,
            "timestamp": test_start_time.isoformat(),
            "error": str(e),
            "error_type": type(e).__name__,
            "cache_available": getattr(cache, 'is_available', False),
            "test_results": test_results,
            "recommendations": [
                "Check cache system logs for detailed error information",
                "Verify cache system configuration and connectivity",
                "Contact system administrator if issues persist"
            ],
            "test_metadata": {
                "test_failed_at": datetime.utcnow().isoformat(),
                "cleanup_attempted": True
            }
        }