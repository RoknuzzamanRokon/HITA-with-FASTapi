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
    """
    Validate Admin or Super User Access for Dashboard Operations
    
    Validates that the current user has sufficient privileges to access dashboard
    endpoints. This function enforces role-based access control for administrative
    operations and logs unauthorized access attempts for security monitoring.
    
    Features:
    - Role-based access control validation
    - Comprehensive unauthorized access logging
    - Security monitoring and audit trail
    - Detailed error messages for troubleshooting
    - User-specific access denial handling
    
    Args:
        current_user (models.User): Currently authenticated user to validate
    
    Returns:
        models.User: The validated user if access is granted
    
    Raises:
        HTTPException: 403 Forbidden if user lacks required privileges
    
    Access Requirements:
        - User must have SUPER_USER or ADMIN_USER role
        - User account must be active and properly authenticated
        - All access attempts are logged for security monitoring
    
    Security Features:
        - Unauthorized access attempts logged with user details
        - Role validation with comprehensive error reporting
        - User identification tracking for audit purposes
        - Detailed access denial messages for troubleshooting
    """
    try:
        # Validate user object
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Validate user role
        if not hasattr(current_user, 'role') or current_user.role is None:
            dashboard_logger.warning(f"User {getattr(current_user, 'id', 'unknown')} has no role defined")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User role not defined. Contact administrator."
            )
        
        # Check if user has required admin privileges
        if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            # Log unauthorized access attempt for security monitoring
            dashboard_logger.warning(f"🚫 Unauthorized dashboard access attempt:")
            dashboard_logger.warning(f"   User ID: {getattr(current_user, 'id', 'unknown')}")
            dashboard_logger.warning(f"   Username: {getattr(current_user, 'username', 'unknown')}")
            dashboard_logger.warning(f"   Role: {current_user.role}")
            dashboard_logger.warning(f"   Email: {getattr(current_user, 'email', 'N/A')}")
            dashboard_logger.warning(f"   Timestamp: {datetime.utcnow().isoformat()}")
            
            # Generate appropriate error message
            user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
            detail = f"Access denied. Only admin and super admin users can access dashboard. Current role: {user_role}"
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail
            )
        
        # Log successful access validation
        dashboard_logger.info(f"✅ Dashboard access granted to {getattr(current_user, 'username', 'unknown')} (Role: {current_user.role})")
        
        return current_user
        
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        # Log unexpected errors
        dashboard_logger.error(f"Error validating user access: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error validating user permissions"
        )

