"""
Universal Activity Logging Decorator
Add this to utils/activity_logging.py
"""

from functools import wraps
from typing import Callable, Any
from fastapi import Request
from sqlalchemy.orm import Session
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel
import models
import logging

logger = logging.getLogger(__name__)


def log_user_activity(
    activity_type: str = "api_access",
    security_level: SecurityLevel = SecurityLevel.LOW,
    log_details: dict = None,
):
    """
    Decorator to automatically log user activity for any endpoint

    Usage:
    @log_user_activity(activity_type="hotel_search", security_level=SecurityLevel.MEDIUM)
    @router.get("/search-hotels")
    async def search_hotels(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        # Your endpoint logic here
        return {"results": []}
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request, user, and db from function arguments
            request = None
            current_user = None
            db = None

            # Look for these in kwargs first
            for key, value in kwargs.items():
                if isinstance(value, Request):
                    request = value
                elif isinstance(value, models.User):
                    current_user = value
                elif isinstance(value, Session):
                    db = value

            # If not found in kwargs, look in args
            if not all([request, current_user, db]):
                for arg in args:
                    if isinstance(arg, Request) and not request:
                        request = arg
                    elif isinstance(arg, models.User) and not current_user:
                        current_user = arg
                    elif isinstance(arg, Session) and not db:
                        db = arg

            # Log the activity if we have the required components
            if request and current_user and db:
                try:
                    audit_logger = AuditLogger(db)

                    # Prepare activity details
                    details = {
                        "action": func.__name__,
                        "endpoint": request.url.path,
                        "method": request.method,
                        "function": f"{func.__module__}.{func.__name__}",
                        "user_role": (
                            current_user.role.value
                            if hasattr(current_user.role, "value")
                            else str(current_user.role)
                        ),
                        "user_email": current_user.email,
                        **(log_details or {}),
                    }

                    # Log the activity
                    audit_logger.log_activity(
                        activity_type=ActivityType.API_ACCESS,
                        user_id=current_user.id,
                        details=details,
                        request=request,
                        security_level=security_level,
                        success=True,
                    )

                    logger.info(
                        f"Logged activity: {activity_type} for user {current_user.id} on {request.url.path}"
                    )

                except Exception as e:
                    logger.error(f"Failed to log activity for {func.__name__}: {e}")
            else:
                logger.warning(
                    f"Could not log activity for {func.__name__} - missing request, user, or db"
                )

            # Call the original function
            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Convenience decorators for common activity types
def log_hotel_activity(security_level: SecurityLevel = SecurityLevel.LOW, **details):
    """Decorator for hotel-related activities"""
    return log_user_activity(
        activity_type="hotel_operation",
        security_level=security_level,
        log_details={"category": "hotel", **details},
    )


def log_search_activity(security_level: SecurityLevel = SecurityLevel.LOW, **details):
    """Decorator for search activities"""
    return log_user_activity(
        activity_type="search_operation",
        security_level=security_level,
        log_details={"category": "search", **details},
    )


def log_content_activity(security_level: SecurityLevel = SecurityLevel.LOW, **details):
    """Decorator for content access activities"""
    return log_user_activity(
        activity_type="content_access",
        security_level=security_level,
        log_details={"category": "content", **details},
    )


def log_mapping_activity(
    security_level: SecurityLevel = SecurityLevel.MEDIUM, **details
):
    """Decorator for mapping activities"""
    return log_user_activity(
        activity_type="mapping_operation",
        security_level=security_level,
        log_details={"category": "mapping", **details},
    )
