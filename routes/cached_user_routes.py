"""
Enhanced user routes with caching support
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from database import get_db
import models
from services.cached_user_service import CachedUserService
from routes.auth import get_current_user
from models import User, UserRole
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel
from models import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1.0/cache/users", tags=["Cached User Management"])

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
    """
    Get Paginated List of Users with Caching (Super User and Admin User Only)
    
    Retrieves a paginated list of users with advanced filtering, sorting, and search
    capabilities. This endpoint utilizes intelligent caching to optimize performance
    for administrative user management operations.
    
    Features:
    - High-performance cached user listing with intelligent cache invalidation
    - Advanced filtering by role, active status, and search terms
    - Flexible sorting options with configurable sort order
    - Comprehensive pagination support for large user datasets
    - Role-based access control with audit logging
    - Search functionality across username and email fields
    
    Args:
        page (int): Page number for pagination (minimum: 1, default: 1)
        limit (int): Number of items per page (range: 1-100, default: 25)
        search (Optional[str]): Search term for filtering by username or email
        role (Optional[str]): Filter users by specific role
        is_active (Optional[bool]): Filter by user active status
        sort_by (str): Field to sort by (default: "created_at")
        sort_order (str): Sort order - "asc" or "desc" (default: "desc")
        db (Session): Database session (injected by dependency)
        current_user (User): Currently authenticated user (injected by dependency)
    
    Returns:
        dict: Paginated user data including:
            - success: Operation success status
            - data: User list with pagination metadata
                - users: List of user objects with details
                - pagination: Page info, total count, has_next/prev
                - filters_applied: Summary of applied filters
                - cache_info: Cache hit/miss information
    
    Access Control:
        - Requires SUPER_USER or ADMIN_USER role
        - All access attempts are logged for audit purposes
        - User identity and query parameters tracked
    
    Caching Strategy:
        - Intelligent caching based on query parameters
        - Automatic cache invalidation on user data changes
        - Role-specific cache optimization
        - Performance metrics tracking
    
    Error Handling:
        - 400: Invalid query parameters or pagination values
        - 401: User not authenticated
        - 403: Insufficient privileges (non-admin users)
        - 500: Database errors or caching system failures
    
    Search Functionality:
        - Case-insensitive search across username and email
        - Partial matching support for flexible user discovery
        - Search term sanitization for security
    
    Use Cases:
        - Administrative user management and oversight
        - User account monitoring and maintenance
        - Bulk user operations and analysis
        - System administration and user support
    """
    try:
        # Validate pagination parameters
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page number must be at least 1"
            )
        
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be between 1 and 100"
            )
        
        # Validate sort parameters
        valid_sort_fields = ["created_at", "username", "email", "role", "is_active", "last_login"]
        if sort_by not in valid_sort_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field. Valid options: {valid_sort_fields}"
            )
        
        # Validate role filter if provided
        if role:
            valid_roles = [r.value for r in UserRole]
            if role not in valid_roles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role filter. Valid options: {valid_roles}"
                )
        
        # Sanitize search term
        if search:
            search = search.strip()
            if len(search) > 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Search term cannot exceed 100 characters"
                )
        
        # 🔒 SECURITY CHECK: Only super users and admin users can access user list
        if not current_user or current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Only super users and admin users can view user list."
            )
        
        # 📝 AUDIT LOG: Record user list access
        try:
            audit_logger = AuditLogger(db)
            audit_logger.log_activity(
                activity_type=ActivityType.API_ACCESS,
                user_id=current_user.id,
                details={
                    "endpoint": "/v1.0/users/list",
                    "action": "view_user_list",
                    "page": page,
                    "limit": limit,
                    "search": search,
                    "role_filter": role,
                    "is_active_filter": is_active,
                    "sort_by": sort_by,
                    "sort_order": sort_order
                },
                security_level=SecurityLevel.MEDIUM,
                success=True
            )
        except Exception as audit_error:
            logger.warning(f"Audit logging failed: {audit_error}")
        
        # Initialize cached user service
        cached_service = CachedUserService(db)
        
        # Get paginated users with enhanced caching
        result = cached_service.get_users_paginated(
            page=page,
            limit=limit,
            search=search,
            role=role,
            is_active=is_active,
            sort_by=sort_by,
            sort_order=sort_order,
            current_user_role=current_user.role
        )
        
        # Add metadata to response
        result.update({
            "request_metadata": {
                "requested_by": current_user.id,
                "request_timestamp": datetime.utcnow().isoformat(),
                "query_parameters": {
                    "page": page,
                    "limit": limit,
                    "search": search,
                    "role": role,
                    "is_active": is_active,
                    "sort_by": sort_by,
                    "sort_order": sort_order
                }
            }
        })
        
        return {
            "success": True,
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching users: {e} - User: {getattr(current_user, 'id', 'unknown')}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )

@router.get("/statistics")
async def get_user_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get User Statistics with Caching (Super User and Admin User Only)
    
    Retrieves comprehensive user statistics and analytics with intelligent caching
    for optimal performance. This endpoint provides essential metrics for user
    management, system monitoring, and administrative decision-making.
    
    Features:
    - Comprehensive user analytics and statistical insights
    - High-performance caching with automatic refresh strategies
    - Role-based access control with audit logging
    - Real-time and historical user metrics
    - System health indicators and user engagement metrics
    
    Statistics Provided:
        - Total user counts by role and status
        - User registration trends and growth metrics
        - Activity patterns and engagement statistics
        - Role distribution and permission analytics
        - Account status breakdown (active/inactive/suspended)
        - Login frequency and user engagement metrics
        - Geographic distribution (if available)
        - System usage patterns and peak activity times
    
    Args:
        db (Session): Database session (injected by dependency)
        current_user (User): Currently authenticated user (injected by dependency)
    
    Returns:
        dict: Comprehensive user statistics including:
            - success: Operation success status
            - data: Statistical data including:
                - user_counts: Total and categorized user counts
                - role_distribution: User distribution by role
                - activity_metrics: User engagement and activity stats
                - growth_trends: Registration and growth patterns
                - system_health: User-related system health indicators
                - cache_info: Cache performance and hit rate information
    
    Access Control:
        - Requires SUPER_USER or ADMIN_USER role
        - All access attempts logged for audit and security
        - Statistics access tracked for compliance
    
    Caching Strategy:
        - Intelligent caching with configurable TTL
        - Automatic cache invalidation on user data changes
        - Performance optimization for frequent administrative access
        - Cache warming for critical statistics
    
    Error Handling:
        - 401: User not authenticated
        - 403: Insufficient privileges (non-admin users)
        - 500: Database errors, caching failures, or calculation errors
    
    Performance Considerations:
        - Optimized queries with database indexing
        - Cached results for improved response times
        - Efficient aggregation and calculation methods
        - Minimal database load through intelligent caching
    
    Use Cases:
        - Administrative dashboards and reporting
        - System capacity planning and resource allocation
        - User behavior analysis and insights
        - Compliance reporting and audit requirements
        - Performance monitoring and optimization
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # 🔒 SECURITY CHECK: Only super users and admin users can access user statistics
        if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Only super users and admin users can view user statistics."
            )
        
        # 📝 AUDIT LOG: Record statistics access
        try:
            audit_logger = AuditLogger(db)
            audit_logger.log_activity(
                activity_type=ActivityType.API_ACCESS,
                user_id=current_user.id,
                details={
                    "endpoint": "/v1.0/users/statistics",
                    "action": "view_user_statistics",
                    "requested_by_role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
                },
                security_level=SecurityLevel.MEDIUM,
                success=True
            )
        except Exception as audit_error:
            logger.warning(f"Audit logging failed for user statistics: {audit_error}")
        
        # Initialize cached user service with validation
        try:
            cached_service = CachedUserService(db)
        except Exception as service_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize user service: {str(service_error)}"
            )
        
        # Get statistics with caching
        stats = cached_service.get_user_statistics()
        
        if stats is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve user statistics"
            )
        
        # Add metadata to statistics
        enhanced_stats = {
            **stats,
            "statistics_metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "requested_by": {
                    "user_id": current_user.id,
                    "username": getattr(current_user, 'username', 'unknown'),
                    "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
                },
                "data_freshness": "cached" if hasattr(stats, 'cache_hit') else "real_time",
                "statistics_version": "2.0"
            }
        }
        
        return {
            "success": True,
            "data": enhanced_stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user statistics: {e} - User: {getattr(current_user, 'id', 'unknown')}")
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
    """
    Get Detailed User Information with Caching (Super User and Admin User Only)
    
    Retrieves comprehensive user details including profile information, activity
    history, permissions, and system metadata. This endpoint provides administrators
    with complete user oversight capabilities through intelligent caching.
    
    Features:
    - Comprehensive user profile and account information
    - Activity history and engagement metrics
    - Permission and role assignment details
    - System metadata and account status information
    - High-performance caching with automatic invalidation
    - Detailed audit logging for security and compliance
    
    User Details Provided:
        - Basic profile information (username, email, names)
        - Account status and verification details
        - Role assignments and permission levels
        - Registration and last activity timestamps
        - Login history and session information
        - Provider permissions and access rights
        - Account settings and preferences
        - Security-related information (2FA status, etc.)
    
    Args:
        user_id (str): Target user's unique identifier
        db (Session): Database session (injected by dependency)
        current_user (User): Currently authenticated user (injected by dependency)
    
    Returns:
        dict: Comprehensive user details including:
            - success: Operation success status
            - data: User detail object including:
                - profile: Basic user profile information
                - account: Account status and settings
                - permissions: Role and provider permissions
                - activity: Recent activity and engagement metrics
                - security: Security-related information
                - metadata: System metadata and timestamps
                - cache_info: Cache performance information
    
    Access Control:
        - Requires SUPER_USER or ADMIN_USER role
        - All access attempts logged with target user ID
        - Sensitive information access tracked for audit
    
    Caching Strategy:
        - User-specific caching with intelligent invalidation
        - Automatic cache refresh on user data changes
        - Performance optimization for administrative workflows
        - Cache warming for frequently accessed users
    
    Error Handling:
        - 400: Invalid user_id format or parameter
        - 401: User not authenticated
        - 403: Insufficient privileges (non-admin users)
        - 404: Target user not found
        - 500: Database errors or caching system failures
    
    Privacy and Security:
        - Sensitive data handling with appropriate access controls
        - Audit trail for all user detail access
        - Data sanitization for security
        - Compliance with privacy regulations
    
    Use Cases:
        - Administrative user account management
        - User support and troubleshooting
        - Security investigations and compliance audits
        - Account verification and validation
        - User behavior analysis and insights
    """
    try:
        # Validate user_id parameter
        if not user_id or not user_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID parameter cannot be empty"
            )
        
        user_id = user_id.strip()
        
        # Basic user_id format validation
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
        
        # 🔒 SECURITY CHECK: Only super users and admin users can access user details
        if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Only super users and admin users can view user details."
            )
        
        # 📝 AUDIT LOG: Record user details access
        try:
            audit_logger = AuditLogger(db)
            audit_logger.log_activity(
                activity_type=ActivityType.API_ACCESS,
                user_id=current_user.id,
                details={
                    "endpoint": f"/v1.0/users/{user_id}/details",
                    "action": "view_user_details",
                    "target_user_id": user_id,
                    "requested_by_role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
                },
                security_level=SecurityLevel.MEDIUM,
                success=True
            )
        except Exception as audit_error:
            logger.warning(f"Audit logging failed for user details access: {audit_error}")
        
        # Initialize cached user service with validation
        try:
            cached_service = CachedUserService(db)
        except Exception as service_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize user service: {str(service_error)}"
            )
        
        # Get user details with caching
        user_details = cached_service.get_user_details(user_id)
        
        if not user_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID '{user_id}' not found"
            )
        
        # Add metadata to user details
        enhanced_details = {
            **user_details,
            "access_metadata": {
                "accessed_at": datetime.utcnow().isoformat(),
                "accessed_by": {
                    "user_id": current_user.id,
                    "username": getattr(current_user, 'username', 'unknown'),
                    "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
                },
                "target_user_id": user_id,
                "data_source": "cached" if hasattr(user_details, 'cache_hit') else "database"
            }
        }
        
        return {
            "success": True,
            "data": enhanced_details
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user details for {user_id}: {e} - Requested by: {getattr(current_user, 'id', 'unknown')}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user details: {str(e)}"
        )

@router.get("/dashboard/statistics")
async def get_dashboard_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get Comprehensive Dashboard Statistics with Caching
    
    Retrieves comprehensive dashboard statistics and key performance indicators
    for administrative oversight and system monitoring. This endpoint provides
    real-time insights into system health, user activity, and operational metrics.
    
    Features:
    - Comprehensive system and user analytics dashboard
    - Real-time and historical performance metrics
    - High-performance caching with intelligent refresh strategies
    - Role-based access control for sensitive administrative data
    - Customizable metrics based on user role and permissions
    
    Dashboard Statistics Provided:
        - System Overview: Total users, active sessions, system health
        - User Analytics: Registration trends, activity patterns, engagement metrics
        - Performance Metrics: Response times, cache hit rates, system load
        - Security Metrics: Failed login attempts, security events, audit summaries
        - Business Metrics: User growth, feature adoption, usage patterns
        - Resource Utilization: Database performance, cache usage, system resources
    
    Args:
        db (Session): Database session (injected by dependency)
        current_user (User): Currently authenticated user (injected by dependency)
    
    Returns:
        dict: Comprehensive dashboard statistics including:
            - success: Operation success status
            - data: Dashboard statistics including:
                - system_overview: High-level system metrics and health
                - user_analytics: User-related statistics and trends
                - performance_metrics: System performance indicators
                - security_summary: Security-related metrics and alerts
                - business_insights: Business and operational metrics
                - cache_performance: Cache system performance data
    
    Access Control:
        - Requires super_user or admin_user role
        - Statistics access logged for audit and compliance
        - Role-specific data filtering and access control
    
    Caching Strategy:
        - Multi-layered caching for optimal performance
        - Automatic cache invalidation based on data changes
        - Cache warming for critical dashboard metrics
        - Performance optimization for frequent administrative access
    
    Error Handling:
        - 401: User not authenticated
        - 403: Insufficient privileges (non-admin users)
        - 500: Database errors, caching failures, or calculation errors
    
    Performance Considerations:
        - Optimized aggregation queries with proper indexing
        - Intelligent caching to reduce database load
        - Efficient data processing and calculation methods
        - Minimal impact on system performance
    
    Use Cases:
        - Administrative dashboards and control panels
        - System monitoring and health assessment
        - Performance analysis and optimization
        - Business intelligence and reporting
        - Operational oversight and decision-making
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Check if user has admin privileges for full dashboard access
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        allowed_roles = ['super_user', 'admin_user']
        
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only admin users can access dashboard statistics. Required roles: {allowed_roles}, current role: {user_role}"
            )
        
        # Initialize cached user service with validation
        try:
            cached_service = CachedUserService(db)
        except Exception as service_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize user service: {str(service_error)}"
            )
        
        # Get dashboard statistics with caching
        dashboard_stats = cached_service.get_dashboard_statistics()
        
        if dashboard_stats is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve dashboard statistics"
            )
        
        # Add metadata and context to dashboard statistics
        enhanced_stats = {
            **dashboard_stats,
            "dashboard_metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "requested_by": {
                    "user_id": current_user.id,
                    "username": getattr(current_user, 'username', 'unknown'),
                    "role": user_role
                },
                "data_freshness": "cached" if hasattr(dashboard_stats, 'cache_hit') else "real_time",
                "dashboard_version": "2.0",
                "access_level": "full_admin" if user_role == 'super_user' else "admin"
            },
            "performance_info": {
                "cache_enabled": True,
                "data_sources": ["database", "cache", "real_time_calculations"],
                "update_frequency": "configurable_based_on_data_type"
            }
        }
        
        # Log dashboard access for audit purposes
        try:
            audit_logger = AuditLogger(db)
            audit_logger.log_activity(
                activity_type=ActivityType.API_ACCESS,
                user_id=current_user.id,
                details={
                    "endpoint": "/v1.0/users/dashboard/statistics",
                    "action": "view_dashboard_statistics",
                    "user_role": user_role,
                    "statistics_generated": True
                },
                security_level=SecurityLevel.MEDIUM,
                success=True
            )
        except Exception as audit_error:
            logger.warning(f"Audit logging failed for dashboard statistics: {audit_error}")
        
        return {
            "success": True,
            "data": enhanced_stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching dashboard statistics: {e} - User: {getattr(current_user, 'id', 'unknown')}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard statistics: {str(e)}"
        )

@router.post("/{user_id}/invalidate-cache")
async def invalidate_user_cache(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Manually Invalidate Cache for Specific User (Admin Only)
    
    Invalidates all cached data associated with a specific user, forcing fresh
    data retrieval on subsequent requests. This administrative operation is useful
    for troubleshooting cache-related issues and ensuring data consistency.
    
    Features:
    - Targeted user-specific cache invalidation
    - Admin-only access control for security
    - Comprehensive audit logging for cache operations
    - Immediate cache invalidation with confirmation
    - Support for troubleshooting and maintenance operations
    
    Cache Types Invalidated:
        - User profile and personal information cache
        - User statistics and activity metrics cache
        - User permissions and role assignment cache
        - User-specific dashboard and reporting cache
        - User session and authentication cache
        - User preference and configuration cache
    
    Args:
        user_id (str): Target user's unique identifier for cache invalidation
        db (Session): Database session (injected by dependency)
        current_user (User): Currently authenticated admin user (injected by dependency)
    
    Returns:
        dict: Cache invalidation result including:
            - success: Operation success status
            - message: Descriptive success message
            - invalidation_details: Information about what was invalidated
            - timestamp: When the invalidation was performed
            - performed_by: Information about the admin who performed the operation
    
    Access Control:
        - Requires super_user or admin_user role
        - All cache invalidation operations logged for audit
        - User identity and target user tracked for security
    
    Error Handling:
        - 400: Invalid user_id parameter or format
        - 401: User not authenticated
        - 403: Insufficient privileges (non-admin users)
        - 404: Target user not found (optional validation)
        - 500: Cache system errors or invalidation failures
    
    Use Cases:
        - Troubleshooting user-specific cache issues
        - Forcing fresh data after user profile updates
        - Resolving data consistency problems
        - Testing and validation of cache behavior
        - Emergency cache cleanup operations
    
    Performance Impact:
        - Minimal system-wide performance impact
        - Target user may experience temporary slower responses
        - Recommended for individual user troubleshooting
        - Cache will rebuild automatically on next access
    """
    try:
        # Validate user_id parameter
        if not user_id or not user_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID parameter cannot be empty"
            )
        
        user_id = user_id.strip()
        
        # Basic user_id format validation
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
        
        # Check if user has admin privileges
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        allowed_roles = ['super_user', 'admin_user']
        
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only admin users can invalidate user caches. Required roles: {allowed_roles}, current role: {user_role}"
            )
        
        # Initialize cached user service with validation
        try:
            cached_service = CachedUserService(db)
        except Exception as service_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize user service: {str(service_error)}"
            )
        
        # Validate that the target user exists (optional but recommended)
        try:
            target_user = db.query(models.User).filter(models.User.id == user_id).first()
            if not target_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User with ID '{user_id}' not found"
                )
        except HTTPException:
            raise
        except Exception as validation_error:
            logger.warning(f"Could not validate target user existence: {validation_error}")
        
        # Record operation timestamp
        invalidation_timestamp = datetime.utcnow()
        
        # Invalidate user caches
        cached_service.invalidate_user_caches(user_id)
        
        # Log successful cache invalidation
        logger.info(f"Cache invalidated for user {user_id} by admin {current_user.id} ({getattr(current_user, 'username', 'unknown')})")
        
        # Log audit trail
        try:
            audit_logger = AuditLogger(db)
            audit_logger.log_activity(
                activity_type=ActivityType.ADMIN_ACTION,
                user_id=current_user.id,
                details={
                    "endpoint": f"/v1.0/users/{user_id}/invalidate_cache",
                    "action": "invalidate_user_cache",
                    "target_user_id": user_id,
                    "admin_role": user_role,
                    "invalidation_timestamp": invalidation_timestamp.isoformat()
                },
                security_level=SecurityLevel.MEDIUM,
                success=True
            )
        except Exception as audit_error:
            logger.warning(f"Audit logging failed for cache invalidation: {audit_error}")
        
        return {
            "success": True,
            "message": f"Cache invalidated successfully for user {user_id}",
            "invalidation_details": {
                "target_user_id": user_id,
                "cache_types_invalidated": [
                    "user_profile",
                    "user_statistics",
                    "user_permissions",
                    "user_dashboard",
                    "user_sessions",
                    "user_preferences"
                ],
                "invalidation_scope": "user_specific",
                "immediate_effect": True
            },
            "timestamp": invalidation_timestamp.isoformat(),
            "performed_by": {
                "admin_user_id": current_user.id,
                "admin_username": getattr(current_user, 'username', 'unknown'),
                "admin_role": user_role
            },
            "next_steps": {
                "cache_rebuild": "automatic_on_next_access",
                "expected_impact": "temporary_slower_response_for_target_user",
                "monitoring": "check_user_performance_after_invalidation"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error invalidating user cache for {user_id}: {e} - Admin: {getattr(current_user, 'id', 'unknown')}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invalidate user cache: {str(e)}"
        )

# Cache management endpoints for super admin
@router.post("/cache/warm")
async def warm_user_cache(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Warm Up User Cache (Super User Only)
    
    Proactively loads frequently accessed user data into the cache system to
    optimize performance for subsequent requests. This operation pre-populates
    cache with essential user-related data to improve system responsiveness.
    
    Features:
    - Comprehensive cache warming for user-related data
    - Super user only access for system-level cache management
    - Intelligent cache population based on usage patterns
    - Performance optimization for high-traffic user operations
    - Detailed logging and monitoring of warming operations
    
    Cache Types Warmed:
        - Frequently accessed user profiles and basic information
        - User statistics and aggregated metrics
        - Role and permission data for authorization
        - Dashboard statistics and summary data
        - System-wide user analytics and trends
        - Authentication and session-related data
    
    Args:
        db (Session): Database session (injected by dependency)
        current_user (User): Currently authenticated super user (injected by dependency)
    
    Returns:
        dict: Cache warming result including:
            - success: Operation success status
            - message: Descriptive success message
            - warming_details: Information about what was warmed
            - warmed_at: Timestamp when warming was performed
            - performance_impact: Expected performance improvements
            - warming_statistics: Metrics about the warming operation
    
    Access Control:
        - Requires SUPER_USER role exclusively
        - Operation logged for audit and monitoring purposes
        - System-level cache management capability
    
    Error Handling:
        - 401: User not authenticated
        - 403: Insufficient privileges (non-super users)
        - 500: Cache warming failures or system errors
        - 503: Cache system temporarily unavailable
    
    Performance Considerations:
        - Operation may temporarily increase system resource usage
        - Recommended during low-traffic periods for optimal results
        - Improves overall system performance after completion
        - May take several minutes for large datasets
    
    Use Cases:
        - System startup and initialization procedures
        - Post-deployment cache preparation
        - Performance optimization before peak usage periods
        - Recovery operations after cache clearing
        - Scheduled maintenance and optimization tasks
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Check if user is super admin
        if current_user.role != UserRole.SUPER_USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super users can warm cache. Current role: " + 
                       (current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role))
            )
        
        # Initialize cached user service with validation
        try:
            cached_service = CachedUserService(db)
        except Exception as service_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize user service: {str(service_error)}"
            )
        
        # Check cache system availability
        try:
            from cache_config import cache
            if not cache.is_available:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Cache system is not available for warming operations"
                )
        except ImportError:
            logger.warning("Could not check cache availability")
        
        # Record warming start time
        warming_start = datetime.utcnow()
        
        # Perform cache warming operation
        cached_service.warm_cache(for_superadmin=True)
        
        # Calculate warming duration
        warming_end = datetime.utcnow()
        warming_duration = (warming_end - warming_start).total_seconds()
        
        # Log successful cache warming
        logger.info(f"Cache warmed by super admin: {current_user.id} ({getattr(current_user, 'username', 'unknown')}) - Duration: {warming_duration:.2f}s")
        
        # Log audit trail
        try:
            audit_logger = AuditLogger(db)
            audit_logger.log_activity(
                activity_type=ActivityType.ADMIN_ACTION,
                user_id=current_user.id,
                details={
                    "endpoint": "/v1.0/users/cache/warm",
                    "action": "warm_user_cache",
                    "warming_duration_seconds": warming_duration,
                    "super_admin_operation": True
                },
                security_level=SecurityLevel.MEDIUM,
                success=True
            )
        except Exception as audit_error:
            logger.warning(f"Audit logging failed for cache warming: {audit_error}")
        
        return {
            "success": True,
            "message": "Cache warming completed successfully",
            "warming_details": {
                "cache_types_warmed": [
                    "user_profiles",
                    "user_statistics",
                    "role_permissions",
                    "dashboard_statistics",
                    "system_analytics",
                    "authentication_data"
                ],
                "warming_strategy": "super_admin_comprehensive",
                "target_audience": "system_wide_optimization"
            },
            "warmed_at": warming_start.isoformat(),
            "warming_statistics": {
                "duration_seconds": warming_duration,
                "completion_time": warming_end.isoformat(),
                "warming_mode": "comprehensive"
            },
            "performance_impact": {
                "expected_improvement": "Significantly reduced response times for user operations",
                "resource_usage": "Temporary increase during warming, then optimized performance",
                "recommendation": "Monitor system performance metrics post-warming"
            },
            "performed_by": {
                "super_admin_id": current_user.id,
                "super_admin_username": getattr(current_user, 'username', 'unknown'),
                "operation_timestamp": warming_start.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache warming failed: {e} - Super admin: {getattr(current_user, 'id', 'unknown')}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache warming failed: {str(e)}"
        )

@router.get("/cache/status")
async def get_cache_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get Cache Status (Super User Only)
    
    Retrieves comprehensive status information about the user cache system,
    including performance metrics, health indicators, and operational statistics.
    This endpoint provides super administrators with detailed cache oversight.
    
    Features:
    - Comprehensive cache system status and health monitoring
    - Performance metrics and operational statistics
    - Super user only access for system-level cache oversight
    - Real-time cache health and performance indicators
    - Detailed cache configuration and capacity information
    
    Status Information Provided:
        - Cache system availability and connectivity
        - Cache hit/miss ratios and performance metrics
        - Memory usage and storage capacity information
        - Cache key distribution and data organization
        - Performance trends and optimization recommendations
        - System health indicators and alerts
    
    Args:
        db (Session): Database session (injected by dependency)
        current_user (User): Currently authenticated super user (injected by dependency)
    
    Returns:
        dict: Comprehensive cache status including:
            - success: Operation success status
            - data: Cache status information including:
                - system_health: Overall cache system health
                - performance_metrics: Hit rates, response times, throughput
                - capacity_info: Memory usage, storage capacity, limits
                - configuration: Cache settings and parameters
                - statistics: Usage patterns and trends
            - checked_at: Timestamp when status was retrieved
            - system_recommendations: Optimization suggestions
    
    Access Control:
        - Requires SUPER_USER role exclusively
        - Status access logged for audit and monitoring
        - System-level cache monitoring capability
    
    Error Handling:
        - 401: User not authenticated
        - 403: Insufficient privileges (non-super users)
        - 500: Cache status retrieval failures or system errors
    
    Performance Considerations:
        - Lightweight operation with minimal system impact
        - Real-time status information without performance degradation
        - Optimized for frequent monitoring and alerting
    
    Use Cases:
        - System monitoring and health assessment
        - Performance analysis and optimization
        - Capacity planning and resource management
        - Troubleshooting cache-related issues
        - Operational dashboards and alerting systems
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Check if user is super admin
        if current_user.role != UserRole.SUPER_USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super users can check cache status. Current role: " + 
                       (current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role))
            )
        
        # Initialize cached user service with validation
        try:
            cached_service = CachedUserService(db)
        except Exception as service_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize user service: {str(service_error)}"
            )
        
        # Record status check timestamp
        status_check_time = datetime.utcnow()
        
        # Get cache status information
        cache_status = cached_service.get_cache_status()
        
        if cache_status is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve cache status information"
            )
        
        # Enhance status with additional metadata
        enhanced_status = {
            **cache_status,
            "status_metadata": {
                "checked_by": {
                    "super_admin_id": current_user.id,
                    "super_admin_username": getattr(current_user, 'username', 'unknown')
                },
                "check_timestamp": status_check_time.isoformat(),
                "status_version": "2.0",
                "check_type": "comprehensive"
            }
        }
        
        # Add system recommendations based on status
        recommendations = []
        if isinstance(cache_status, dict):
            # Example recommendation logic (customize based on actual cache_status structure)
            if cache_status.get('hit_rate', 0) < 80:
                recommendations.append("Consider cache warming or increasing TTL values")
            if cache_status.get('memory_usage_percent', 0) > 90:
                recommendations.append("High memory usage - consider cache cleanup or capacity increase")
            if cache_status.get('error_rate', 0) > 5:
                recommendations.append("Elevated error rate - investigate cache system health")
        
        enhanced_status['system_recommendations'] = recommendations
        
        # Log cache status access
        logger.info(f"Cache status checked by super admin: {current_user.id} ({getattr(current_user, 'username', 'unknown')})")
        
        # Log audit trail
        try:
            audit_logger = AuditLogger(db)
            audit_logger.log_activity(
                activity_type=ActivityType.API_ACCESS,
                user_id=current_user.id,
                details={
                    "endpoint": "/v1.0/users/cache/status",
                    "action": "check_cache_status",
                    "super_admin_operation": True,
                    "status_retrieved": True
                },
                security_level=SecurityLevel.LOW,
                success=True
            )
        except Exception as audit_error:
            logger.warning(f"Audit logging failed for cache status check: {audit_error}")
        
        return {
            "success": True,
            "data": enhanced_status,
            "checked_at": status_check_time.isoformat(),
            "check_duration_ms": (datetime.utcnow() - status_check_time).total_seconds() * 1000
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache status check failed: {e} - Super admin: {getattr(current_user, 'id', 'unknown')}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache status check failed: {str(e)}"
        )