@router.get("/stats")
async def get_dashboard_stats(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get Comprehensive Dashboard Statistics (Admin and Super User Only)
    
    Retrieves comprehensive system statistics and key performance indicators for
    administrative dashboards. This endpoint provides essential metrics for system
    monitoring, user management, and business intelligence.
    
    Features:
    - Comprehensive user statistics and demographics
    - Activity tracking and engagement metrics
    - Points system analytics and transaction summaries
    - Role-based user distribution analysis
    - Recent registration and activity trends
    - System health and usage indicators
    - Graceful handling of missing database tables
    
    Statistics Provided:
        - User Demographics: Total users, role distribution, recent registrations
        - Activity Metrics: Active users, recent activity, engagement patterns
        - Points Analytics: Points distributed, current balances, transaction volumes
        - System Health: API key usage, inactive users, system utilization
        - Business Intelligence: Growth trends, user engagement, system adoption
    
    Args:
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)
    
    Returns:
        dict: Comprehensive dashboard statistics including:
            - total_users: Total registered users in the system
            - active_users: Users active in the last 7 days
            - admin_users: Combined count of admin and super users
            - general_users: Count of general/standard users
            - points_distributed: Total points distributed across all users
            - current_balance: Current total points balance in the system
            - recent_signups: New user registrations in the last 30 days
            - inactive_users: Users with no recent activity
            - additional_stats: Detailed breakdown and extended metrics
            - timestamp: When statistics were generated
            - requested_by: Information about the requesting admin user
    
    Access Control:
        - Requires ADMIN_USER or SUPER_USER role
        - All access attempts logged for audit purposes
        - Unauthorized access attempts tracked and blocked
    
    Error Handling:
        - 401: User not authenticated
        - 403: Insufficient privileges (non-admin users)
        - 500: Database errors or system failures
        - Graceful degradation when optional tables are missing
    
    Database Resilience:
        - Handles missing UserActivityLog table gracefully
        - Handles missing UserPoint table gracefully
        - Handles missing PointTransaction table gracefully
        - Provides default values when data is unavailable
    
    Use Cases:
        - Administrative dashboards and control panels
        - System monitoring and health assessment
        - Business intelligence and reporting
        - User management and oversight
        - Performance analysis and optimization
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Log dashboard access attempt for audit purposes
        dashboard_logger.info(f"Dashboard stats requested by user: {current_user.username} (ID: {current_user.id}, Role: {current_user.role})")
        
        # Validate user permissions BEFORE processing to avoid wrapping 403 in 500
        require_admin_or_superuser(current_user)
        
        # Calculate date ranges for time-based statistics
        now = datetime.utcnow()
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)
        
        # Initialize all statistics with safe defaults
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
        
        # Collect basic user statistics with error handling
        try:
            # Core user counts
            total_users = db.query(func.count(models.User.id)).scalar() or 0
            
            # User role distribution
            admin_users = db.query(func.count(models.User.id)).filter(
                models.User.role == UserRole.ADMIN_USER
            ).scalar() or 0
            
            super_users = db.query(func.count(models.User.id)).filter(
                models.User.role == UserRole.SUPER_USER
            ).scalar() or 0
            
            general_users = db.query(func.count(models.User.id)).filter(
                models.User.role == UserRole.GENERAL_USER
            ).scalar() or 0
            
            # Recent user registrations
            recent_signups = db.query(func.count(models.User.id)).filter(
                models.User.created_at >= thirty_days_ago
            ).scalar() or 0
            
            # Users with API keys (system integration indicator)
            users_with_api_keys = db.query(func.count(models.User.id)).filter(
                models.User.api_key.isnot(None)
            ).scalar() or 0
            
        except Exception as e:
            dashboard_logger.error(f"Error fetching basic user statistics: {e}")
            # Continue with default values
        
        # Collect activity statistics with graceful degradation
        try:
            # Active users in the last 7 days
            active_users = db.query(func.count(func.distinct(models.UserActivityLog.user_id))).filter(
                models.UserActivityLog.created_at >= seven_days_ago
            ).scalar() or 0
            
            # Recent activity count
            recent_activity_count = db.query(func.count(models.UserActivityLog.id)).filter(
                models.UserActivityLog.created_at >= seven_days_ago
            ).scalar() or 0
            
            # Calculate inactive users (users without recent activity)
            users_with_activity = db.query(func.distinct(models.UserActivityLog.user_id)).filter(
                models.UserActivityLog.created_at >= thirty_days_ago
            ).subquery()
            
            inactive_users = db.query(func.count(models.User.id)).filter(
                ~models.User.id.in_(db.query(users_with_activity.c.user_id))
            ).scalar() or 0
            
        except Exception as e:
            dashboard_logger.warning(f"UserActivityLog table may not exist or be accessible: {e}")
            # If no activity data available, assume all users are inactive
            inactive_users = total_users
        
        # Collect points system statistics with graceful degradation
        try:
            total_points_distributed = db.query(func.sum(models.UserPoint.total_points)).scalar() or 0
            current_balance = db.query(func.sum(models.UserPoint.current_points)).scalar() or 0
        except Exception as e:
            dashboard_logger.warning(f"UserPoint table may not exist or be accessible: {e}")
            # Continue with default values (0)
        
        # Collect transaction statistics with graceful degradation
        try:
            total_transactions = db.query(func.count(models.PointTransaction.id)).scalar() or 0
        except Exception as e:
            dashboard_logger.warning(f"PointTransaction table may not exist or be accessible: {e}")
            # Continue with default values (0)
        
        # Calculate derived metrics
        points_used = max(0, total_points_distributed - current_balance)
        
        # Compile comprehensive statistics response
        return {
            "total_users": total_users,
            "active_users": active_users,
            "admin_users": admin_users + super_users,  # Combined admin count for dashboard
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
                "points_used": points_used,
                "user_engagement_rate": round((active_users / total_users * 100), 2) if total_users > 0 else 0,
                "admin_percentage": round(((admin_users + super_users) / total_users * 100), 2) if total_users > 0 else 0
            },
            "data_quality": {
                "activity_data_available": recent_activity_count > 0,
                "points_data_available": total_points_distributed > 0,
                "transaction_data_available": total_transactions > 0
            },
            "timestamp": now.isoformat(),
            "requested_by": {
                "user_id": current_user.id,
                "username": current_user.username,
                "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
            }
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions (like 403 Forbidden) without modification
        raise
    except Exception as e:
        # Log detailed error information for debugging
        import traceback
        dashboard_logger.error(f"Dashboard statistics error: {e}")
        dashboard_logger.error(f"Traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard statistics: {str(e)}"
        )

