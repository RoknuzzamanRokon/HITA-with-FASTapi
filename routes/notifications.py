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
    NotificationCreate,
)
from models import NotificationType, NotificationPriority, NotificationStatus, UserRole
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel
from cache_config import cache, CacheConfig


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
    Get Unread Notification Count (Optimized with Caching)

    Retrieve the count of unread notifications for the authenticated user.

    **Performance Optimizations:**
    - Redis caching with 30-second TTL (reduces DB load by ~83%)
    - Cache invalidation on notification state changes
    - Lightweight response (no database joins)

    **Recommended Frontend Polling:**
    - Use 15-30 second intervals instead of 5 seconds
    - Consider WebSocket for real-time updates
    - Implement exponential backoff when no changes detected
    """
    try:
        # Build cache key for this user's unread count
        cache_key = f"notification:unread_count:{current_user.id}"

        # Try to get from cache first (30-second TTL)
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            return UnreadCountResponse(**cached_response)

        # Cache miss - query database
        service = NotificationService(db)
        response = service.get_unread_count(current_user.id)

        # Cache the response for 30 seconds
        # This means: 5s polling = only 1 DB query per 30s = 83% reduction
        cache.set(cache_key, response.dict(), ttl=30)

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
    """
    try:
        # Create service instance
        service = NotificationService(db)

        # Mark notification as read
        notification = service.mark_notification_read(notification_id, current_user.id)

        # Invalidate unread count cache for this user
        cache_key = f"notification:unread_count:{current_user.id}"
        cache.delete(cache_key)

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
    """
    try:
        # Create service instance
        service = NotificationService(db)

        # Mark all notifications as read
        response = service.mark_all_read(current_user.id)

        # Invalidate unread count cache for this user
        cache_key = f"notification:unread_count:{current_user.id}"
        cache.delete(cache_key)

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


@router.post("/admin/create", response_model=NotificationResponse)
async def create_notification_admin(
    notification_data: NotificationCreate,
    request: Request,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Create Notification (Admin Only)

    Create a new notification for any user. This endpoint is restricted to admin users only.
    """
    try:
        # Check user permissions
        if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_user or admin_user can create notifications.",
            )

        # Verify target user exists
        target_user = (
            db.query(models.User)
            .filter(models.User.id == notification_data.user_id)
            .first()
        )
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {notification_data.user_id} not found",
            )

        # Create service instance
        service = NotificationService(db)

        # Create notification
        notification = service.create_notification(
            user_id=notification_data.user_id,
            type=notification_data.type,
            title=notification_data.title,
            message=notification_data.message,
            priority=notification_data.priority,
            metadata=notification_data.meta_data,
        )

        # Log admin action
        audit_logger = AuditLogger(db)
        audit_logger.log_activity(
            activity_type=ActivityType.USER_UPDATED,
            user_id=current_user.id,
            details={
                "action": "create_notification",
                "target_user_id": notification_data.user_id,
                "notification_id": notification.id,
                "notification_type": notification_data.type.value,
                "title": notification_data.title,
            },
            request=request,
            security_level=SecurityLevel.MEDIUM,
            success=True,
        )

        # Convert to response format
        return NotificationResponse.model_validate(notification)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create notification: {str(e)}",
        )


@router.post("/admin/broadcast")
async def broadcast_notification_admin(
    notification_data: dict,
    request: Request,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Broadcast Notification to All Users (Admin Only)

    Create a notification for all active users in the system.
    """
    try:
        # Check user permissions
        if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_user or admin_user can broadcast notifications.",
            )

        # Validate required fields
        required_fields = ["type", "title", "message"]
        for field in required_fields:
            if field not in notification_data:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Missing required field: {field}",
                )

        # Get all active users
        active_users = db.query(models.User).filter(models.User.is_active == True).all()

        if not active_users:
            return {
                "count": 0,
                "message": "No active users found to notify",
            }

        # Create service instance
        service = NotificationService(db)

        # Create notifications for all users
        created_notifications = []
        for user in active_users:
            try:
                notification = service.create_notification(
                    user_id=user.id,
                    type=NotificationType(notification_data["type"]),
                    title=notification_data["title"],
                    message=notification_data["message"],
                    priority=NotificationPriority(
                        notification_data.get("priority", "medium")
                    ),
                    metadata=notification_data.get("meta_data"),
                )
                created_notifications.append(notification)
            except Exception as e:
                # Log individual failures but continue
                print(f"Failed to create notification for user {user.id}: {str(e)}")

        return {
            "count": len(created_notifications),
            "message": f"Successfully created {len(created_notifications)} notifications for active users",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to broadcast notification: {str(e)}",
        )
