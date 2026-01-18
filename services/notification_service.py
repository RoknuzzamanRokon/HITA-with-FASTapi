"""
Notification Service - Business logic layer for notifications
"""

from typing import Optional, Dict, Any, Tuple, List
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from models import (
    Notification,
    NotificationType,
    NotificationPriority,
    NotificationStatus,
    User,
)
from schemas import (
    NotificationCreate,
    NotificationResponse,
    NotificationListResponse,
    NotificationFilters,
    UnreadCountResponse,
    MarkAllReadResponse,
)
from repositories.notification_repository import (
    NotificationRepository,
    NotificationNotFoundError,
    UnauthorizedNotificationAccessError,
)
from cache_config import cache

# Configure logging
logger = logging.getLogger(__name__)


class NotificationService:
    """Service layer for notification business logic"""

    def __init__(self, db: Session):
        self.db = db
        self.repository = NotificationRepository(db)

    def create_notification(
        self,
        user_id: str,
        type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """
        Create a new notification

        Args:
            user_id: ID of the user to notify
            type: Type of notification
            title: Notification title
            message: Notification message
            priority: Priority level (default: MEDIUM)
            metadata: Additional context data

        Returns:
            Created Notification object
        """
        notification_data = NotificationCreate(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            priority=priority,
            meta_data=metadata,
        )

        notification = self.repository.create_notification(notification_data)
        logger.info(
            f"Created notification {notification.id} for user {user_id} (type: {type.value})"
        )

        return notification

    def get_notifications(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 25,
        filters: Optional[NotificationFilters] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> NotificationListResponse:
        """
        Get user notifications with pagination and filters

        Args:
            user_id: ID of the user
            page: Page number (1-indexed)
            limit: Number of results per page
            filters: Optional filters for status, type, priority
            sort_by: Field to sort by (created_at or priority)
            sort_order: Sort order (asc or desc)

        Returns:
            NotificationListResponse with notifications and metadata
        """
        if filters is None:
            filters = NotificationFilters()

        notifications, total = self.repository.get_notifications_with_pagination(
            user_id=user_id,
            page=page,
            limit=limit,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Get unread count
        unread_count = self.repository.get_unread_count(user_id)

        # Convert to response format
        notification_responses = [
            NotificationResponse.model_validate(notif) for notif in notifications
        ]

        # Calculate total pages
        total_pages = (total + limit - 1) // limit if total > 0 else 0

        return NotificationListResponse(
            notifications=notification_responses,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            unread_count=unread_count,
        )

    def mark_notification_read(
        self, notification_id: int, user_id: str
    ) -> Notification:
        """
        Mark a notification as read

        Args:
            notification_id: ID of the notification
            user_id: ID of the user

        Returns:
            Updated Notification object

        Raises:
            NotificationNotFoundError: If notification doesn't exist
            UnauthorizedNotificationAccessError: If user doesn't own the notification
        """
        notification = self.repository.mark_as_read(notification_id, user_id)
        logger.info(f"User {user_id} marked notification {notification_id} as read")

        return notification

    def mark_all_read(self, user_id: str) -> MarkAllReadResponse:
        """
        Mark all unread notifications as read for a user

        Args:
            user_id: ID of the user

        Returns:
            MarkAllReadResponse with count of updated notifications
        """
        updated_count = self.repository.mark_all_as_read(user_id)
        logger.info(f"User {user_id} marked {updated_count} notifications as read")

        return MarkAllReadResponse(
            updated_count=updated_count,
            message=f"Successfully marked {updated_count} notification(s) as read",
        )

    def delete_notification(self, notification_id: int, user_id: str) -> bool:
        """
        Delete a notification

        Args:
            notification_id: ID of the notification
            user_id: ID of the user

        Returns:
            True if deleted successfully

        Raises:
            NotificationNotFoundError: If notification doesn't exist
            UnauthorizedNotificationAccessError: If user doesn't own the notification
        """
        result = self.repository.delete_notification(notification_id, user_id)
        logger.info(f"User {user_id} deleted notification {notification_id}")

        return result

    def get_unread_count(self, user_id: str) -> UnreadCountResponse:
        """
        Get count of unread notifications for a user (Optimized)

        Args:
            user_id: ID of the user

        Returns:
            UnreadCountResponse with count and last notification timestamp

        Note:
            This method is optimized to use a single query instead of two.
            The result is cached at the route level for 30 seconds.
        """
        count = self.repository.get_unread_count(user_id)

        # Optimize: Only fetch last notification timestamp if there are unread notifications
        # This avoids an unnecessary query when count is 0
        last_notification_at = None
        if count > 0:
            # Get the most recent notification timestamp with a lightweight query
            last_notification = (
                self.db.query(Notification.created_at)
                .filter(Notification.user_id == user_id)
                .order_by(Notification.created_at.desc())
                .first()
            )
            last_notification_at = last_notification[0] if last_notification else None

        return UnreadCountResponse(
            unread_count=count, last_notification_at=last_notification_at
        )

    def notify_permission_change(
        self, user_id: str, action: str, supplier_name: str, admin_username: str
    ) -> Notification:
        """
        Create notification for permission change

        Args:
            user_id: ID of the user whose permissions changed
            action: Action performed (granted, revoked)
            supplier_name: Name of the supplier
            admin_username: Username of the admin who made the change

        Returns:
            Created Notification object
        """
        title = f"Permission {action.capitalize()}"
        message = (
            f"Your access to {supplier_name} has been {action} by {admin_username}."
        )

        metadata = {
            "action": action,
            "supplier_name": supplier_name,
            "admin_username": admin_username,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return self.create_notification(
            user_id=user_id,
            type=NotificationType.PERMISSION,
            title=title,
            message=message,
            priority=NotificationPriority.HIGH,
            metadata=metadata,
        )

    def notify_export_complete(
        self, user_id: str, export_id: str, export_type: str, file_path: str
    ) -> Notification:
        """
        Create notification for completed export

        Args:
            user_id: ID of the user who initiated the export
            export_id: ID of the export job
            export_type: Type of export (hotel, mapping, etc.)
            file_path: Path to the exported file

        Returns:
            Created Notification object
        """
        title = "Export Complete"
        message = f"Your {export_type} export is ready for download."

        metadata = {
            "export_id": export_id,
            "export_type": export_type,
            "file_path": file_path,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return self.create_notification(
            user_id=user_id,
            type=NotificationType.EXPORT,
            title=title,
            message=message,
            priority=NotificationPriority.MEDIUM,
            metadata=metadata,
        )

    def notify_point_transaction(
        self,
        user_id: str,
        transaction_type: str,
        points: int,
        from_user: Optional[str] = None,
    ) -> Notification:
        """
        Create notification for point transaction

        Args:
            user_id: ID of the user receiving the notification
            transaction_type: Type of transaction (received, deducted, allocated)
            points: Number of points involved
            from_user: Username of the sender (for received transactions)

        Returns:
            Created Notification object
        """
        if transaction_type == "received" and from_user:
            title = "Points Received"
            message = f"You received {points} points from {from_user}."
        elif transaction_type == "deducted":
            title = "Points Deducted"
            message = f"{points} points were deducted from your account."
        elif transaction_type == "allocated":
            title = "Points Allocated"
            message = f"{points} points have been allocated to your account."
        else:
            title = "Point Transaction"
            message = f"Your point balance has changed by {points} points."

        metadata = {
            "transaction_type": transaction_type,
            "points": points,
            "from_user": from_user,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Use HIGH priority for significant point changes (>= 1000 points)
        priority = (
            NotificationPriority.HIGH
            if abs(points) >= 1000
            else NotificationPriority.MEDIUM
        )

        return self.create_notification(
            user_id=user_id,
            type=NotificationType.POINT,
            title=title,
            message=message,
            priority=priority,
            metadata=metadata,
        )

    def notify_api_key_event(
        self,
        user_id: str,
        event_type: str,
        expires_at: Optional[datetime] = None,
    ) -> Notification:
        """
        Create notification for API key events

        Args:
            user_id: ID of the user
            event_type: Type of event (created, expiring, expired)
            expires_at: Expiration timestamp (for created/expiring events)

        Returns:
            Created Notification object
        """
        if event_type == "created":
            title = "API Key Created"
            message = "A new API key has been generated for your account."
            priority = NotificationPriority.MEDIUM
        elif event_type == "expiring":
            title = "API Key Expiring Soon"
            message = f"Your API key will expire on {expires_at.strftime('%Y-%m-%d')}."
            priority = NotificationPriority.HIGH
        elif event_type == "expired":
            title = "API Key Expired"
            message = "Your API key has expired. Please generate a new one."
            priority = NotificationPriority.CRITICAL
        else:
            title = "API Key Event"
            message = f"An API key event occurred: {event_type}"
            priority = NotificationPriority.MEDIUM

        metadata = {
            "event_type": event_type,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return self.create_notification(
            user_id=user_id,
            type=NotificationType.API_KEY,
            title=title,
            message=message,
            priority=priority,
            metadata=metadata,
        )

    def notify_system_maintenance(
        self, scheduled_at: datetime, duration: str, description: str
    ) -> List[Notification]:
        """
        Create system maintenance notifications for all active users

        Args:
            scheduled_at: When the maintenance is scheduled
            duration: Expected duration of maintenance
            description: Description of the maintenance

        Returns:
            List of created Notification objects
        """
        title = "Scheduled System Maintenance"
        message = f"System maintenance is scheduled for {scheduled_at.strftime('%Y-%m-%d %H:%M UTC')}. Expected duration: {duration}. {description}"

        metadata = {
            "scheduled_at": scheduled_at.isoformat(),
            "duration": duration,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Get all active users
        active_users = self.db.query(User).filter(User.is_active == True).all()

        notifications = []
        for user in active_users:
            notification = self.create_notification(
                user_id=user.id,
                type=NotificationType.MAINTENANCE,
                title=title,
                message=message,
                priority=NotificationPriority.HIGH,
                metadata=metadata,
            )
            notifications.append(notification)

        logger.info(f"Created {len(notifications)} system maintenance notifications")

        return notifications

    def cleanup_old_notifications(self, retention_days: int = 90) -> int:
        """
        Clean up old read notifications

        Args:
            retention_days: Number of days to retain notifications (default: 90)

        Returns:
            Count of notifications deleted
        """
        deleted_count = self.repository.delete_old_notifications(retention_days)

        logger.info(
            f"Cleanup job completed: deleted {deleted_count} notifications older than {retention_days} days"
        )

        return deleted_count
