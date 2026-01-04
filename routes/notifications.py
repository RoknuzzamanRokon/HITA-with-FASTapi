"""
Notification API Routes
Provides endpoints for managing user notifications
"""

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_active_user
import models
from services.notification_service import NotificationService
from repositories.notification_repository import (
    NotificationNotFoundError,
    UnauthorizedNotificationAccessError,
)
from schemas import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
    MarkAllReadResponse,
    NotificationFilters,
)
from models import NotificationType, NotificationPriority, NotificationStatus
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel


# Router setup
router = APIRouter(
    prefix="/v1.0/notifications",
    tags=["Notifications"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=NotificationListResponse)
async def get_notifications(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(25, ge=1, le=100, description="Items per page (max 100)"),
    status: Optional[NotificationStatus] = Query(
        None, description="Filter by notification status (read/unread)"
    ),
    type: Optional[NotificationType] = Query(
        None, description="Filter by notification type"
    ),
    priority: Optional[NotificationPriority] = Query(
        None, description="Filter by priority level"
    ),
    sort_by: str = Query(
        "created_at",
        description="Sort field (created_at or priority)",
        regex="^(created_at|priority)$",
    ),
    sort_order: str = Query(
        "desc", description="Sort order (asc or desc)", regex="^(asc|desc)$"
    ),
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get User Notifications

    Retrieve paginated list of notifications for the authenticated user with optional filtering and sorting.

    **Features:**
    - Pagination support (default: 25 items per page, max: 100)
    - Filter by status (read/unread)
    - Filter by notification type
    - Filter by priority level
    - Sort by creation date or priority
    - Returns unread count with results

    **Authentication:**
    - Requires valid JWT token
    - Users can only access their own notifications

    **Query Parameters:**
    - page: Page number (default: 1)
    - limit: Items per page (default: 25, max: 100)
    - status: Filter by read/unread status
    - type: Filter by notification type
    - priority: Filter by priority level
    - sort_by: Sort field (created_at or priority)
    - sort_order: Sort order (asc or desc)

    **Returns:**
    - notifications: List of notification objects
    - total: Total number of notifications matching filters
    - page: Current page number
    - limit: Items per page
    - total_pages: Total number of pages
    - unread_count: Count of unread notifications

    **Requirements:** 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 7.1, 7.5
    """
    try:
        # Create service instance
        service = NotificationService(db)

        # Build filters
        filters = NotificationFilters(
            status=status,
            type=type,
            priority=priority,
        )

        # Get notifications
        response = service.get_notifications(
            user_id=current_user.id,
            page=page,
            limit=limit,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve notifications: {str(e)}",
        )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get Unread Notification Count

    Retrieve the count of unread notifications for the authenticated user.

    **Features:**
    - Fast count query without retrieving full notification content
    - Returns timestamp of most recent notification
    - Efficient for badge/indicator displays

    **Authentication:**
    - Requires valid JWT token
    - Users can only access their own notification count

    **Returns:**
    - unread_count: Number of unread notifications
    - last_notification_at: Timestamp of most recent notification (null if none)

    **Use Cases:**
    - Notification badge display
    - UI indicators
    - Dashboard widgets
    - Mobile app notifications

    **Requirements:** 7.1, 7.5
    """
    try:
        # Create service instance
        service = NotificationService(db)

        # Get unread count
        response = service.get_unread_count(current_user.id)

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve unread count: {str(e)}",
        )


@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    request: Request,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Mark Notification as Read

    Mark a specific notification as read for the authenticated user.

    **Features:**
    - Updates notification status to 'read'
    - Records read timestamp
    - Validates user ownership
    - Audit logging for security

    **Authentication:**
    - Requires valid JWT token
    - Users can only mark their own notifications as read

    **Path Parameters:**
    - notification_id: ID of the notification to mark as read

    **Returns:**
    - Updated notification object with read status and timestamp

    **Error Responses:**
    - 404: Notification not found
    - 403: User not authorized to access this notification
    - 500: Internal server error

    **Requirements:** 4.1, 4.2, 4.3
    """
    try:
        # Create service instance
        service = NotificationService(db)

        # Mark notification as read
        notification = service.mark_notification_read(notification_id, current_user.id)

        # Convert to response format
        return NotificationResponse.model_validate(notification)

    except NotificationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )
    except UnauthorizedNotificationAccessError:
        # Log unauthorized access attempt
        audit_logger = AuditLogger(db)
        audit_logger.log_activity(
            activity_type=ActivityType.UNAUTHORIZED_ACCESS_ATTEMPT,
            user_id=current_user.id,
            details={
                "action": "mark_notification_read",
                "notification_id": notification_id,
                "reason": "notification_belongs_to_different_user",
            },
            request=request,
            security_level=SecurityLevel.MEDIUM,
            success=False,
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this notification",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark notification as read: {str(e)}",
        )


@router.put("/mark-all-read", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Mark All Notifications as Read

    Mark all unread notifications as read for the authenticated user.

    **Features:**
    - Bulk update of all unread notifications
    - Records read timestamp for all updated notifications
    - Returns count of notifications updated
    - Efficient batch operation

    **Authentication:**
    - Requires valid JWT token
    - Only affects current user's notifications

    **Returns:**
    - updated_count: Number of notifications marked as read
    - message: Success message with count

    **Use Cases:**
    - "Mark all as read" button
    - Clearing notification list
    - Bulk notification management

    **Requirements:** 5.1, 5.2, 5.4
    """
    try:
        # Create service instance
        service = NotificationService(db)

        # Mark all notifications as read
        response = service.mark_all_read(current_user.id)

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark all notifications as read: {str(e)}",
        )


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    request: Request,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Delete Notification

    Permanently delete a specific notification for the authenticated user.

    **Features:**
    - Permanent deletion from database
    - Validates user ownership
    - Audit logging for security
    - Cannot be undone

    **Authentication:**
    - Requires valid JWT token
    - Users can only delete their own notifications

    **Path Parameters:**
    - notification_id: ID of the notification to delete

    **Returns:**
    - Success message confirming deletion

    **Error Responses:**
    - 404: Notification not found
    - 403: User not authorized to delete this notification
    - 500: Internal server error

    **Security:**
    - Authorization checks prevent cross-user deletion
    - Unauthorized attempts are logged for audit
    - Deletion is permanent and cannot be reversed

    **Requirements:** 6.1, 6.2, 6.5
    """
    try:
        # Create service instance
        service = NotificationService(db)

        # Delete notification
        service.delete_notification(notification_id, current_user.id)

        # Log successful deletion
        audit_logger = AuditLogger(db)
        audit_logger.log_activity(
            activity_type=ActivityType.USER_UPDATED,
            user_id=current_user.id,
            details={
                "action": "delete_notification",
                "notification_id": notification_id,
            },
            request=request,
            security_level=SecurityLevel.LOW,
            success=True,
        )

        return {
            "message": f"Notification {notification_id} deleted successfully",
            "notification_id": notification_id,
        }

    except NotificationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )
    except UnauthorizedNotificationAccessError:
        # Log unauthorized access attempt
        audit_logger = AuditLogger(db)
        audit_logger.log_activity(
            activity_type=ActivityType.UNAUTHORIZED_ACCESS_ATTEMPT,
            user_id=current_user.id,
            details={
                "action": "delete_notification",
                "notification_id": notification_id,
                "reason": "notification_belongs_to_different_user",
            },
            request=request,
            security_level=SecurityLevel.MEDIUM,
            success=False,
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this notification",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete notification: {str(e)}",
        )
