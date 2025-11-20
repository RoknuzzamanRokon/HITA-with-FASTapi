"""
Audit Dashboard API Routes

Provides analytics and visualization-ready data for audit logs
"""

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case
from typing import Annotated, Optional, List
from datetime import datetime, timedelta
import models
from database import get_db
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel
from routes.auth import get_current_user
from security.middleware import validate_user_permissions

router = APIRouter(
    prefix="/v1.0",
    tags=["Audit Analytics"]
)


@router.get("/audit/analytics")
async def get_audit_analytics(
    request: Request,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    user_id: Optional[str] = Query(None, description="Filter by specific user ID"),
):
    """
    Get audit analytics data optimized for frontend graphs and visualizations
    
    Returns:
    - Activity timeline (daily counts)
    - Activity breakdown by type
    - Security events summary
    - Top active users
    - Authentication statistics
    - User management statistics
    """
    
    # Validate permissions - only admin and super users can access audit analytics
    validate_user_permissions(current_user, [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER])
    
    audit_logger = AuditLogger(db)
    
    # Calculate date range
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Base query
    base_query = db.query(models.UserActivityLog).filter(
        models.UserActivityLog.created_at >= start_date
    )
    
    # Apply user filter if specified
    if user_id:
        base_query = base_query.filter(models.UserActivityLog.user_id == user_id)
    
    # 1. Daily Activity Timeline (for line/area chart)
    daily_activity = db.query(
        func.date(models.UserActivityLog.created_at).label('date'),
        func.count(models.UserActivityLog.id).label('count')
    ).filter(
        models.UserActivityLog.created_at >= start_date
    )
    
    if user_id:
        daily_activity = daily_activity.filter(models.UserActivityLog.user_id == user_id)
    
    daily_activity = daily_activity.group_by(
        func.date(models.UserActivityLog.created_at)
    ).order_by(func.date(models.UserActivityLog.created_at)).all()
    
    # 2. Activity Breakdown by Type (for pie/donut chart)
    activity_by_type = db.query(
        models.UserActivityLog.action,
        func.count(models.UserActivityLog.id).label('count')
    ).filter(
        models.UserActivityLog.created_at >= start_date
    )
    
    if user_id:
        activity_by_type = activity_by_type.filter(models.UserActivityLog.user_id == user_id)
    
    activity_by_type = activity_by_type.group_by(
        models.UserActivityLog.action
    ).order_by(desc('count')).all()
    
    # 3. Security Events (for alert dashboard)
    security_activity_types = [
        ActivityType.UNAUTHORIZED_ACCESS_ATTEMPT.value,
        ActivityType.RATE_LIMIT_EXCEEDED.value,
        ActivityType.SUSPICIOUS_ACTIVITY.value,
        ActivityType.ACCOUNT_LOCKED.value,
        ActivityType.LOGIN_FAILED.value
    ]
    
    security_events = db.query(
        models.UserActivityLog.action,
        func.count(models.UserActivityLog.id).label('count')
    ).filter(
        models.UserActivityLog.created_at >= start_date,
        models.UserActivityLog.action.in_(security_activity_types)
    )
    
    if user_id:
        security_events = security_events.filter(models.UserActivityLog.user_id == user_id)
    
    security_events = security_events.group_by(
        models.UserActivityLog.action
    ).all()
    
    # 4. Top Active Users (for leaderboard/bar chart)
    top_users = []
    if not user_id:  # Only show if not filtering by specific user
        top_users_query = db.query(
            models.UserActivityLog.user_id,
            models.User.username,
            models.User.email,
            func.count(models.UserActivityLog.id).label('activity_count')
        ).join(
            models.User, models.UserActivityLog.user_id == models.User.id
        ).filter(
            models.UserActivityLog.created_at >= start_date,
            models.UserActivityLog.user_id.isnot(None)
        ).group_by(
            models.UserActivityLog.user_id,
            models.User.username,
            models.User.email
        ).order_by(desc('activity_count')).limit(10).all()
        
        top_users = [
            {
                "user_id": row.user_id,
                "username": row.username,
                "email": row.email,
                "activity_count": row.activity_count
            }
            for row in top_users_query
        ]
    
    # 5. Authentication Statistics (for stats cards)
    auth_stats = db.query(
        func.sum(case((models.UserActivityLog.action == ActivityType.LOGIN_SUCCESS.value, 1), else_=0)).label('successful_logins'),
        func.sum(case((models.UserActivityLog.action == ActivityType.LOGIN_FAILED.value, 1), else_=0)).label('failed_logins'),
        func.sum(case((models.UserActivityLog.action == ActivityType.LOGOUT.value, 1), else_=0)).label('logouts'),
        func.sum(case((models.UserActivityLog.action == ActivityType.PASSWORD_RESET_REQUEST.value, 1), else_=0)).label('password_resets')
    ).filter(
        models.UserActivityLog.created_at >= start_date
    )
    
    if user_id:
        auth_stats = auth_stats.filter(models.UserActivityLog.user_id == user_id)
    
    auth_stats = auth_stats.first()
    
    # 6. User Management Statistics (for stats cards)
    user_mgmt_stats = db.query(
        func.sum(case((models.UserActivityLog.action == ActivityType.USER_CREATED.value, 1), else_=0)).label('users_created'),
        func.sum(case((models.UserActivityLog.action == ActivityType.USER_UPDATED.value, 1), else_=0)).label('users_updated'),
        func.sum(case((models.UserActivityLog.action == ActivityType.USER_DELETED.value, 1), else_=0)).label('users_deleted'),
        func.sum(case((models.UserActivityLog.action == ActivityType.USER_ROLE_CHANGED.value, 1), else_=0)).label('role_changes')
    ).filter(
        models.UserActivityLog.created_at >= start_date
    )
    
    if user_id:
        user_mgmt_stats = user_mgmt_stats.filter(models.UserActivityLog.user_id == user_id)
    
    user_mgmt_stats = user_mgmt_stats.first()
    
    # 7. Hourly Activity Pattern (for heatmap)
    hourly_pattern = db.query(
        func.extract('hour', models.UserActivityLog.created_at).label('hour'),
        func.count(models.UserActivityLog.id).label('count')
    ).filter(
        models.UserActivityLog.created_at >= start_date
    )
    
    if user_id:
        hourly_pattern = hourly_pattern.filter(models.UserActivityLog.user_id == user_id)
    
    hourly_pattern = hourly_pattern.group_by(
        func.extract('hour', models.UserActivityLog.created_at)
    ).order_by('hour').all()
    
    # 8. Recent Critical Events (for alerts)
    recent_critical = db.query(models.UserActivityLog).filter(
        models.UserActivityLog.created_at >= start_date,
        models.UserActivityLog.action.in_(security_activity_types)
    )
    
    if user_id:
        recent_critical = recent_critical.filter(models.UserActivityLog.user_id == user_id)
    
    recent_critical = recent_critical.order_by(
        desc(models.UserActivityLog.created_at)
    ).limit(10).all()
    
    # Log this analytics access
    audit_logger.log_activity(
        activity_type=ActivityType.DATA_EXPORT,
        user_id=current_user.id,
        details={
            'action': 'audit_analytics_access',
            'days_requested': days,
            'filtered_user_id': user_id
        },
        request=request,
        security_level=SecurityLevel.LOW
    )
    
    # Build response
    return {
        "period": {
            "days": days,
            "start_date": start_date.isoformat(),
            "end_date": datetime.utcnow().isoformat()
        },
        "filter": {
            "user_id": user_id
        },
        "summary": {
            "total_activities": base_query.count(),
            "total_security_events": sum(row.count for row in security_events),
            "unique_users": db.query(func.count(func.distinct(models.UserActivityLog.user_id))).filter(
                models.UserActivityLog.created_at >= start_date,
                models.UserActivityLog.user_id.isnot(None)
            ).scalar() if not user_id else 1
        },
        "timeline": {
            "daily_activity": [
                {
                    "date": row.date.isoformat(),
                    "count": row.count
                }
                for row in daily_activity
            ]
        },
        "activity_breakdown": {
            "by_type": [
                {
                    "action": row.action,
                    "count": row.count,
                    "percentage": round((row.count / base_query.count() * 100), 2) if base_query.count() > 0 else 0
                }
                for row in activity_by_type
            ]
        },
        "security": {
            "events_by_type": [
                {
                    "action": row.action,
                    "count": row.count
                }
                for row in security_events
            ],
            "recent_critical_events": [
                {
                    "id": log.id,
                    "action": log.action,
                    "user_id": log.user_id,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at.isoformat(),
                    "details": log.details
                }
                for log in recent_critical
            ]
        },
        "authentication": {
            "successful_logins": auth_stats.successful_logins or 0,
            "failed_logins": auth_stats.failed_logins or 0,
            "logouts": auth_stats.logouts or 0,
            "password_resets": auth_stats.password_resets or 0,
            "success_rate": round(
                (auth_stats.successful_logins / (auth_stats.successful_logins + auth_stats.failed_logins) * 100)
                if (auth_stats.successful_logins or 0) + (auth_stats.failed_logins or 0) > 0 else 0,
                2
            )
        },
        "user_management": {
            "users_created": user_mgmt_stats.users_created or 0,
            "users_updated": user_mgmt_stats.users_updated or 0,
            "users_deleted": user_mgmt_stats.users_deleted or 0,
            "role_changes": user_mgmt_stats.role_changes or 0
        },
        "patterns": {
            "hourly_distribution": [
                {
                    "hour": int(row.hour),
                    "count": row.count
                }
                for row in hourly_pattern
            ]
        },
        "top_users": top_users
    }


