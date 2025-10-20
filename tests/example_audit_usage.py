"""
Examples of how to use audit_logging.py functions in your FastAPI routes
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from database import get_db
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel, SessionManager
import models

router = APIRouter()

# Example 1: Basic Activity Logging
@router.post("/example/user-action")
async def example_user_action(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Example of logging a user action"""
    
    # Initialize audit logger
    audit_logger = AuditLogger(db)
    
    # Log the activity
    audit_logger.log_activity(
        activity_type=ActivityType.USER_UPDATED,
        user_id=current_user.id,
        details={"action": "profile_update", "fields": ["email", "username"]},
        request=request,
        security_level=SecurityLevel.MEDIUM,
        success=True
    )
    
    return {"message": "Action logged successfully"}


# Example 2: Authentication Event Logging
@router.post("/example/login")
async def example_login(
    request: Request,
    db: Session = Depends(get_db)
):
    """Example of logging authentication events"""
    
    audit_logger = AuditLogger(db)
    
    # Successful login
    audit_logger.log_authentication_event(
        activity_type=ActivityType.LOGIN_SUCCESS,
        user_id="user123",
        email="user@example.com",
        request=request,
        success=True
    )
    
    # Failed login attempt
    audit_logger.log_authentication_event(
        activity_type=ActivityType.LOGIN_FAILED,
        user_id=None,  # No user ID for failed login
        email="hacker@example.com",
        request=request,
        success=False,
        failure_reason="Invalid password"
    )
    
    return {"message": "Authentication events logged"}


# Example 3: Security Event Logging
@router.post("/example/security-event")
async def example_security_event(
    request: Request,
    db: Session = Depends(get_db)
):
    """Example of logging security events"""
    
    audit_logger = AuditLogger(db)
    
    # Log suspicious activity
    audit_logger.log_security_event(
        activity_type=ActivityType.SUSPICIOUS_ACTIVITY,
        user_id="user123",
        request=request,
        details={
            "reason": "Multiple failed login attempts",
            "attempts": 5,
            "time_window": "5 minutes"
        },
        security_level=SecurityLevel.HIGH
    )
    
    return {"message": "Security event logged"}


# Example 4: Point Transaction Logging
@router.post("/example/point-transaction")
async def example_point_transaction(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Example of logging point transactions"""
    
    audit_logger = AuditLogger(db)
    
    # Log point transfer
    audit_logger.log_point_transaction(
        activity_type=ActivityType.POINTS_TRANSFERRED,
        giver_id=current_user.id,
        receiver_id="receiver123",
        points=100,
        transaction_type="transfer",
        request=request
    )
    
    return {"message": "Point transaction logged"}


# Example 5: Bulk Operation Logging
@router.post("/example/bulk-operation")
async def example_bulk_operation(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Example of logging bulk operations"""
    
    audit_logger = AuditLogger(db)
    
    # Simulate bulk user update
    affected_users = 50
    errors = ["User ID 123 not found", "Invalid email for user 456"]
    
    audit_logger.log_bulk_operation(
        user_id=current_user.id,
        operation_type="bulk_user_update",
        affected_count=affected_users,
        request=request,
        success=True,
        errors=errors
    )
    
    return {"message": "Bulk operation logged"}


# Example 6: Session Management
@router.post("/example/session-management")
async def example_session_management(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Example of session management"""
    
    session_manager = SessionManager(db)
    
    # Create a new session
    from datetime import datetime, timedelta
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    session = session_manager.create_session(
        user_id=current_user.id,
        session_id="session_123",
        request=request,
        expires_at=expires_at
    )
    
    # Update session activity
    session_manager.update_session_activity("session_123")
    
    # Get active sessions
    active_sessions = session_manager.get_active_sessions(current_user.id)
    
    return {
        "message": "Session managed",
        "active_sessions": len(active_sessions)
    }


# Example 7: Get Activity History
@router.get("/example/activity-history/{user_id}")
async def get_activity_history(
    user_id: str,
    db: Session = Depends(get_db),
    days: int = 30
):
    """Example of retrieving activity history"""
    
    audit_logger = AuditLogger(db)
    
    # Get user activity history
    activities = audit_logger.get_user_activity_history(
        user_id=user_id,
        days=days,
        activity_types=[ActivityType.LOGIN_SUCCESS, ActivityType.USER_UPDATED],
        limit=50
    )
    
    # Get security events
    security_events = audit_logger.get_security_events(
        days=7,
        security_level=SecurityLevel.HIGH,
        limit=20
    )
    
    # Get activity summary
    summary = audit_logger.get_activity_summary(
        user_id=user_id,
        days=days
    )
    
    return {
        "activities": len(activities),
        "security_events": len(security_events),
        "summary": summary
    }