"""
Property-based tests for notification system using Hypothesis

These tests verify universal properties that should hold across all valid executions.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import datetime, timedelta
from models import NotificationType, NotificationPriority, NotificationStatus
from schemas import NotificationCreate, NotificationFilters
from repositories.notification_repository import NotificationRepository
import time


# Custom strategies for notification data
@st.composite
def notification_type_strategy(draw):
    """Strategy for generating NotificationType values"""
    return draw(st.sampled_from(list(NotificationType)))


@st.composite
def notification_priority_strategy(draw):
    """Strategy for generating NotificationPriority values"""
    return draw(st.sampled_from(list(NotificationPriority)))


@st.composite
def user_id_strategy(draw):
    """Strategy for generating user IDs (10 character strings)"""
    return draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=10,
            max_size=10,
        )
    )


@st.composite
def notification_create_strategy(draw, user_id=None):
    """Strategy for generating NotificationCreate objects"""
    if user_id is None:
        user_id = draw(user_id_strategy())

    return NotificationCreate(
        user_id=user_id,
        type=draw(notification_type_strategy()),
        priority=draw(notification_priority_strategy()),
        title=draw(st.text(min_size=1, max_size=255)),
        message=draw(st.text(min_size=1, max_size=1000)),
        meta_data=draw(
            st.none()
            | st.dictionaries(
                st.text(min_size=1, max_size=50),
                st.text(min_size=1, max_size=100),
                max_size=5,
            )
        ),
    )


class TestNotificationCreationProperties:
    """
    Property tests for notification creation
    """

    @given(
        user_id=user_id_strategy(),
        notification_type=notification_type_strategy(),
        priority=notification_priority_strategy(),
        title=st.text(min_size=1, max_size=255),
        message=st.text(min_size=1, max_size=1000),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_1_notification_creation_stores_all_fields(
        self, test_db, user_id, notification_type, priority, title, message
    ):
        """
        Feature: notification-system, Property 1: Notification creation stores all required fields
        Validates: Requirements 1.2, 1.3, 1.5

        For any notification creation request with valid data, the stored notification
        should contain type, priority, title, message, timestamp, user_id, and initial
        status of unread.
        """
        # Arrange
        repository = NotificationRepository(test_db)
        notification_data = NotificationCreate(
            user_id=user_id,
            type=notification_type,
            priority=priority,
            title=title,
            message=message,
            meta_data=None,
        )

        # Act
        notification = repository.create_notification(notification_data)

        # Assert - All required fields are present
        assert notification.id is not None, "Notification should have an ID"
        assert notification.user_id == user_id, "User ID should match"
        assert notification.type == notification_type, "Type should match"
        assert notification.priority == priority, "Priority should match"
        assert notification.title == title, "Title should match"
        assert notification.message == message, "Message should match"
        assert (
            notification.status == NotificationStatus.UNREAD
        ), "Initial status should be UNREAD"
        assert notification.created_at is not None, "Created timestamp should be set"
        assert isinstance(
            notification.created_at, datetime
        ), "Created_at should be a datetime"
        assert (
            notification.read_at is None
        ), "Read_at should be None for new notifications"


class TestChronologicalOrderingProperties:
    """
    Property tests for chronological ordering
    """

    @given(
        user_id=user_id_strategy(),
        notification_count=st.integers(min_value=2, max_value=10),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_2_chronological_ordering_maintained(
        self, test_db, user_id, notification_count
    ):
        """
        Feature: notification-system, Property 2: Chronological ordering is maintained
        Validates: Requirements 1.4

        For any user with multiple notifications, retrieving their notifications
        should return them ordered by creation timestamp in descending order (newest first).
        """
        # Arrange
        repository = NotificationRepository(test_db)
        created_notifications = []

        # Create multiple notifications with slight time delays
        for i in range(notification_count):
            notification_data = NotificationCreate(
                user_id=user_id,
                type=NotificationType.SYSTEM,
                priority=NotificationPriority.MEDIUM,
                title=f"Notification {i}",
                message=f"Message {i}",
                meta_data=None,
            )
            notification = repository.create_notification(notification_data)
            created_notifications.append(notification)
            # Small delay to ensure different timestamps
            time.sleep(0.01)

        # Act
        filters = NotificationFilters()
        retrieved_notifications, total = repository.get_notifications_with_pagination(
            user_id=user_id,
            page=1,
            limit=notification_count,
            filters=filters,
            sort_by="created_at",
            sort_order="desc",
        )

        # Assert - Notifications are in chronological order (newest first)
        assert (
            len(retrieved_notifications) == notification_count
        ), "Should retrieve all notifications"

        for i in range(len(retrieved_notifications) - 1):
            current_time = retrieved_notifications[i].created_at
            next_time = retrieved_notifications[i + 1].created_at
            assert (
                current_time >= next_time
            ), f"Notification {i} should be newer than notification {i+1}"


class TestUserIsolationProperties:
    """
    Property tests for user isolation
    """

    @given(
        user1_id=user_id_strategy(),
        user2_id=user_id_strategy(),
        notification_count=st.integers(min_value=1, max_value=5),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_3_user_isolation_in_retrieval(
        self, test_db, user1_id, user2_id, notification_count
    ):
        """
        Feature: notification-system, Property 3: User isolation in notification retrieval
        Validates: Requirements 2.1

        For any user requesting their notifications, the returned list should only
        contain notifications where the user_id matches the requesting user's ID.
        """
        # Ensure users are different
        assume(user1_id != user2_id)

        # Clear any existing notifications from previous examples
        from models import Notification
        from repositories.repository_config import query_cache

        test_db.query(Notification).delete()
        test_db.commit()

        # Clear the query cache to avoid stale results
        query_cache.clear()

        # Arrange
        repository = NotificationRepository(test_db)

        # Create notifications for user1
        for i in range(notification_count):
            notification_data = NotificationCreate(
                user_id=user1_id,
                type=NotificationType.SYSTEM,
                priority=NotificationPriority.MEDIUM,
                title=f"User1 Notification {i}",
                message=f"Message for user1 {i}",
                meta_data=None,
            )
            repository.create_notification(notification_data)

        # Create notifications for user2
        for i in range(notification_count):
            notification_data = NotificationCreate(
                user_id=user2_id,
                type=NotificationType.PERMISSION,
                priority=NotificationPriority.HIGH,
                title=f"User2 Notification {i}",
                message=f"Message for user2 {i}",
                meta_data=None,
            )
            repository.create_notification(notification_data)

        # Act - Retrieve notifications for user1
        filters = NotificationFilters()
        user1_notifications, user1_total = repository.get_notifications_with_pagination(
            user_id=user1_id, page=1, limit=100, filters=filters
        )

        # Assert - All retrieved notifications belong to user1
        assert (
            len(user1_notifications) == notification_count
        ), f"Should retrieve exactly {notification_count} notifications for user1"

        for notification in user1_notifications:
            assert (
                notification.user_id == user1_id
            ), "All notifications should belong to user1"
            assert (
                notification.user_id != user2_id
            ), "No notifications should belong to user2"

        # Act - Retrieve notifications for user2
        user2_notifications, user2_total = repository.get_notifications_with_pagination(
            user_id=user2_id, page=1, limit=100, filters=filters
        )

        # Assert - All retrieved notifications belong to user2
        assert (
            len(user2_notifications) == notification_count
        ), f"Should retrieve exactly {notification_count} notifications for user2"

        for notification in user2_notifications:
            assert (
                notification.user_id == user2_id
            ), "All notifications should belong to user2"
            assert (
                notification.user_id != user1_id
            ), "No notifications should belong to user1"