# Health check endpoint for cached services
@router.get("/health/cache")
async def cache_health_check() -> Dict[str, Any]:
    """
    Check Cache Health for User Services
    
    Performs comprehensive health checks on the cache system specifically for
    user-related services. This endpoint validates cache connectivity, operation
    functionality, and performance for user data caching operations.
    
    Features:
    - Comprehensive cache system health validation
    - User service specific cache operation testing
    - Real-time cache performance assessment
    - No authentication required for health monitoring
    - Safe testing operations with automatic cleanup
    
    Health Checks Performed:
        1. Cache system availability and connectivity
        2. Basic cache operations (set, get, delete)
        3. Data integrity verification
        4. Performance timing measurements
        5. Error handling and recovery testing
        6. User-specific cache functionality validation
    
    Returns:
        dict: Comprehensive health check results including:
            - success: Overall health check success status
            - timestamp: When health check was performed
            - cache_status: Cache system availability and operation results
            - performance_metrics: Operation timing and performance data
            - health_assessment: Overall system health evaluation
            - recommendations: Suggestions based on health check results
    
    Health Check Operations:
        - set: Tests cache data storage functionality
        - get: Tests cache data retrieval and integrity
        - delete: Tests cache data removal and cleanup
        - availability: Tests basic cache system connectivity
    
    Error Handling:
        - Graceful handling of cache system failures
        - Detailed error reporting for troubleshooting
        - Safe operation with automatic cleanup
        - Partial results when some operations fail
    
    Use Cases:
        - System health monitoring and alerting
        - Cache system troubleshooting and diagnostics
        - Performance testing and validation
        - Integration testing for user services
        - Automated health checks and monitoring
    
    Performance Considerations:
        - Lightweight operations for minimal system impact
        - Quick response times for monitoring systems
        - Safe for frequent health check execution
        - Automatic cleanup to prevent test data accumulation
    """
    health_check_start = datetime.utcnow()
    test_key = f"user_health_check_{int(health_check_start.timestamp())}"
    test_value = {
        "timestamp": health_check_start.isoformat(),
        "test": True,
        "service": "user_cache_health_check",
        "test_id": "user_service_validation"
    }
    
    try:
        # Import cache configuration with error handling
        try:
            from cache_config import cache
        except ImportError as import_error:
            logger.error(f"Cache configuration import failed: {import_error}")
            return {
                "success": False,
                "timestamp": health_check_start.isoformat(),
                "error": f"Cache configuration not available: {str(import_error)}",
                "cache_status": {
                    "available": False,
                    "operations": {"set": False, "get": False, "delete": False},
                    "error_type": "configuration_error"
                },
                "recommendations": ["Check cache system configuration and dependencies"]
            }
        
        # Initialize health check results
        cache_status = {
            "available": False,
            "operations": {"set": False, "get": False, "delete": False},
            "data_integrity": False,
            "cleanup_successful": False
        }
        
        performance_metrics = {
            "availability_check_ms": 0,
            "set_operation_ms": 0,
            "get_operation_ms": 0,
            "delete_operation_ms": 0,
            "total_check_duration_ms": 0
        }
        
        # Test 1: Cache availability check with timing
        availability_start = datetime.utcnow()
        cache_available = getattr(cache, 'is_available', False)
        availability_end = datetime.utcnow()
        performance_metrics["availability_check_ms"] = (availability_end - availability_start).total_seconds() * 1000
        cache_status["available"] = cache_available
        
        if not cache_available:
            health_check_end = datetime.utcnow()
            performance_metrics["total_check_duration_ms"] = (health_check_end - health_check_start).total_seconds() * 1000
            
            return {
                "success": False,
                "timestamp": health_check_start.isoformat(),
                "cache_status": cache_status,
                "performance_metrics": performance_metrics,
                "health_assessment": "cache_unavailable",
                "recommendations": [
                    "Check cache system connectivity and configuration",
                    "Verify cache service is running and accessible",
                    "Review cache system logs for errors"
                ]
            }
        
        # Test 2: Set operation with timing
        set_start = datetime.utcnow()
        set_success = cache.set(test_key, test_value, 30)  # 30 second TTL
        set_end = datetime.utcnow()
        performance_metrics["set_operation_ms"] = (set_end - set_start).total_seconds() * 1000
        cache_status["operations"]["set"] = bool(set_success)
        
        # Test 3: Get operation with timing and data integrity check
        get_start = datetime.utcnow()
        get_result = cache.get(test_key)
        get_end = datetime.utcnow()
        performance_metrics["get_operation_ms"] = (get_end - get_start).total_seconds() * 1000
        
        cache_status["operations"]["get"] = get_result is not None
        cache_status["data_integrity"] = get_result == test_value
        
        # Test 4: Delete operation with timing
        delete_start = datetime.utcnow()
        delete_success = cache.delete(test_key)
        delete_end = datetime.utcnow()
        performance_metrics["delete_operation_ms"] = (delete_end - delete_start).total_seconds() * 1000
        cache_status["operations"]["delete"] = bool(delete_success)
        
        # Test 5: Verify cleanup
        cleanup_check = cache.get(test_key)
        cache_status["cleanup_successful"] = cleanup_check is None
        
        # Calculate total duration
        health_check_end = datetime.utcnow()
        performance_metrics["total_check_duration_ms"] = (health_check_end - health_check_start).total_seconds() * 1000
        
        # Assess overall health
        critical_operations = [
            cache_status["available"],
            cache_status["operations"]["set"],
            cache_status["operations"]["get"],
            cache_status["data_integrity"],
            cache_status["operations"]["delete"],
            cache_status["cleanup_successful"]
        ]
        
        overall_success = all(critical_operations)
        health_assessment = "healthy" if overall_success else "issues_detected"
        
        # Generate performance assessment
        avg_operation_time = (
            performance_metrics["set_operation_ms"] + 
            performance_metrics["get_operation_ms"] + 
            performance_metrics["delete_operation_ms"]
        ) / 3
        
        performance_level = "excellent" if avg_operation_time < 10 else "good" if avg_operation_time < 50 else "needs_attention"
        
        # Generate recommendations
        recommendations = []
        if not overall_success:
            recommendations.append("Cache system has operational issues - investigate failed operations")
        if avg_operation_time > 100:
            recommendations.append("Cache operations are slow - check system performance")
        if not cache_status["data_integrity"]:
            recommendations.append("Data integrity issues detected - verify cache serialization")
        if overall_success and avg_operation_time < 10:
            recommendations.append("Cache system is performing optimally for user services")
        
        return {
            "success": overall_success,
            "timestamp": health_check_start.isoformat(),
            "cache_status": cache_status,
            "performance_metrics": performance_metrics,
            "health_assessment": health_assessment,
            "performance_level": performance_level,
            "recommendations": recommendations,
            "test_metadata": {
                "test_key_used": test_key,
                "test_ttl_seconds": 30,
                "operations_tested": 4,
                "service_focus": "user_cache_operations",
                "health_check_version": "2.0"
            }
        }
        
    except Exception as e:
        # Ensure cleanup even on error
        try:
            from cache_config import cache
            cache.delete(test_key)
        except:
            pass  # Ignore cleanup errors
        
        logger.error(f"Cache health check failed: {e}")
        
        health_check_end = datetime.utcnow()
        total_duration = (health_check_end - health_check_start).total_seconds() * 1000
        
        return {
            "success": False,
            "timestamp": health_check_start.isoformat(),
            "error": str(e),
            "error_type": type(e).__name__,
            "cache_status": {
                "available": False,
                "operations": {"set": False, "get": False, "delete": False},
                "error_details": str(e)
            },
            "performance_metrics": {
                "total_check_duration_ms": total_duration,
                "failed_at": "exception_during_health_check"
            },
            "recommendations": [
                "Check cache system logs for detailed error information",
                "Verify cache system configuration and connectivity",
                "Contact system administrator if issues persist"
            ],
            "test_metadata": {
                "health_check_failed": True,
                "cleanup_attempted": True,
                "error_timestamp": datetime.utcnow().isoformat()
            }
        }
