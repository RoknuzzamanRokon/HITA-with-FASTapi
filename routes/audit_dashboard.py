"""
Audit Dashboard Routes - View audit logs and security events
"""

from fastapi import APIRouter, Depends, Query
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

@router.get("/my-activity")
async def get_my_activity(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    days: int = Query(30, description="Number of days to look back"),
    limit: int = Query(50, description="Maximum number of records")
):
    """Get current user's activity history"""
    
    audit_logger = AuditLogger(db)
    
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

@router.get("/security-events")
async def get_security_events(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
    days: int = Query(7, description="Number of days to look back"),
    security_level: Optional[SecurityLevel] = Query(None, description="Filter by security level"),
    limit: int = Query(100, description="Maximum number of records")
):
    """Get security events (admin only)"""
    
    audit_logger = AuditLogger(db)
    
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

@router.get("/activity-summary")
async def get_activity_summary(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    days: int = Query(30, description="Number of days to look back")
):
    """Get activity summary for current user"""
    
    audit_logger = AuditLogger(db)
    
    summary = audit_logger.get_activity_summary(
        user_id=current_user.id,
        days=days
    )
    
    return summary

@router.get("/system-summary")
async def get_system_activity_summary(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
    days: int = Query(30, description="Number of days to look back")
):
    """Get system-wide activity summary (admin only)"""
    
    audit_logger = AuditLogger(db)
    
    summary = audit_logger.get_activity_summary(
        user_id=None,  # System-wide
        days=days
    )
    
    return summary

@router.get("/user/{user_id}/activity")
async def get_user_activity(
    user_id: str,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
    days: int = Query(30, description="Number of days to look back"),
    activity_types: Optional[List[str]] = Query(None, description="Filter by activity types"),
    limit: int = Query(100, description="Maximum number of records")
):
    """Get specific user's activity (admin only)"""
    
    audit_logger = AuditLogger(db)
    
    # Convert string activity types to enum
    activity_type_enums = None
    if activity_types:
        activity_type_enums = [ActivityType(at) for at in activity_types if at in ActivityType.__members__.values()]
    
    activities = audit_logger.get_user_activity_history(
        user_id=user_id,
        days=days,
        activity_types=activity_type_enums,
        limit=limit
    )
    
    return {
        "user_id": user_id,
        "period_days": days,
        "activity_type_filter": activity_types,
        "total_activities": len(activities),
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

@router.get("/activity-types")
async def get_available_activity_types():
    """Get list of all available activity types"""
    
    return {
        "activity_types": [activity_type.value for activity_type in ActivityType],
        "security_levels": [level.value for level in SecurityLevel]
    }