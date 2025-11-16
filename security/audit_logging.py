"""
Audit Logging and Activity Tracking for User Management

This module provides comprehensive audit logging and activity tracking for all
user management operations, security events, and system activities.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from fastapi import Request
import models
from security.input_validation import validate_ip_address, sanitize_user_agent


class ActivityType(str, Enum):
    """Types of activities to log"""
    
    # Authentication activities
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_RESET_REQUEST = "password_reset_request"
    PASSWORD_RESET_SUCCESS = "password_reset_success"
    PASSWORD_CHANGE = "password_change"
    
    # User management activities
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    USER_ROLE_CHANGED = "user_role_changed"
    
    # Point management activities
    POINTS_GIVEN = "points_given"
    POINTS_USED = "points_used"
    POINTS_RESET = "points_reset"
    POINTS_TRANSFERRED = "points_transferred"
    
    # Permission activities
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    PERMISSION_UPDATED = "permission_updated"
    
    # Security events
    UNAUTHORIZED_ACCESS_ATTEMPT = "unauthorized_access_attempt"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    
    # System activities
    BULK_OPERATION = "bulk_operation"
    DATA_EXPORT = "data_export"
    EXPORT_DATA = "export_data"  # Alias for DATA_EXPORT
    SYSTEM_CONFIGURATION_CHANGE = "system_configuration_change"
    
    # API activities
    API_ACCESS = "api_access"
    API_ERROR = "api_error"
    SEARCH_PERFORMED = "search_performed"


class SecurityLevel(str, Enum):
    """Security levels for audit events"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditLogger:
    """Main audit logging class"""
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger("audit")
        
        # Configure audit logger if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - AUDIT - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log_activity(
        self,
        activity_type: ActivityType,
        user_id: Optional[str] = None,
        target_user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        security_level: SecurityLevel = SecurityLevel.LOW,
        success: bool = True
    ) -> models.UserActivityLog:
        """
        Log user activity
        
        Args:
            activity_type: Type of activity
            user_id: ID of user performing the action
            target_user_id: ID of user being acted upon (if different)
            details: Additional details about the activity
            request: FastAPI request object for IP/user agent
            security_level: Security level of the event
            success: Whether the activity was successful
            
        Returns:
            Created audit log entry
        """
        # Extract request information
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = self._extract_ip_address(request)
            user_agent = sanitize_user_agent(request.headers.get('user-agent', ''))
        
        # Prepare details
        audit_details = details or {}
        audit_details.update({
            'security_level': security_level.value,
            'success': success,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Add target user info if different from acting user
        if target_user_id and target_user_id != user_id:
            audit_details['target_user_id'] = target_user_id
        
        # Create audit log entry
        audit_log = models.UserActivityLog(
            user_id=user_id,
            action=activity_type.value,
            details=audit_details,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow()
        )
        
        try:
            self.db.add(audit_log)
            self.db.commit()
            self.db.refresh(audit_log)
            
            # Also log to application logger for immediate visibility
            log_message = self._format_log_message(
                activity_type, user_id, target_user_id, audit_details, ip_address
            )
            
            if security_level == SecurityLevel.CRITICAL:
                self.logger.critical(log_message)
            elif security_level == SecurityLevel.HIGH:
                self.logger.warning(log_message)
            else:
                self.logger.info(log_message)
            
            return audit_log
            
        except Exception as e:
            self.logger.error(f"Failed to create audit log: {e}")
            # Don't let audit logging failure break the main operation
            self.db.rollback()
            return None
    
    def log_authentication_event(
        self,
        activity_type: ActivityType,
        user_id: Optional[str],
        email: Optional[str],
        request: Request,
        success: bool = True,
        failure_reason: Optional[str] = None
    ):
        """Log authentication-related events"""
        details = {
            'email': email,
            'success': success
        }
        
        if not success and failure_reason:
            details['failure_reason'] = failure_reason
        
        security_level = SecurityLevel.MEDIUM if success else SecurityLevel.HIGH
        
        self.log_activity(
            activity_type=activity_type,
            user_id=user_id,
            details=details,
            request=request,
            security_level=security_level,
            success=success
        )
    
    def log_user_management_event(
        self,
        activity_type: ActivityType,
        acting_user_id: str,
        target_user_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ):
        """Log user management events"""
        details = {}
        
        if changes:
            # Sanitize sensitive information
            safe_changes = changes.copy()
            if 'password' in safe_changes:
                safe_changes['password'] = '[REDACTED]'
            if 'hashed_password' in safe_changes:
                safe_changes['hashed_password'] = '[REDACTED]'
            
            details['changes'] = safe_changes
        
        security_level = SecurityLevel.MEDIUM
        if activity_type in [ActivityType.USER_DELETED, ActivityType.USER_ROLE_CHANGED]:
            security_level = SecurityLevel.HIGH
        
        self.log_activity(
            activity_type=activity_type,
            user_id=acting_user_id,
            target_user_id=target_user_id,
            details=details,
            request=request,
            security_level=security_level
        )
    
    def log_security_event(
        self,
        activity_type: ActivityType,
        user_id: Optional[str],
        request: Request,
        details: Optional[Dict[str, Any]] = None,
        security_level: SecurityLevel = SecurityLevel.HIGH
    ):
        """Log security-related events"""
        security_details = details or {}
        security_details.update({
            'security_event': True,
            'requires_investigation': security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]
        })
        
        self.log_activity(
            activity_type=activity_type,
            user_id=user_id,
            details=security_details,
            request=request,
            security_level=security_level,
            success=False
        )
    
    def log_point_transaction(
        self,
        activity_type: ActivityType,
        giver_id: str,
        receiver_id: Optional[str],
        points: int,
        transaction_type: str,
        request: Optional[Request] = None
    ):
        """Log point-related transactions"""
        details = {
            'points': points,
            'transaction_type': transaction_type,
            'receiver_id': receiver_id
        }
        
        self.log_activity(
            activity_type=activity_type,
            user_id=giver_id,
            target_user_id=receiver_id,
            details=details,
            request=request,
            security_level=SecurityLevel.MEDIUM
        )
    
    def log_bulk_operation(
        self,
        user_id: str,
        operation_type: str,
        affected_count: int,
        request: Request,
        success: bool = True,
        errors: Optional[List[str]] = None
    ):
        """Log bulk operations"""
        details = {
            'operation_type': operation_type,
            'affected_count': affected_count,
            'success': success
        }
        
        if errors:
            details['errors'] = errors
        
        self.log_activity(
            activity_type=ActivityType.BULK_OPERATION,
            user_id=user_id,
            details=details,
            request=request,
            security_level=SecurityLevel.MEDIUM,
            success=success
        )
    
    def get_user_activity_history(
        self,
        user_id: str,
        days: int = 30,
        activity_types: Optional[List[ActivityType]] = None,
        limit: int = 100
    ) -> List[models.UserActivityLog]:
        """Get activity history for a user"""
        query = self.db.query(models.UserActivityLog).filter(
            models.UserActivityLog.user_id == user_id,
            models.UserActivityLog.created_at >= datetime.utcnow() - timedelta(days=days)
        )
        
        if activity_types:
            query = query.filter(
                models.UserActivityLog.action.in_([at.value for at in activity_types])
            )
        
        return query.order_by(desc(models.UserActivityLog.created_at)).limit(limit).all()
    
    def get_security_events(
        self,
        days: int = 7,
        security_level: Optional[SecurityLevel] = None,
        limit: int = 100
    ) -> List[models.UserActivityLog]:
        """Get security events"""
        security_activity_types = [
            ActivityType.UNAUTHORIZED_ACCESS_ATTEMPT.value,
            ActivityType.RATE_LIMIT_EXCEEDED.value,
            ActivityType.SUSPICIOUS_ACTIVITY.value,
            ActivityType.ACCOUNT_LOCKED.value,
            ActivityType.LOGIN_FAILED.value
        ]
        
        query = self.db.query(models.UserActivityLog).filter(
            models.UserActivityLog.action.in_(security_activity_types),
            models.UserActivityLog.created_at >= datetime.utcnow() - timedelta(days=days)
        )
        
        if security_level:
            query = query.filter(
                models.UserActivityLog.details.contains(f'"security_level": "{security_level.value}"')
            )
        
        return query.order_by(desc(models.UserActivityLog.created_at)).limit(limit).all()
    
    def get_activity_summary(
        self,
        user_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get activity summary statistics"""
        base_query = self.db.query(models.UserActivityLog).filter(
            models.UserActivityLog.created_at >= datetime.utcnow() - timedelta(days=days)
        )
        
        if user_id:
            base_query = base_query.filter(models.UserActivityLog.user_id == user_id)
        
        # Get activity counts by type
        activity_counts = base_query.with_entities(
            models.UserActivityLog.action,
            func.count(models.UserActivityLog.id).label('count')
        ).group_by(models.UserActivityLog.action).all()
        
        # Get daily activity counts
        daily_counts = base_query.with_entities(
            func.date(models.UserActivityLog.created_at).label('date'),
            func.count(models.UserActivityLog.id).label('count')
        ).group_by(func.date(models.UserActivityLog.created_at)).all()
        
        # Get security events count
        security_events = base_query.filter(
            models.UserActivityLog.action.in_([
                ActivityType.UNAUTHORIZED_ACCESS_ATTEMPT.value,
                ActivityType.RATE_LIMIT_EXCEEDED.value,
                ActivityType.SUSPICIOUS_ACTIVITY.value,
                ActivityType.LOGIN_FAILED.value
            ])
        ).count()
        
        return {
            'period_days': days,
            'total_activities': base_query.count(),
            'security_events': security_events,
            'activity_by_type': {row.action: row.count for row in activity_counts},
            'daily_activity': [
                {'date': row.date.isoformat(), 'count': row.count}
                for row in daily_counts
            ]
        }
    
    def _extract_ip_address(self, request: Request) -> Optional[str]:
        """Extract and validate IP address from request"""
        # First try to get from middleware state (preferred method)
        if hasattr(request.state, 'real_ip') and request.state.real_ip:
            return request.state.real_ip
        
        # Fallback to manual extraction
        # Check for forwarded headers (when behind proxy/load balancer)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            ip = forwarded_for.split(',')[0].strip()
            if validate_ip_address(ip):
                return ip
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip and validate_ip_address(real_ip):
            return real_ip
        
        # Check additional headers
        client_ip = request.headers.get('X-Client-IP')
        if client_ip and validate_ip_address(client_ip):
            return client_ip
        
        cf_ip = request.headers.get('CF-Connecting-IP')
        if cf_ip and validate_ip_address(cf_ip):
            return cf_ip
        
        # Fall back to direct client IP
        if request.client and validate_ip_address(request.client.host):
            return request.client.host
        
        return None
    
    def _format_log_message(
        self,
        activity_type: ActivityType,
        user_id: Optional[str],
        target_user_id: Optional[str],
        details: Dict[str, Any],
        ip_address: Optional[str]
    ) -> str:
        """Format log message for application logger"""
        message_parts = [f"Activity: {activity_type.value}"]
        
        if user_id:
            message_parts.append(f"User: {user_id}")
        
        if target_user_id and target_user_id != user_id:
            message_parts.append(f"Target: {target_user_id}")
        
        if ip_address:
            message_parts.append(f"IP: {ip_address}")
        
        if details.get('success') is False:
            message_parts.append("Status: FAILED")
        
        return " | ".join(message_parts)


class SessionManager:
    """Manage user sessions and track session activity"""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger(db)
    
    def create_session(
        self,
        user_id: str,
        session_id: str,
        request: Request,
        expires_at: datetime
    ) -> models.UserSession:
        """Create a new user session"""
        session = models.UserSession(
            id=session_id,
            user_id=user_id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            expires_at=expires_at,
            is_active=True
        )
        
        try:
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            
            # Log session creation
            self.audit_logger.log_activity(
                activity_type=ActivityType.LOGIN_SUCCESS,
                user_id=user_id,
                details={'session_id': session_id},
                request=request,
                security_level=SecurityLevel.LOW
            )
            
            return session
            
        except Exception as e:
            self.db.rollback()
            raise e
    
    def update_session_activity(self, session_id: str):
        """Update session last activity timestamp"""
        session = self.db.query(models.UserSession).filter(
            models.UserSession.id == session_id,
            models.UserSession.is_active == True
        ).first()
        
        if session:
            session.last_activity = datetime.utcnow()
            self.db.commit()
    
    def end_session(self, session_id: str, user_id: str, request: Optional[Request] = None):
        """End a user session"""
        session = self.db.query(models.UserSession).filter(
            models.UserSession.id == session_id,
            models.UserSession.user_id == user_id
        ).first()
        
        if session:
            session.is_active = False
            self.db.commit()
            
            # Log session end
            self.audit_logger.log_activity(
                activity_type=ActivityType.LOGOUT,
                user_id=user_id,
                details={'session_id': session_id},
                request=request,
                security_level=SecurityLevel.LOW
            )
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        expired_sessions = self.db.query(models.UserSession).filter(
            models.UserSession.expires_at < datetime.utcnow(),
            models.UserSession.is_active == True
        ).all()
        
        for session in expired_sessions:
            session.is_active = False
        
        if expired_sessions:
            self.db.commit()
        
        return len(expired_sessions)
    
    def get_active_sessions(self, user_id: str) -> List[models.UserSession]:
        """Get active sessions for a user"""
        return self.db.query(models.UserSession).filter(
            models.UserSession.user_id == user_id,
            models.UserSession.is_active == True,
            models.UserSession.expires_at > datetime.utcnow()
        ).order_by(desc(models.UserSession.last_activity)).all()
    
    def revoke_all_sessions(self, user_id: str, except_session_id: Optional[str] = None):
        """Revoke all sessions for a user"""
        query = self.db.query(models.UserSession).filter(
            models.UserSession.user_id == user_id,
            models.UserSession.is_active == True
        )
        
        if except_session_id:
            query = query.filter(models.UserSession.id != except_session_id)
        
        sessions = query.all()
        for session in sessions:
            session.is_active = False
        
        if sessions:
            self.db.commit()
        
        return len(sessions)


def create_audit_middleware():
    """Create middleware for automatic audit logging"""
    
    class AuditMiddleware:
        def __init__(self, app):
            self.app = app
        
        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return
            
            # Store request start time
            start_time = datetime.utcnow()
            
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    # Log API access
                    request_time = datetime.utcnow() - start_time
                    
                    # You could add automatic API access logging here
                    # For now, we'll let individual endpoints handle their own logging
                    pass
                
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
    
    return AuditMiddleware