@router.get("/audit/user-activity/{user_id}")
async def get_user_activity_graph(
    request: Request,
    user_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
):
    """
    Get specific user's activity data optimized for graphs
    
    Returns activity timeline and breakdown for a single user
    """
    
    # Validate permissions
    validate_user_permissions(current_user, [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER])
    
    # Verify user exists
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    audit_logger = AuditLogger(db)
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get daily activity
    daily_activity = db.query(
        func.date(models.UserActivityLog.created_at).label('date'),
        func.count(models.UserActivityLog.id).label('count')
    ).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.created_at >= start_date
    ).group_by(
        func.date(models.UserActivityLog.created_at)
    ).order_by(func.date(models.UserActivityLog.created_at)).all()
    
    # Get activity by type
    activity_by_type = db.query(
        models.UserActivityLog.action,
        func.count(models.UserActivityLog.id).label('count')
    ).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.created_at >= start_date
    ).group_by(
        models.UserActivityLog.action
    ).order_by(desc('count')).all()
    
    # Get recent activities
    recent_activities = db.query(models.UserActivityLog).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.created_at >= start_date
    ).order_by(desc(models.UserActivityLog.created_at)).limit(20).all()
    
    # Log access
    audit_logger.log_activity(
        activity_type=ActivityType.DATA_EXPORT,
        user_id=current_user.id,
        details={
            'action': 'user_activity_graph_access',
            'target_user_id': user_id,
            'days_requested': days
        },
        request=request,
        security_level=SecurityLevel.LOW
    )
    
    return {
        "user": {
            "id": target_user.id,
            "username": target_user.username,
            "email": target_user.email,
            "role": target_user.role
        },
        "period": {
            "days": days,
            "start_date": start_date.isoformat(),
            "end_date": datetime.utcnow().isoformat()
        },
        "timeline": [
            {
                "date": row.date.isoformat(),
                "count": row.count
            }
            for row in daily_activity
        ],
        "activity_breakdown": [
            {
                "action": row.action,
                "count": row.count
            }
            for row in activity_by_type
        ],
        "recent_activities": [
            {
                "id": log.id,
                "action": log.action,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat(),
                "details": log.details
            }
            for log in recent_activities
        ],
        "total_activities": sum(row.count for row in activity_by_type)
    }


