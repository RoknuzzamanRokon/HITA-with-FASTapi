"""
Enhanced user routes with caching support
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import logging

from database import get_db
import models
from services.cached_user_service import CachedUserService
from routes.auth import get_current_user
from models import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1.0/users",
    tags=["Cached User Management"])

@router.get("/list")
async def get_users_paginated(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(25, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for username or email"),
    role: Optional[str] = Query(None, description="Filter by user role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get paginated list of users with caching"""
    
    try:
        if current_user.role == models.UserRole.GENERAL_USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="General users cannot access the user list"
            )
        else:
            # Initialize cached user service
            cached_service = CachedUserService(db)
            
            # Get paginated users with caching
            result = cached_service.get_users_paginated(
                page=page,
                limit=limit,
                search=search,
                role=role,
                is_active=is_active,
                sort_by=sort_by,
                sort_order=sort_order
            )
            
            return {
                "success": True,
                "data": result
            }
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )

@router.get("/statistics")
async def get_user_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get user statistics with caching"""
    
    try:
        # Initialize cached user service
        cached_service = CachedUserService(db)
        
        # Get statistics with caching
        stats = cached_service.get_user_statistics()
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Error fetching user statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user statistics: {str(e)}"
        )

@router.get("/{user_id}/details")
async def get_user_details(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get detailed user information with caching"""
    
    try:
        # Initialize cached user service
        cached_service = CachedUserService(db)
        
        # Get user details with caching
        user_details = cached_service.get_user_details(user_id)
        
        if not user_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        return {
            "success": True,
            "data": user_details
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user details: {str(e)}"
        )

@router.get("/dashboard/statistics")
async def get_dashboard_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get comprehensive dashboard statistics with caching"""
    
    # Check if user has admin privileges for full dashboard access
    if current_user.role not in ['super_user', 'admin_user']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can access dashboard statistics"
        )
    
    try:
        # Initialize cached user service
        cached_service = CachedUserService(db)
        
        # Get dashboard statistics with caching
        dashboard_stats = cached_service.get_dashboard_statistics()
        
        return {
            "success": True,
            "data": dashboard_stats
        }
        
    except Exception as e:
        logger.error(f"Error fetching dashboard statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard statistics: {str(e)}"
        )

@router.post("/{user_id}/invalidate_cache")
async def invalidate_user_cache(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Manually invalidate cache for specific user (Admin only)"""
    
    # Check if user has admin privileges
    if current_user.role not in ['super_user', 'admin_user']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can invalidate user caches"
        )
    
    try:
        # Initialize cached user service
        cached_service = CachedUserService(db)
        
        # Invalidate user caches
        cached_service.invalidate_user_caches(user_id)
        
        logger.info(f"Cache invalidated for user {user_id} by {current_user.id}")
        
        return {
            "success": True,
            "message": f"Cache invalidated for user {user_id}"
        }
        
    except Exception as e:
        logger.error(f"Error invalidating user cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invalidate user cache: {str(e)}"
        )

# Health check endpoint for cached services
@router.get("/health/cache")
async def cache_health_check() -> Dict[str, Any]:
    """Check cache health for user services"""
    
    try:
        from cache_config import cache
        
        # Test basic cache operations
        test_key = "health_check_test"
        test_value = {"timestamp": "2025-01-01T00:00:00", "test": True}
        
        # Test cache operations
        cache_available = cache.is_available
        set_success = cache.set(test_key, test_value, 10) if cache_available else False
        get_success = cache.get(test_key) == test_value if cache_available else False
        delete_success = cache.delete(test_key) if cache_available else False
        
        return {
            "success": True,
            "cache_status": {
                "available": cache_available,
                "operations": {
                    "set": set_success,
                    "get": get_success,
                    "delete": delete_success
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "cache_status": {
                "available": False,
                "operations": {
                    "set": False,
                    "get": False,
                    "delete": False
                }
            }
        }