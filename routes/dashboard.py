"""
Dashboard Routes - User statistics and analytics for admin and superuser
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import Dict, Any
from datetime import datetime, timedelta

from database import get_db
from routes.auth import get_current_active_user
import models
from models import UserRole

router = APIRouter(
    prefix="/v1.0/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_active_user)]
)

# Add logging for dashboard access attempts
import logging
dashboard_logger = logging.getLogger("dashboard_access")
dashboard_logger.setLevel(logging.INFO)

def require_admin_or_superuser(current_user: models.User) -> models.User:
    """Check if user is admin or superuser"""
    if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
        # Log unauthorized access attempts for debugging
        print(f"🚫 Unauthorized dashboard access attempt:")
        print(f"   User ID: {current_user.id}")
        print(f"   Username: {current_user.username}")
        print(f"   Role: {current_user.role}")
        print(f"   Email: {getattr(current_user, 'email', 'N/A')}")
        
        # Special message for the specific user causing issues
        if current_user.username == "roman":
            detail = "Access denied. User 'roman' does not have dashboard permissions. Please use an admin account or contact administrator to upgrade permissions."
        else:
            detail = "Access denied. Only admin and super admin users can access dashboard."
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )
    return current_user

@router.get("/stats")
async def get_dashboard_stats(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive dashboard statistics for admin and superuser
    Returns: Total Users, Active Users, Admin Users, General Users, 
    Points Distributed, Current Balance, Recent Signups, Inactive Users
    """
    
    # Log dashboard access attempt
    dashboard_logger.info(f"Dashboard stats requested by user: {current_user.username} (ID: {current_user.id}, Role: {current_user.role})")
    
    # Temporary: Block specific user to stop spam
    if current_user.username == "roman":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dashboard access temporarily disabled for this user. Please contact administrator."
        )
    
    # Check permissions BEFORE try block to avoid wrapping 403 in 500
    require_admin_or_superuser(current_user)
    
    try:
        
        # Calculate date ranges
        now = datetime.utcnow()
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)
        
        # Initialize all values with defaults
        total_users = 0
        admin_users = 0
        super_users = 0
        general_users = 0
        active_users = 0
        recent_signups = 0
        inactive_users = 0
        total_points_distributed = 0
        current_balance = 0
        total_transactions = 0
        recent_activity_count = 0
        users_with_api_keys = 0
        
        # Basic user statistics (these should always work)
        try:
            total_users = db.query(func.count(models.User.id)).scalar() or 0
            
            admin_users = db.query(func.count(models.User.id)).filter(
                models.User.role == UserRole.ADMIN_USER
            ).scalar() or 0
            
            super_users = db.query(func.count(models.User.id)).filter(
                models.User.role == UserRole.SUPER_USER
            ).scalar() or 0
            
            general_users = db.query(func.count(models.User.id)).filter(
                models.User.role == UserRole.GENERAL_USER
            ).scalar() or 0
            
            recent_signups = db.query(func.count(models.User.id)).filter(
                models.User.created_at >= thirty_days_ago
            ).scalar() or 0
            
            users_with_api_keys = db.query(func.count(models.User.id)).filter(
                models.User.api_key.isnot(None)
            ).scalar() or 0
            
        except Exception as e:
            print(f"Error fetching basic user stats: {e}")
        
        # Activity statistics (may fail if UserActivityLog table doesn't exist)
        try:
            active_users = db.query(func.count(func.distinct(models.UserActivityLog.user_id))).filter(
                models.UserActivityLog.created_at >= seven_days_ago
            ).scalar() or 0
            
            recent_activity_count = db.query(func.count(models.UserActivityLog.id)).filter(
                models.UserActivityLog.created_at >= seven_days_ago
            ).scalar() or 0
            
            # Calculate inactive users
            users_with_activity = db.query(func.distinct(models.UserActivityLog.user_id)).filter(
                models.UserActivityLog.created_at >= thirty_days_ago
            ).subquery()
            
            inactive_users = db.query(func.count(models.User.id)).filter(
                ~models.User.id.in_(db.query(users_with_activity.c.user_id))
            ).scalar() or 0
            
        except Exception as e:
            print(f"Error fetching activity stats (UserActivityLog may not exist): {e}")
            # If no activity data, assume all users are inactive
            inactive_users = total_users
        
        # Points statistics (may fail if UserPoint table doesn't exist)
        try:
            total_points_distributed = db.query(func.sum(models.UserPoint.total_points)).scalar() or 0
            current_balance = db.query(func.sum(models.UserPoint.current_points)).scalar() or 0
        except Exception as e:
            print(f"Error fetching points stats (UserPoint may not exist): {e}")
        
        # Transaction statistics (may fail if PointTransaction table doesn't exist)
        try:
            total_transactions = db.query(func.count(models.PointTransaction.id)).scalar() or 0
        except Exception as e:
            print(f"Error fetching transaction stats (PointTransaction may not exist): {e}")
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "admin_users": admin_users + super_users,  # Combined admin count
            "general_users": general_users,
            "points_distributed": total_points_distributed,
            "current_balance": current_balance,
            "recent_signups": recent_signups,
            "inactive_users": inactive_users,
            "additional_stats": {
                "super_users": super_users,
                "admin_users_only": admin_users,
                "total_transactions": total_transactions,
                "recent_activity_count": recent_activity_count,
                "users_with_api_keys": users_with_api_keys,
                "points_used": total_points_distributed - current_balance
            },
            "timestamp": now.isoformat(),
            "requested_by": {
                "user_id": current_user.id,
                "username": current_user.username,
                "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
            }
        }
    
    except Exception as e:
        # Log the detailed error
        import traceback
        print(f"Dashboard stats error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard statistics: {str(e)}"
        )