@router.get("/audit/my-activity")
async def get_my_activity(
    request: Request,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
):
    """
    Get current user's own activity data (available to ALL users)
    
    Any authenticated user can view their own activity history and statistics.
    This endpoint provides a personal dashboard of user activity.
    """
    
    audit_logger = AuditLogger(db)
    start_date = datetime.utcnow() - timedelta(days=days)
    user_id = current_user.id
    
    # Get daily activity
    daily_activity = db.query(
        func.date(models.UserActivityLog.created_at).label('date'),
        func.count(models.UserActivityLog.id).label('count')
    ).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.created_at >= start_date
    ).group_by(
        func.date(models.UserActivityLog.created_at)
    ).order_by(func.date(models.UserActivityLog.created_at)).all()
    
    # Get activity by type
    activity_by_type = db.query(
        models.UserActivityLog.action,
        func.count(models.UserActivityLog.id).label('count')
    ).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.created_at >= start_date
    ).group_by(
        models.UserActivityLog.action
    ).order_by(desc('count')).all()
    
    # Get recent activities (limit sensitive details)
    recent_activities = db.query(models.UserActivityLog).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.created_at >= start_date
    ).order_by(desc(models.UserActivityLog.created_at)).limit(50).all()
    
    # Authentication stats for this user
    auth_stats = db.query(
        func.sum(case((models.UserActivityLog.action == ActivityType.LOGIN_SUCCESS.value, 1), else_=0)).label('successful_logins'),
        func.sum(case((models.UserActivityLog.action == ActivityType.LOGIN_FAILED.value, 1), else_=0)).label('failed_logins'),
        func.sum(case((models.UserActivityLog.action == ActivityType.LOGOUT.value, 1), else_=0)).label('logouts')
    ).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.created_at >= start_date
    ).first()
    
    # Hourly pattern
    hourly_pattern = db.query(
        func.extract('hour', models.UserActivityLog.created_at).label('hour'),
        func.count(models.UserActivityLog.id).label('count')
    ).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.created_at >= start_date
    ).group_by(
        func.extract('hour', models.UserActivityLog.created_at)
    ).order_by('hour').all()
    
    # Most active day
    most_active_day = db.query(
        func.date(models.UserActivityLog.created_at).label('date'),
        func.count(models.UserActivityLog.id).label('count')
    ).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.created_at >= start_date
    ).group_by(
        func.date(models.UserActivityLog.created_at)
    ).order_by(desc('count')).first()
    
    # Log this access
    audit_logger.log_activity(
        activity_type=ActivityType.API_ACCESS,
        user_id=current_user.id,
        details={
            'action': 'my_activity_access',
            'days_requested': days
        },
        request=request,
        security_level=SecurityLevel.LOW
    )
    
    total_activities = sum(row.count for row in activity_by_type)
    
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role,
            "account_created": current_user.created_at.isoformat() if current_user.created_at else None
        },
        "period": {
            "days": days,
            "start_date": start_date.isoformat(),
            "end_date": datetime.utcnow().isoformat()
        },
        "summary": {
            "total_activities": total_activities,
            "average_daily_activities": round(total_activities / days, 2) if days > 0 else 0,
            "most_active_day": {
                "date": most_active_day.date.isoformat() if most_active_day else None,
                "count": most_active_day.count if most_active_day else 0
            }
        },
        "timeline": [
            {
                "date": row.date.isoformat(),
                "count": row.count
            }
            for row in daily_activity
        ],
        "activity_breakdown": [
            {
                "action": row.action,
                "action_label": row.action.replace('_', ' ').title(),
                "count": row.count,
                "percentage": round((row.count / total_activities * 100), 2) if total_activities > 0 else 0
            }
            for row in activity_by_type
        ],
        "authentication": {
            "successful_logins": auth_stats.successful_logins or 0,
            "failed_logins": auth_stats.failed_logins or 0,
            "logouts": auth_stats.logouts or 0,
            "success_rate": round(
                (auth_stats.successful_logins / (auth_stats.successful_logins + auth_stats.failed_logins) * 100)
                if (auth_stats.successful_logins or 0) + (auth_stats.failed_logins or 0) > 0 else 100,
                2
            )
        },
        "patterns": {
            "hourly_distribution": [
                {
                    "hour": int(row.hour),
                    "hour_label": f"{int(row.hour):02d}:00",
                    "count": row.count
                }
                for row in hourly_pattern
            ],
            "most_active_hour": max(hourly_pattern, key=lambda x: x.count).hour if hourly_pattern else None
        },
        "recent_activities": [
            {
                "id": log.id,
                "action": log.action,
                "action_label": log.action.replace('_', ' ').title(),
                "created_at": log.created_at.isoformat(),
                "ip_address": log.ip_address,
                "details": log.details
            }
            for log in recent_activities
        ]
    }


