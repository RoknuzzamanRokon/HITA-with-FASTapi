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
    Get your own activity history and audit trail.
    
    **What it does:**
    Shows your personal activity history including logins, API calls, and actions.
    
    **Parameters:**
    - `days` - How many days back to look (default: 30, max: 365)
    - `limit` - Max number of records (default: 50, max: 1000)
    
    **Response includes:**
    - Your activity list with timestamps
    - Action types and details
    - IP addresses used
    - Total activity count
    
    **Example usage:**
    `/my_activity?days=7&limit=20` - Get last 7 days, max 20 records
    
    **Example response:**
    ```json
    {
        "user_id": "user123",
        "username": "john_doe",
        "total_activities": 15,
        "activities": [
            {
                "action": "LOGIN",
                "details": "Successful login",
                "ip_address": "192.168.1.100",
                "created_at": "2024-01-15T10:30:00"
            }
        ]
    }
    ```
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
    Get security events and threats (Admin only).
    
    **What it does:**
    Shows security-related events like failed logins, suspicious activities, and threats.
    
    **Who can use:**
    - Admin users only
    
    **Parameters:**
    - `days` - How many days back to look (default: 7, max: 90)
    - `security_level` - Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)
    - `limit` - Max number of records (default: 100, max: 1000)
    
    **Security levels:**
    - LOW: Normal events (successful logins)
    - MEDIUM: Notable events (password changes)
    - HIGH: Concerning events (failed logins)
    - CRITICAL: Severe events (data breaches)
    
    **Example usage:**
    `/security_events?days=3&security_level=HIGH` - Get high-severity events from last 3 days
    
    **Example response:**
    ```json
    {
        "period_days": 7,
        "security_level_filter": "HIGH",
        "total_events": 5,
        "events": [
            {
                "action": "FAILED_LOGIN",
                "user_id": "user123",
                "ip_address": "192.168.1.100",
                "details": "Multiple failed login attempts"
            }
        ]
    }
    ```
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
    Get your activity summary and statistics.
    
    **What it does:**
    Shows a statistical summary of your activities with breakdowns and trends.
    
    **Parameters:**
    - `days` - How many days to analyze (default: 30, max: 365)
    
    **Response includes:**
    - Total activity count
    - Activity breakdown by type (logins, API calls, etc.)
    - Daily activity trends
    - Peak activity hours
    - Number of unique IP addresses used
    
    **Example usage:**
    `/activity_summary?days=14` - Get 2-week activity summary
    
    **Example response:**
    ```json
    {
        "total_activities": 150,
        "activity_breakdown": {
            "LOGIN": 25,
            "API_CALL": 100,
            "DATA_ACCESS": 25
        },
        "daily_activity_trend": [
            {"date": "2024-01-01", "count": 10}
        ],
        "most_active_hours": [9, 14, 16],
        "unique_ip_addresses": 3
    }
    ```
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
    Get system-wide activity summary (Admin only).
    
    **What it does:**
    Shows activity statistics across all users for system monitoring and health assessment.
    
    **Who can use:**
    - Admin users only
    
    **Parameters:**
    - `days` - How many days to analyze (default: 30, max: 365)
    
    **Response includes:**
    - Total system activities
    - Number of active users
    - Activity breakdown by type
    - User activity distribution
    - Peak usage periods
    - Security events overview
    
    **Use cases:**
    - System capacity planning
    - Security monitoring
    - User behavior analysis
    - Compliance reporting
    
    **Example response:**
    ```json
    {
        "total_activities": 5000,
        "total_users_active": 150,
        "activity_breakdown": {
            "LOGIN": 500,
            "API_CALL": 3500,
            "DATA_ACCESS": 1000
        },
        "peak_activity_periods": ["09:00", "14:00", "16:00"],
        "security_events_summary": {
            "total": 25,
            "critical": 2,
            "high": 8
        }
    }
    ```
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
    Get any user's activity history (Admin only).
    
    **What it does:**
    Shows detailed activity history for a specific user for investigations and monitoring.
    
    **Who can use:**
    - Admin users only
    
    **Parameters:**
    - `user_id` - Target user's ID (required)
    - `days` - How many days back to look (default: 30, max: 365)
    - `activity_types` - Filter by specific types (LOGIN, API_CALL, etc.)
    - `limit` - Max number of records (default: 100, max: 1000)
    
    **Activity types:**
    - LOGIN: User authentication
    - API_CALL: API endpoint usage
    - DATA_ACCESS: Data viewing
    - DATA_MODIFICATION: Data changes
    - SECURITY_EVENT: Security activities
    
    **Use cases:**
    - Security investigations
    - User behavior monitoring
    - Compliance auditing
    - Troubleshooting issues
    
    **Example usage:**
    `/user/user123/activity?days=7&activity_types=LOGIN&activity_types=SECURITY_EVENT`
    
    **Example response:**
    ```json
    {
        "user_id": "user123",
        "user_info": {
            "username": "john_doe",
            "email": "john@example.com",
            "role": "GENERAL_USER"
        },
        "total_activities": 25,
        "activities": [
            {
                "action": "LOGIN",
                "details": "Successful login",
                "ip_address": "192.168.1.100",
                "created_at": "2024-01-15T10:30:00"
            }
        ]
    }
    ```
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
    Get available activity types and security levels for filtering.
    
    **What it does:**
    Shows all available activity types and security levels you can use to filter other endpoints.
    
    **Response includes:**
    - All activity types with descriptions
    - All security levels with descriptions
    - Usage examples for filtering
    
    **Activity types:**
    - LOGIN: User authentication
    - API_CALL: API endpoint usage
    - DATA_ACCESS: Data viewing
    - DATA_MODIFICATION: Data changes
    - SECURITY_EVENT: Security activities
    - SYSTEM_ACCESS: System operations
    - ADMIN_ACTION: Admin operations
    - USER_MANAGEMENT: User account changes
    
    **Security levels:**
    - LOW: Routine operations
    - MEDIUM: Standard operations
    - HIGH: Sensitive operations
    - CRITICAL: High-risk operations
    
    **Use cases:**
    - Populate filter dropdowns
    - API client configuration
    - Understanding available filters
    
    **Example response:**
    ```json
    {
        "activity_types": ["LOGIN", "API_CALL", "DATA_ACCESS"],
        "security_levels": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        "activity_type_descriptions": {
            "LOGIN": "User authentication and session management"
        },
        "usage_examples": {
            "example_activity_filter": "?activity_types=LOGIN&activity_types=API_CALL"
        }
    }
    ```
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