@router.get("/user-activity")
async def get_user_activity_stats(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    days: int = 30
) -> Dict[str, Any]:
    """
    Get detailed user activity statistics
    """
    
    # Check permissions BEFORE try block
    require_admin_or_superuser(current_user)
    
    try:
        
        # Calculate date range
        now = datetime.utcnow()
        start_date = now - timedelta(days=days)
        
        daily_activity = []
        most_active_users = []
        
        # Try to get activity data (may fail if UserActivityLog doesn't exist)
        try:
            # Activity by day
            daily_activity = db.query(
                func.date(models.UserActivityLog.created_at).label('date'),
                func.count(models.UserActivityLog.id).label('activity_count'),
                func.count(func.distinct(models.UserActivityLog.user_id)).label('unique_users')
            ).filter(
                models.UserActivityLog.created_at >= start_date
            ).group_by(
                func.date(models.UserActivityLog.created_at)
            ).order_by(
                func.date(models.UserActivityLog.created_at)
            ).all()
            
            # Most active users
            most_active_users = db.query(
                models.User.id,
                models.User.username,
                models.User.email,
                models.User.role,
                func.count(models.UserActivityLog.id).label('activity_count')
            ).join(
                models.UserActivityLog, models.User.id == models.UserActivityLog.user_id
            ).filter(
                models.UserActivityLog.created_at >= start_date
            ).group_by(
                models.User.id, models.User.username, models.User.email, models.User.role
            ).order_by(
                func.count(models.UserActivityLog.id).desc()
            ).limit(10).all()
            
        except Exception as e:
            print(f"UserActivityLog table may not exist or be empty: {e}")
            # Return empty data if activity log doesn't exist
            daily_activity = []
            most_active_users = []
        
        return {
            "period_days": days,
            "daily_activity": [
                {
                    "date": str(day.date),
                    "activity_count": day.activity_count,
                    "unique_users": day.unique_users
                }
                for day in daily_activity
            ],
            "most_active_users": [
                {
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
                    "activity_count": user.activity_count
                }
                for user in most_active_users
            ],
            "timestamp": now.isoformat()
        }
    
    except Exception as e:
        import traceback
        print(f"User activity stats error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user activity statistics: {str(e)}"
        )

@router.get("/points-summary")
async def get_points_summary(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get detailed points and transaction statistics
    """
    
    # Check permissions BEFORE try block
    require_admin_or_superuser(current_user)
    
    try:
        
        points_by_role = []
        recent_transactions = 0
        transaction_types = []
        top_point_holders = []
        
        # Try to get points data (may fail if UserPoint table doesn't exist)
        try:
            # Points distribution by user role
            points_by_role = db.query(
                models.User.role,
                func.count(models.User.id).label('user_count'),
                func.sum(models.UserPoint.total_points).label('total_points'),
                func.sum(models.UserPoint.current_points).label('current_points'),
                func.avg(models.UserPoint.current_points).label('avg_points')
            ).join(
                models.UserPoint, models.User.id == models.UserPoint.user_id
            ).group_by(
                models.User.role
            ).all()
            
            # Top point holders
            top_point_holders = db.query(
                models.User.id,
                models.User.username,
                models.User.role,
                models.UserPoint.current_points,
                models.UserPoint.total_points
            ).join(
                models.UserPoint, models.User.id == models.UserPoint.user_id
            ).order_by(
                models.UserPoint.current_points.desc()
            ).limit(10).all()
            
        except Exception as e:
            print(f"UserPoint table may not exist or be empty: {e}")
        
        # Try to get transaction data (may fail if PointTransaction table doesn't exist)
        try:
            # Recent transactions (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_transactions = db.query(func.count(models.PointTransaction.id)).filter(
                models.PointTransaction.created_at >= thirty_days_ago
            ).scalar() or 0
            
            # Transaction volume by type
            transaction_types = db.query(
                models.PointTransaction.transaction_type,
                func.count(models.PointTransaction.id).label('count'),
                func.sum(models.PointTransaction.points).label('total_points')
            ).group_by(
                models.PointTransaction.transaction_type
            ).all()
            
        except Exception as e:
            print(f"PointTransaction table may not exist or be empty: {e}")
        
        return {
            "points_by_role": [
                {
                    "role": role.role.value if hasattr(role.role, 'value') else str(role.role),
                    "user_count": role.user_count,
                    "total_points": role.total_points or 0,
                    "current_points": role.current_points or 0,
                    "avg_points": float(role.avg_points or 0)
                }
                for role in points_by_role
            ],
            "recent_transactions_30d": recent_transactions,
            "transaction_types": [
                {
                    "type": tx.transaction_type,
                    "count": tx.count,
                    "total_points": tx.total_points or 0
                }
                for tx in transaction_types
            ],
            "top_point_holders": [
                {
                    "user_id": user.id,
                    "username": user.username,
                    "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
                    "current_points": user.current_points or 0,
                    "total_points": user.total_points or 0
                }
                for user in top_point_holders
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        import traceback
        print(f"Points summary error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch points summary: {str(e)}"
        )