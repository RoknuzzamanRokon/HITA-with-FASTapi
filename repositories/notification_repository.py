"""
Notification Repository - Data access layer for notifications
"""

from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, asc
from datetime import datetime, timedelta
from models import (
    Notification,
    NotificationType,
    NotificationPriority,
    NotificationStatus,
)
from schemas import NotificationCreate, NotificationFilters
from .repository_config import (
    RepositoryConfig,
    cached_query,
    monitor_performance,
    repository_metrics,
)


class NotificationNotFoundError(Exception):
    """Raised when a notification is not found"""

    pass


class UnauthorizedNotificationAccessError(Exception):
    """Raised when a user attempts to access another user's notification"""

    pass


class NotificationRepository:
    """Repository for notification data access with optimized queries"""

    def __init__(self, db: Session):
        self.db = db

    @monitor_performance("create_notification")
    def create_notification(
        self, notification_data: NotificationCreate
    ) -> Notification:
        """
        Create a new notification

        Args:
            notification_data: NotificationCreate schema with notification details

        Returns:
            Created Notification object
        """
        repository_metrics.increment_query_count()

        notification = Notification(
            user_id=notification_data.user_id,
            type=notification_data.type,
            priority=notification_data.priority,
            title=notification_data.title,
            message=notification_data.message,
            status=NotificationStatus.UNREAD,
            metadata=notification_data.meta_data,
            created_at=datetime.utcnow(),
        )

        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)

        return notification

    @monitor_performance("get_notification_by_id")
    def get_notification_by_id(
        self, notification_id: int, user_id: str
    ) -> Optional[Notification]:
        """
        Get a notification by ID with user authorization check

        Args:
            notification_id: ID of the notification
            user_id: ID of the user requesting the notification

        Returns:
            Notification object if found and authorized

        Raises:
            NotificationNotFoundError: If notification doesn't exist
            UnauthorizedNotificationAccessError: If user doesn't own the notification
        """
        repository_metrics.increment_query_count()

        notification = (
            self.db.query(Notification)
            .filter(Notification.id == notification_id)
            .first()
        )

        if not notification:
            raise NotificationNotFoundError(f"Notification {notification_id} not found")

        if notification.user_id != user_id:
            raise UnauthorizedNotificationAccessError(
                f"User {user_id} not authorized to access notification {notification_id}"
            )

        return notification

    @monitor_performance("get_notifications_with_pagination")
    @cached_query(["user_id", "page", "limit", "filters", "sort_by", "sort_order"])
    def get_notifications_with_pagination(
        self,
        user_id: str,
        page: int,
        limit: int,
        filters: NotificationFilters,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Notification], int]:
        """
        Get user notifications with pagination and filtering

        Args:
            user_id: ID of the user
            page: Page number (1-indexed)
            limit: Number of results per page
            filters: NotificationFilters object with filter criteria
            sort_by: Field to sort by (created_at or priority)
            sort_order: Sort order (asc or desc)

        Returns:
            Tuple of (notifications list, total count)
        """
        repository_metrics.increment_query_count()

        # Validate and adjust pagination parameters
        limit = min(limit, RepositoryConfig.MAX_PAGE_SIZE)
        page = max(1, page)

        # Base query - always filter by user_id for security
        query = self.db.query(Notification).filter(Notification.user_id == user_id)

        # Apply filters
        query = self._apply_filters(query, filters)

        # Get total count before pagination
        total = query.count()

        # Apply sorting
        query = self._apply_sorting(query, sort_by, sort_order)

        # Apply pagination
        notifications = query.offset((page - 1) * limit).limit(limit).all()

        return notifications, total

    def _apply_filters(self, query, filters: NotificationFilters):
        """
        Apply filters to the notification query

        Args:
            query: SQLAlchemy query object
            filters: NotificationFilters object

        Returns:
            Filtered query object
        """
        if filters.status is not None:
            query = query.filter(Notification.status == filters.status)

        if filters.type is not None:
            query = query.filter(Notification.type == filters.type)

        if filters.priority is not None:
            query = query.filter(Notification.priority == filters.priority)

        if filters.created_after:
            query = query.filter(Notification.created_at >= filters.created_after)

        if filters.created_before:
            query = query.filter(Notification.created_at <= filters.created_before)

        return query

    def _apply_sorting(self, query, sort_by: str, sort_order: str):
        """
        Apply sorting to the notification query

        Args:
            query: SQLAlchemy query object
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)

        Returns:
            Sorted query object
        """
        sort_column = None

        if sort_by == "created_at":
            sort_column = Notification.created_at
        elif sort_by == "priority":
            # Priority sorting: critical > high > medium > low
            # Map priority to numeric values for sorting
            priority_order = {
                NotificationPriority.CRITICAL: 4,
                NotificationPriority.HIGH: 3,
                NotificationPriority.MEDIUM: 2,
                NotificationPriority.LOW: 1,
            }
            # Use CASE statement for priority ordering
            from sqlalchemy import case

            sort_column = case(
                (Notification.priority == NotificationPriority.CRITICAL.value, 4),
                (Notification.priority == NotificationPriority.HIGH.value, 3),
                (Notification.priority == NotificationPriority.MEDIUM.value, 2),
                (Notification.priority == NotificationPriority.LOW.value, 1),
                else_=0,
            )
        else:
            # Default to created_at
            sort_column = Notification.created_at

        if sort_order.lower() == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

        return query

    @monitor_performance("mark_as_read")
    def mark_as_read(
        self, notification_id: int, user_id: str
    ) -> Optional[Notification]:
        """
        Mark a single notification as read

        Args:
            notification_id: ID of the notification
            user_id: ID of the user

        Returns:
            Updated Notification object

        Raises:
            NotificationNotFoundError: If notification doesn't exist
            UnauthorizedNotificationAccessError: If user doesn't own the notification
        """
        repository_metrics.increment_query_count()

        # Get notification with authorization check
        notification = self.get_notification_by_id(notification_id, user_id)

        # Update status and read timestamp
        notification.status = NotificationStatus.READ
        notification.read_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(notification)

        return notification

    @monitor_performance("mark_all_as_read")
    def mark_all_as_read(self, user_id: str) -> int:
        """
        Mark all unread notifications as read for a user

        Args:
            user_id: ID of the user

        Returns:
            Count of notifications updated
        """
        repository_metrics.increment_query_count()

        current_time = datetime.utcnow()

        # Update all unread notifications for the user
        updated_count = (
            self.db.query(Notification)
            .filter(
                and_(
                    Notification.user_id == user_id,
                    Notification.status == NotificationStatus.UNREAD,
                )
            )
            .update(
                {"status": NotificationStatus.READ, "read_at": current_time},
                synchronize_session=False,
            )
        )

        self.db.commit()

        return updated_count

    @monitor_performance("get_unread_count")
    def get_unread_count(self, user_id: str) -> int:
        """
        Get count of unread notifications for a user

        Args:
            user_id: ID of the user

        Returns:
            Count of unread notifications
        """
        repository_metrics.increment_query_count()

        count = (
            self.db.query(func.count(Notification.id))
            .filter(
                and_(
                    Notification.user_id == user_id,
                    Notification.status == NotificationStatus.UNREAD,
                )
            )
            .scalar()
        )

        return count or 0

    @monitor_performance("delete_notification")
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
        repository_metrics.increment_query_count()

        # Get notification with authorization check
        notification = self.get_notification_by_id(notification_id, user_id)

        # Delete the notification
        self.db.delete(notification)
        self.db.commit()

        return True

    @monitor_performance("delete_old_notifications")
    def delete_old_notifications(self, retention_days: int = 90) -> int:
        """
        Delete read notifications older than retention period

        Args:
            retention_days: Number of days to retain notifications

        Returns:
            Count of notifications deleted
        """
        repository_metrics.increment_query_count()

        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Delete only read notifications older than retention period
        deleted_count = (
            self.db.query(Notification)
            .filter(
                and_(
                    Notification.status == NotificationStatus.READ,
                    Notification.created_at < cutoff_date,
                )
            )
            .delete(synchronize_session=False)
        )

        self.db.commit()

        return deleted_count