@router.get("/audit/my-stats")
async def get_my_stats(
    request: Request,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get quick stats summary for current user (available to ALL users)
    
    Returns a lightweight summary of user activity statistics.
    Perfect for dashboard widgets and quick overview cards.
    """
    
    user_id = current_user.id
    
    # Last 7 days
    last_7_days = datetime.utcnow() - timedelta(days=7)
    # Last 30 days
    last_30_days = datetime.utcnow() - timedelta(days=30)
    # All time
    
    # Activity counts
    activities_7_days = db.query(func.count(models.UserActivityLog.id)).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.created_at >= last_7_days
    ).scalar() or 0
    
    activities_30_days = db.query(func.count(models.UserActivityLog.id)).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.created_at >= last_30_days
    ).scalar() or 0
    
    activities_all_time = db.query(func.count(models.UserActivityLog.id)).filter(
        models.UserActivityLog.user_id == user_id
    ).scalar() or 0
    
    # Last login
    last_login = db.query(models.UserActivityLog).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.action == ActivityType.LOGIN_SUCCESS.value
    ).order_by(desc(models.UserActivityLog.created_at)).first()
    
    # Most common action
    most_common_action = db.query(
        models.UserActivityLog.action,
        func.count(models.UserActivityLog.id).label('count')
    ).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.created_at >= last_30_days
    ).group_by(
        models.UserActivityLog.action
    ).order_by(desc('count')).first()
    
    # Failed login attempts (security indicator)
    failed_logins_7_days = db.query(func.count(models.UserActivityLog.id)).filter(
        models.UserActivityLog.user_id == user_id,
        models.UserActivityLog.action == ActivityType.LOGIN_FAILED.value,
        models.UserActivityLog.created_at >= last_7_days
    ).scalar() or 0
    
    # Account age
    account_age_days = (datetime.utcnow() - current_user.created_at).days if current_user.created_at else 0
    
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "account_age_days": account_age_days
        },
        "activity_summary": {
            "last_7_days": activities_7_days,
            "last_30_days": activities_30_days,
            "all_time": activities_all_time,
            "daily_average_30_days": round(activities_30_days / 30, 2)
        },
        "last_login": {
            "timestamp": last_login.created_at.isoformat() if last_login else None,
            "ip_address": last_login.ip_address if last_login else None,
            "days_ago": (datetime.utcnow() - last_login.created_at).days if last_login else None
        },
        "most_common_action": {
            "action": most_common_action.action if most_common_action else None,
            "action_label": most_common_action.action.replace('_', ' ').title() if most_common_action else None,
            "count": most_common_action.count if most_common_action else 0
        },
        "security": {
            "failed_login_attempts_7_days": failed_logins_7_days,
            "status": "warning" if failed_logins_7_days > 3 else "good"
        }
    }


@router.get("/audit/my-timeline")
async def get_my_timeline(
    request: Request,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(100, ge=1, le=500, description="Number of activities to retrieve"),
    action_filter: Optional[str] = Query(None, description="Filter by action type"),
):
    """
    Get current user's activity timeline (available to ALL users)
    
    Returns a chronological list of user activities with filtering options.
    Perfect for activity feed components.
    """
    
    user_id = current_user.id
    
    # Build query
    query = db.query(models.UserActivityLog).filter(
        models.UserActivityLog.user_id == user_id
    )
    
    # Apply action filter if provided
    if action_filter:
        query = query.filter(models.UserActivityLog.action == action_filter)
    
    # Get activities
    activities = query.order_by(
        desc(models.UserActivityLog.created_at)
    ).limit(limit).all()
    
    # Get available action types for this user
    available_actions = db.query(
        models.UserActivityLog.action,
        func.count(models.UserActivityLog.id).label('count')
    ).filter(
        models.UserActivityLog.user_id == user_id
    ).group_by(
        models.UserActivityLog.action
    ).all()
    
    return {
        "user_id": user_id,
        "total_returned": len(activities),
        "filter_applied": action_filter,
        "available_actions": [
            {
                "action": row.action,
                "action_label": row.action.replace('_', ' ').title(),
                "count": row.count
            }
            for row in available_actions
        ],
        "timeline": [
            {
                "id": log.id,
                "action": log.action,
                "action_label": log.action.replace('_', ' ').title(),
                "timestamp": log.created_at.isoformat(),
                "time_ago": _format_time_ago(log.created_at),
                "ip_address": log.ip_address,
                "details": log.details
            }
            for log in activities
        ]
    }


def _format_time_ago(timestamp: datetime) -> str:
    """Helper function to format timestamp as 'time ago' string"""
    now = datetime.utcnow()
    diff = now - timestamp
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "just now"