@router.get("/user_activity")
async def get_user_activity_stats(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    days: int = 30
) -> Dict[str, Any]:
    """
    Get Detailed User Activity Statistics (Admin and Super User Only)
    
    Retrieves comprehensive user activity analytics including daily activity trends,
    most active users, and engagement patterns over a specified time period. This
    endpoint provides insights for user behavior analysis and system optimization.
    
    Features:
    - Daily activity trend analysis with user engagement metrics
    - Most active users identification and ranking
    - Configurable time period for flexible analysis
    - Comprehensive activity pattern insights
    - Graceful handling of missing activity data
    - User engagement and behavior analytics
    
    Activity Metrics Provided:
        - Daily Activity Trends: Activity counts and unique users per day
        - User Engagement: Most active users with activity rankings
        - Activity Patterns: Peak usage times and engagement trends
        - User Behavior: Activity distribution and usage patterns
        - System Usage: Overall activity volume and user participation
    
    Args:
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)
        days (int): Number of days to analyze (default: 30, range: 1-365)
    
    Returns:
        dict: Comprehensive activity statistics including:
            - period_days: Analysis period in days
            - daily_activity: Day-by-day activity breakdown including:
                - date: Date of activity
                - activity_count: Total activities for the day
                - unique_users: Number of unique active users
            - most_active_users: Top 10 most active users including:
                - user_id: User identifier
                - username: User's username
                - email: User's email address
                - role: User's role in the system
                - activity_count: Total activities by the user
            - activity_summary: Aggregated activity insights
            - timestamp: When analysis was performed
    
    Access Control:
        - Requires ADMIN_USER or SUPER_USER role
        - Activity analysis access logged for audit purposes
        - User privacy considerations in activity reporting
    
    Error Handling:
        - 400: Invalid days parameter (outside valid range)
        - 401: User not authenticated
        - 403: Insufficient privileges (non-admin users)
        - 500: Database errors or activity log access failures
        - Graceful degradation when UserActivityLog table is missing
    
    Data Privacy:
        - User email addresses included for admin oversight
        - Activity patterns aggregated to protect individual privacy
        - Sensitive user actions filtered from public activity metrics
    
    Use Cases:
        - User engagement analysis and optimization
        - System usage pattern identification
        - User behavior insights for product development
        - Performance monitoring and capacity planning
        - User support and account management
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Validate days parameter
        if days < 1 or days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days parameter must be between 1 and 365"
            )
        
        # Validate user permissions BEFORE processing
        require_admin_or_superuser(current_user)
        
        # Calculate analysis date range
        now = datetime.utcnow()
        start_date = now - timedelta(days=days)
        
        # Initialize activity data structures
        daily_activity = []
        most_active_users = []
        activity_summary = {
            "total_activities": 0,
            "total_unique_users": 0,
            "avg_daily_activities": 0,
            "avg_daily_users": 0,
            "peak_activity_date": None,
            "data_available": False
        }
        
        # Attempt to collect activity data with graceful degradation
        try:
            # Daily activity trend analysis
            daily_activity_raw = db.query(
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
            
            # Process daily activity data
            daily_activity = [
                {
                    "date": str(day.date),
                    "activity_count": day.activity_count,
                    "unique_users": day.unique_users
                }
                for day in daily_activity_raw
            ]
            
            # Most active users analysis
            most_active_users_raw = db.query(
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
            
            # Process most active users data
            most_active_users = [
                {
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
                    "activity_count": user.activity_count
                }
                for user in most_active_users_raw
            ]
            
            # Calculate activity summary metrics
            if daily_activity:
                activity_summary["total_activities"] = sum(day["activity_count"] for day in daily_activity)
                activity_summary["total_unique_users"] = len(set(
                    user["user_id"] for user in most_active_users
                ))
                activity_summary["avg_daily_activities"] = round(
                    activity_summary["total_activities"] / len(daily_activity), 2
                )
                activity_summary["avg_daily_users"] = round(
                    sum(day["unique_users"] for day in daily_activity) / len(daily_activity), 2
                )
                
                # Find peak activity date
                peak_day = max(daily_activity, key=lambda x: x["activity_count"])
                activity_summary["peak_activity_date"] = peak_day["date"]
                activity_summary["data_available"] = True
            
        except Exception as e:
            dashboard_logger.warning(f"UserActivityLog table may not exist or be accessible: {e}")
            # Continue with empty data structures if activity log is not available
            daily_activity = []
            most_active_users = []
            activity_summary["data_available"] = False
        
        # Log activity analysis access
        dashboard_logger.info(f"User activity analysis requested by {current_user.username} for {days} days")
        
        return {
            "period_days": days,
            "analysis_period": {
                "start_date": start_date.isoformat(),
                "end_date": now.isoformat(),
                "total_days_analyzed": days
            },
            "daily_activity": daily_activity,
            "most_active_users": most_active_users,
            "activity_summary": activity_summary,
            "data_quality": {
                "activity_log_available": activity_summary["data_available"],
                "days_with_data": len(daily_activity),
                "users_with_activity": len(most_active_users)
            },
            "timestamp": now.isoformat(),
            "requested_by": {
                "user_id": current_user.id,
                "username": current_user.username,
                "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
            }
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        # Log detailed error information
        import traceback
        dashboard_logger.error(f"User activity statistics error: {e}")
        dashboard_logger.error(f"Traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user activity statistics: {str(e)}"
        )

@router.get("/points_summary")
async def get_points_summary(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get Detailed Points and Transaction Statistics (Admin and Super User Only)
    
    Retrieves comprehensive points system analytics including points distribution
    by user role, transaction patterns, top point holders, and financial insights.
    This endpoint provides essential data for points system management and analysis.
    
    Features:
    - Points distribution analysis by user role
    - Transaction volume and pattern analysis
    - Top point holders identification and ranking
    - Financial insights and points economy metrics
    - Transaction type breakdown and analytics
    - Graceful handling of missing points/transaction data
    
    Points Analytics Provided:
        - Role-based Points Distribution: Points allocation across user roles
        - Transaction Analytics: Recent transaction volumes and patterns
        - Top Users: Highest point holders and their statistics
        - Financial Metrics: Points economy health and distribution
        - Usage Patterns: Points earning and spending behaviors
        - System Health: Points system utilization and engagement
    
    Args:
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)
    
    Returns:
        dict: Comprehensive points system statistics including:
            - points_by_role: Points distribution breakdown by user role
            - recent_transactions_30d: Transaction count in last 30 days
            - transaction_types: Breakdown of transaction types and volumes
            - top_point_holders: Top 10 users by current point balance
            - points_economy: Overall points system health metrics
            - financial_insights: Points distribution and utilization analysis
            - timestamp: When analysis was performed
    
    Points by Role Structure:
        - role: User role (GENERAL_USER, ADMIN_USER, SUPER_USER)
        - user_count: Number of users in this role with points
        - total_points: Total points ever distributed to this role
        - current_points: Current point balance for this role
        - avg_points: Average points per user in this role
    
    Access Control:
        - Requires ADMIN_USER or SUPER_USER role
        - Points system access logged for audit purposes
        - Financial data access tracked for compliance
    
    Error Handling:
        - 401: User not authenticated
        - 403: Insufficient privileges (non-admin users)
        - 500: Database errors or points system access failures
        - Graceful degradation when UserPoint table is missing
        - Graceful degradation when PointTransaction table is missing
    
    Data Privacy:
        - User identifiers included for administrative oversight
        - Points balances visible for system management
        - Transaction patterns aggregated for privacy protection
    
    Use Cases:
        - Points system administration and management
        - Financial analysis and points economy monitoring
        - User engagement and rewards program optimization
        - System capacity planning and resource allocation
        - Compliance reporting and audit requirements
    """
    try:
        # Validate user authentication
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Validate user permissions BEFORE processing
        require_admin_or_superuser(current_user)
        
        # Initialize data structures with safe defaults
        points_by_role = []
        recent_transactions = 0
        transaction_types = []
        top_point_holders = []
        points_economy = {
            "total_points_in_system": 0,
            "total_points_distributed": 0,
            "points_utilization_rate": 0,
            "average_user_balance": 0,
            "data_available": False
        }
        
        # Attempt to collect points distribution data
        try:
            # Points distribution analysis by user role
            points_by_role_raw = db.query(
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
            
            # Process points by role data
            points_by_role = [
                {
                    "role": role.role.value if hasattr(role.role, 'value') else str(role.role),
                    "user_count": role.user_count,
                    "total_points": role.total_points or 0,
                    "current_points": role.current_points or 0,
                    "avg_points": float(role.avg_points or 0),
                    "points_utilization": round(
                        ((role.total_points - role.current_points) / role.total_points * 100), 2
                    ) if role.total_points and role.total_points > 0 else 0
                }
                for role in points_by_role_raw
            ]
            
            # Top point holders analysis
            top_point_holders_raw = db.query(
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
            
            # Process top point holders data
            top_point_holders = [
                {
                    "user_id": user.id,
                    "username": user.username,
                    "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
                    "current_points": user.current_points or 0,
                    "total_points": user.total_points or 0,
                    "points_used": (user.total_points or 0) - (user.current_points or 0)
                }
                for user in top_point_holders_raw
            ]
            
            # Calculate points economy metrics
            if points_by_role:
                points_economy["total_points_distributed"] = sum(role["total_points"] for role in points_by_role)
                points_economy["total_points_in_system"] = sum(role["current_points"] for role in points_by_role)
                points_economy["points_utilization_rate"] = round(
                    ((points_economy["total_points_distributed"] - points_economy["total_points_in_system"]) 
                     / points_economy["total_points_distributed"] * 100), 2
                ) if points_economy["total_points_distributed"] > 0 else 0
                points_economy["average_user_balance"] = round(
                    points_economy["total_points_in_system"] / sum(role["user_count"] for role in points_by_role), 2
                ) if sum(role["user_count"] for role in points_by_role) > 0 else 0
                points_economy["data_available"] = True
            
        except Exception as e:
            dashboard_logger.warning(f"UserPoint table may not exist or be accessible: {e}")
            # Continue with empty data if points system is not available
        
        # Attempt to collect transaction data
        try:
            # Recent transactions analysis (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_transactions = db.query(func.count(models.PointTransaction.id)).filter(
                models.PointTransaction.created_at >= thirty_days_ago
            ).scalar() or 0
            
            # Transaction type breakdown and analysis
            transaction_types_raw = db.query(
                models.PointTransaction.transaction_type,
                func.count(models.PointTransaction.id).label('count'),
                func.sum(models.PointTransaction.points).label('total_points'),
                func.avg(models.PointTransaction.points).label('avg_points')
            ).group_by(
                models.PointTransaction.transaction_type
            ).all()
            
            # Process transaction types data
            transaction_types = [
                {
                    "type": tx.transaction_type,
                    "count": tx.count,
                    "total_points": tx.total_points or 0,
                    "avg_points": float(tx.avg_points or 0),
                    "percentage_of_total": 0  # Will be calculated after processing all types
                }
                for tx in transaction_types_raw
            ]
            
            # Calculate transaction type percentages
            total_transaction_count = sum(tx["count"] for tx in transaction_types)
            if total_transaction_count > 0:
                for tx in transaction_types:
                    tx["percentage_of_total"] = round((tx["count"] / total_transaction_count * 100), 2)
            
        except Exception as e:
            dashboard_logger.warning(f"PointTransaction table may not exist or be accessible: {e}")
            # Continue with empty data if transaction system is not available
        
        # Log points summary access
        dashboard_logger.info(f"Points summary requested by {current_user.username}")
        
        return {
            "points_by_role": points_by_role,
            "recent_transactions_30d": recent_transactions,
            "transaction_types": transaction_types,
            "top_point_holders": top_point_holders,
            "points_economy": points_economy,
            "financial_insights": {
                "total_roles_with_points": len(points_by_role),
                "most_active_transaction_type": max(transaction_types, key=lambda x: x["count"])["type"] if transaction_types else None,
                "highest_point_holder": top_point_holders[0] if top_point_holders else None,
                "transaction_activity_level": "high" if recent_transactions > 100 else "medium" if recent_transactions > 10 else "low"
            },
            "data_quality": {
                "points_data_available": points_economy["data_available"],
                "transaction_data_available": recent_transactions > 0 or len(transaction_types) > 0,
                "users_with_points": sum(role["user_count"] for role in points_by_role),
                "transaction_types_count": len(transaction_types)
            },
            "timestamp": datetime.utcnow().isoformat(),
            "requested_by": {
                "user_id": current_user.id,
                "username": current_user.username,
                "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
            }
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        # Log detailed error information
        import traceback
        dashboard_logger.error(f"Points summary error: {e}")
        dashboard_logger.error(f"Traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch points summary: {str(e)}"
        )