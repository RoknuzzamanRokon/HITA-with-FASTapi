"""
Audit Dashboard Routes - View audit logs and security events
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from database import get_db
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel
from routes.auth import get_current_active_user, require_admin
import models

router = APIRouter(
    prefix="/v1.0/audit",
    tags=["Audit Dashboard"],
    dependencies=[Depends(get_current_active_user)]
)

@router.get("/my_activity")
async def get_my_activity(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    days: int = Query(30, description="Number of days to look back"),
    limit: int = Query(50, description="Maximum number of records")
):
    """
    Get Current User's Activity History
    
    Retrieves the activity history for the currently authenticated user. This endpoint
    allows users to view their own audit trail and activity logs within a specified
    time period.
    
    Features:
    - Personal activity history access
    - Configurable time period (days lookback)
    - Configurable result limit for performance
    - Detailed activity information including IP addresses
    - ISO formatted timestamps for consistency
    
    Args:
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)
        days (int): Number of days to look back (default: 30, max recommended: 365)
        limit (int): Maximum number of records to return (default: 50, max recommended: 1000)
    
    Returns:
        dict: User activity data including:
            - user_id: User's unique identifier
            - username: User's username
            - period_days: Number of days covered in the query
            - total_activities: Count of activities returned
            - activities: List of activity objects with details
    
    Activity Object Structure:
        - id: Unique activity record ID
        - action: Type of action performed
        - details: Additional details about the activity
        - ip_address: IP address from which the activity originated
        - created_at: ISO formatted timestamp of the activity
    
    Error Handling:
        - 400: Invalid parameter values (negative days/limit)
        - 401: User not authenticated
        - 500: Database or audit logging system errors
    
    Security:
        - Users can only access their own activity history
        - No sensitive information exposed in activity details
        - IP addresses logged for security auditing
    """
    try:
        # Validate input parameters
        if days < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days parameter must be at least 1"
            )
        
        if days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days parameter cannot exceed 365 for performance reasons"
            )
        
        if limit < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit parameter must be at least 1"
            )
        
        if limit > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit parameter cannot exceed 1000 for performance reasons"
            )
        
        # Initialize audit logger
        audit_logger = AuditLogger(db)
        
        # Get user activity history
        activities = audit_logger.get_user_activity_history(
            user_id=current_user.id,
            days=days,
            limit=limit
        )
        
        return {
            "user_id": current_user.id,
            "username": current_user.username,
            "period_days": days,
            "total_activities": len(activities),
            "activities": [
                {
                    "id": activity.id,
                    "action": activity.action,
                    "details": activity.details,
                    "ip_address": activity.ip_address,
                    "created_at": activity.created_at.isoformat(),
                }
                for activity in activities
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user activity history: {str(e)}"
        )

@router.get("/security_events")
async def get_security_events(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
    days: int = Query(7, description="Number of days to look back"),
    security_level: Optional[SecurityLevel] = Query(None, description="Filter by security level"),
    limit: int = Query(100, description="Maximum number of records")
):
    """
    Get Security Events (Admin Only)
    
    Retrieves security-related events and audit logs for administrative monitoring.
    This endpoint provides comprehensive security event tracking for system administrators
    to monitor potential security threats and suspicious activities.
    
    Features:
    - Admin-only access for security monitoring
    - Configurable time period for event retrieval
    - Security level filtering (LOW, MEDIUM, HIGH, CRITICAL)
    - Comprehensive event details including user agents
    - IP address tracking for security analysis
    
    Args:
        admin: Admin user (injected by dependency, requires admin role)
        db (Session): Database session (injected by dependency)
        days (int): Number of days to look back (default: 7, max: 90)
        security_level (Optional[SecurityLevel]): Filter by security level
        limit (int): Maximum number of records (default: 100, max: 1000)
    
    Returns:
        dict: Security events data including:
            - period_days: Number of days covered in the query
            - security_level_filter: Applied security level filter
            - total_events: Count of security events returned
            - events: List of security event objects
    
    Security Event Object Structure:
        - id: Unique event record ID
        - action: Type of security action/event
        - user_id: ID of user associated with the event
        - details: Detailed information about the security event
        - ip_address: Source IP address of the event
        - user_agent: Browser/client user agent string
        - created_at: ISO formatted timestamp of the event
    
    Security Levels:
        - LOW: Routine security events (successful logins, etc.)
        - MEDIUM: Noteworthy events (password changes, permission changes)
        - HIGH: Concerning events (failed login attempts, unauthorized access)
        - CRITICAL: Severe security events (data breaches, system compromises)
    
    Error Handling:
        - 400: Invalid parameter values
        - 401: User not authenticated
        - 403: User not authorized (non-admin)
        - 500: Database or audit logging system errors
    
    Access Control:
        - Requires admin role for access
        - Provides system-wide security event visibility
    """
    try:
        # Validate input parameters
        if days < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days parameter must be at least 1"
            )
        
        if days > 90:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days parameter cannot exceed 90 for security event queries"
            )
        
        if limit < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit parameter must be at least 1"
            )
        
        if limit > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit parameter cannot exceed 1000 for performance reasons"
            )
        
        # Initialize audit logger
        audit_logger = AuditLogger(db)
        
        # Get security events
        security_events = audit_logger.get_security_events(
            days=days,
            security_level=security_level,
            limit=limit
        )
        
        return {
            "period_days": days,
            "security_level_filter": security_level.value if security_level else "all",
            "total_events": len(security_events),
            "events": [
                {
                    "id": event.id,
                    "action": event.action,
                    "user_id": event.user_id,
                    "details": event.details,
                    "ip_address": event.ip_address,
                    "user_agent": event.user_agent,
                    "created_at": event.created_at.isoformat(),
                }
                for event in security_events
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving security events: {str(e)}"
        )

@router.get("/activity_summary")
async def get_activity_summary(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    days: int = Query(30, description="Number of days to look back")
):
    """
    Get Activity Summary for Current User
    
    Provides a statistical summary of the current user's activities over a specified
    time period. This endpoint offers aggregated insights into user behavior patterns
    and activity trends.
    
    Features:
    - Personal activity statistics and trends
    - Configurable time period for analysis
    - Activity type breakdown and counts
    - Time-based activity patterns
    - Performance metrics and usage statistics
    
    Args:
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)
        days (int): Number of days to analyze (default: 30, max: 365)
    
    Returns:
        dict: Activity summary data including:
            - total_activities: Total number of activities in the period
            - activity_breakdown: Count by activity type
            - daily_activity_trend: Activity counts by day
            - most_active_hours: Peak activity time periods
            - unique_ip_addresses: Number of different IP addresses used
            - activity_types_used: List of activity types performed
    
    Summary Metrics:
        - Activity counts by type (login, API calls, data access, etc.)
        - Temporal patterns (hourly, daily activity distribution)
        - Geographic patterns (based on IP addresses)
        - Usage intensity metrics
    
    Error Handling:
        - 400: Invalid parameter values (negative or excessive days)
        - 401: User not authenticated
        - 500: Database or audit logging system errors
    
    Privacy:
        - Users can only access their own activity summary
        - No sensitive data exposed in aggregated statistics
        - IP addresses are counted but not exposed individually
    """
    try:
        # Validate input parameters
        if days < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days parameter must be at least 1"
            )
        
        if days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days parameter cannot exceed 365 for performance reasons"
            )
        
        # Initialize audit logger
        audit_logger = AuditLogger(db)
        
        # Get activity summary
        summary = audit_logger.get_activity_summary(
            user_id=current_user.id,
            days=days
        )
        
        # Ensure summary is not None and add metadata
        if summary is None:
            summary = {
                "total_activities": 0,
                "activity_breakdown": {},
                "message": "No activity found for the specified period"
            }
        
        # Add metadata to summary
        summary.update({
            "user_id": current_user.id,
            "username": current_user.username,
            "period_days": days,
            "summary_generated_at": datetime.utcnow().isoformat()
        })
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating activity summary: {str(e)}"
        )

@router.get("/system_activity_summary")
async def get_system_activity_summary(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
    days: int = Query(30, description="Number of days to look back")
):
    """
    Get System-Wide Activity Summary (Admin Only)
    
    Provides comprehensive statistical analysis of all system activities across all users
    for administrative monitoring and system health assessment. This endpoint offers
    system-wide insights for capacity planning and security monitoring.
    
    Features:
    - System-wide activity analytics across all users
    - Administrative oversight and monitoring capabilities
    - Comprehensive activity type breakdown
    - User activity distribution and patterns
    - System usage trends and peak periods
    - Security event correlation and analysis
    
    Args:
        admin: Admin user (injected by dependency, requires admin role)
        db (Session): Database session (injected by dependency)
        days (int): Number of days to analyze (default: 30, max: 365)
    
    Returns:
        dict: System-wide activity summary including:
            - total_activities: Total activities across all users
            - total_users_active: Number of active users in period
            - activity_breakdown: Activity counts by type
            - user_activity_distribution: Activity distribution across users
            - peak_activity_periods: Times of highest system usage
            - security_events_summary: Security-related activity overview
            - system_health_metrics: Performance and usage indicators
    
    System Metrics:
        - Total system activity volume
        - User engagement and adoption metrics
        - Activity type distribution (API calls, logins, data access)
        - Geographic distribution of activities
        - Security event frequency and severity
        - System performance indicators
    
    Error Handling:
        - 400: Invalid parameter values
        - 401: User not authenticated
        - 403: User not authorized (non-admin)
        - 500: Database or audit logging system errors
    
    Access Control:
        - Requires admin role for system-wide visibility
        - Provides comprehensive system oversight capabilities
        - Aggregated data to protect individual user privacy
    
    Use Cases:
        - System capacity planning and resource allocation
        - Security monitoring and threat detection
        - User behavior analysis and system optimization
        - Compliance reporting and audit trail maintenance
    """
    try:
        # Validate input parameters
        if days < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days parameter must be at least 1"
            )
        
        if days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days parameter cannot exceed 365 for performance reasons"
            )
        
        # Initialize audit logger
        audit_logger = AuditLogger(db)
        
        # Get system-wide activity summary
        summary = audit_logger.get_activity_summary(
            user_id=None,  # System-wide
            days=days
        )
        
        # Ensure summary is not None and add metadata
        if summary is None:
            summary = {
                "total_activities": 0,
                "total_users_active": 0,
                "activity_breakdown": {},
                "message": "No system activity found for the specified period"
            }
        
        # Add system-wide metadata
        summary.update({
            "scope": "system_wide",
            "period_days": days,
            "summary_generated_at": datetime.utcnow().isoformat(),
            "generated_by_admin": admin.username
        })
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating system activity summary: {str(e)}"
        )

@router.get("/user/{user_id}/activity")
async def get_user_activity(
    user_id: str,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
    days: int = Query(30, description="Number of days to look back"),
    activity_types: Optional[List[str]] = Query(None, description="Filter by activity types"),
    limit: int = Query(100, description="Maximum number of records")
):
    """
    Get Specific User's Activity History (Admin Only)
    
    Retrieves detailed activity history for a specific user, providing administrators
    with comprehensive oversight capabilities for user behavior monitoring, security
    investigations, and compliance auditing.
    
    Features:
    - Admin-only access to any user's activity history
    - Activity type filtering for targeted investigations
    - Comprehensive activity details including user agents
    - Configurable time periods and result limits
    - Support for security investigations and compliance audits
    
    Args:
        user_id (str): Target user's unique identifier
        admin: Admin user (injected by dependency, requires admin role)
        db (Session): Database session (injected by dependency)
        days (int): Number of days to look back (default: 30, max: 365)
        activity_types (Optional[List[str]]): Filter by specific activity types
        limit (int): Maximum number of records (default: 100, max: 1000)
    
    Returns:
        dict: User activity data including:
            - user_id: Target user's identifier
            - period_days: Number of days covered
            - activity_type_filter: Applied activity type filters
            - total_activities: Count of activities returned
            - activities: Detailed list of user activities
            - user_info: Basic information about the target user
    
    Activity Object Structure:
        - id: Unique activity record ID
        - action: Type of action performed by the user
        - details: Comprehensive details about the activity
        - ip_address: Source IP address of the activity
        - user_agent: Browser/client user agent string
        - created_at: ISO formatted timestamp
    
    Activity Type Filtering:
        - LOGIN: User authentication activities
        - API_CALL: API endpoint access and usage
        - DATA_ACCESS: Data retrieval and viewing activities
        - DATA_MODIFICATION: Data creation, update, deletion
        - SECURITY_EVENT: Security-related activities
        - SYSTEM_ACCESS: System-level access and operations
    
    Error Handling:
        - 400: Invalid parameter values or activity types
        - 401: User not authenticated
        - 403: User not authorized (non-admin)
        - 404: Target user not found
        - 500: Database or audit logging system errors
    
    Access Control:
        - Requires admin role for access to other users' data
        - Provides comprehensive user oversight capabilities
        - Maintains detailed audit trail for administrative actions
    
    Use Cases:
        - Security incident investigation
        - User behavior analysis and monitoring
        - Compliance auditing and reporting
        - Troubleshooting user-reported issues
        - Performance analysis and optimization
    """
    try:
        # Validate input parameters
        if not user_id or not user_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID cannot be empty"
            )
        
        if days < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days parameter must be at least 1"
            )
        
        if days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days parameter cannot exceed 365 for performance reasons"
            )
        
        if limit < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit parameter must be at least 1"
            )
        
        if limit > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit parameter cannot exceed 1000 for performance reasons"
            )
        
        # Verify target user exists
        target_user = db.query(models.User).filter(models.User.id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID '{user_id}' not found"
            )
        
        # Initialize audit logger
        audit_logger = AuditLogger(db)
        
        # Convert and validate activity types
        activity_type_enums = None
        if activity_types:
            try:
                activity_type_enums = []
                for at in activity_types:
                    if at in ActivityType.__members__.values():
                        activity_type_enums.append(ActivityType(at))
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid activity type: '{at}'. Valid types: {list(ActivityType.__members__.values())}"
                        )
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error processing activity types: {str(e)}"
                )
        
        # Get user activity history
        activities = audit_logger.get_user_activity_history(
            user_id=user_id,
            days=days,
            activity_types=activity_type_enums,
            limit=limit
        )
        
        return {
            "user_id": user_id,
            "user_info": {
                "username": target_user.username,
                "email": target_user.email,
                "role": target_user.role.value if target_user.role else None,
                "is_active": target_user.is_active
            },
            "period_days": days,
            "activity_type_filter": activity_types,
            "total_activities": len(activities),
            "query_metadata": {
                "queried_by_admin": admin.username,
                "query_timestamp": datetime.utcnow().isoformat(),
                "filters_applied": {
                    "days": days,
                    "activity_types": activity_types,
                    "limit": limit
                }
            },
            "activities": [
                {
                    "id": activity.id,
                    "action": activity.action,
                    "details": activity.details,
                    "ip_address": activity.ip_address,
                    "user_agent": activity.user_agent,
                    "created_at": activity.created_at.isoformat(),
                }
                for activity in activities
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user activity: {str(e)}"
        )

@router.get("/activity_types")
async def get_available_activity_types():
    """
    Get Available Activity Types and Security Levels
    
    Provides a comprehensive list of all available activity types and security levels
    that can be used for filtering and categorizing audit logs and security events.
    This endpoint serves as a reference for other audit dashboard endpoints.
    
    Features:
    - Complete enumeration of activity types
    - Security level definitions and descriptions
    - Reference data for filtering other endpoints
    - System configuration and capability discovery
    
    Returns:
        dict: Available types and levels including:
            - activity_types: List of all available activity types
            - security_levels: List of all security levels
            - activity_type_descriptions: Detailed descriptions of each activity type
            - security_level_descriptions: Detailed descriptions of each security level
            - usage_examples: Examples of how to use these types in other endpoints
    
    Activity Types:
        - LOGIN: User authentication and session management
        - API_CALL: API endpoint access and usage
        - DATA_ACCESS: Data retrieval and viewing operations
        - DATA_MODIFICATION: Data creation, update, and deletion
        - SECURITY_EVENT: Security-related activities and alerts
        - SYSTEM_ACCESS: System-level operations and access
        - ADMIN_ACTION: Administrative operations and changes
        - USER_MANAGEMENT: User account and permission changes
    
    Security Levels:
        - LOW: Routine operations with minimal security impact
        - MEDIUM: Standard operations requiring basic monitoring
        - HIGH: Sensitive operations requiring enhanced monitoring
        - CRITICAL: High-risk operations requiring immediate attention
    
    Error Handling:
        - 500: System configuration or enum processing errors
    
    Use Cases:
        - Frontend dropdown population for filtering
        - API client configuration and validation
        - Documentation and system capability discovery
        - Audit log categorization and analysis
    """
    try:
        # Get activity types with descriptions
        activity_type_info = {
            "LOGIN": "User authentication and session management activities",
            "API_CALL": "API endpoint access and usage tracking",
            "DATA_ACCESS": "Data retrieval and viewing operations",
            "DATA_MODIFICATION": "Data creation, update, and deletion operations",
            "SECURITY_EVENT": "Security-related activities and alerts",
            "SYSTEM_ACCESS": "System-level operations and access",
            "ADMIN_ACTION": "Administrative operations and system changes",
            "USER_MANAGEMENT": "User account and permission management"
        }
        
        # Get security levels with descriptions
        security_level_info = {
            "LOW": "Routine operations with minimal security impact",
            "MEDIUM": "Standard operations requiring basic monitoring",
            "HIGH": "Sensitive operations requiring enhanced monitoring",
            "CRITICAL": "High-risk operations requiring immediate attention"
        }
        
        # Get available enum values
        available_activity_types = [activity_type.value for activity_type in ActivityType]
        available_security_levels = [level.value for level in SecurityLevel]
        
        return {
            "activity_types": available_activity_types,
            "security_levels": available_security_levels,
            "activity_type_descriptions": {
                activity_type: activity_type_info.get(activity_type, "No description available")
                for activity_type in available_activity_types
            },
            "security_level_descriptions": {
                level: security_level_info.get(level, "No description available")
                for level in available_security_levels
            },
            "usage_examples": {
                "filter_by_activity_type": "Use activity_types parameter in other endpoints",
                "filter_by_security_level": "Use security_level parameter in security events endpoint",
                "example_activity_filter": f"?activity_types={available_activity_types[0]}&activity_types={available_activity_types[1] if len(available_activity_types) > 1 else available_activity_types[0]}",
                "example_security_filter": f"?security_level={available_security_levels[0] if available_security_levels else 'LOW'}"
            },
            "metadata": {
                "total_activity_types": len(available_activity_types),
                "total_security_levels": len(available_security_levels),
                "last_updated": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving activity types and security levels: {str(e)}"
        )