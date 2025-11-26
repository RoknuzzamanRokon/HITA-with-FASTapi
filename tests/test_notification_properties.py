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


class TestMarkAsReadProperties:
    """
    Property tests for mark as read operations
    """

    @given(
        user_id=user_id_strategy(),
        notification_data=notification_create_strategy(),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_9_mark_as_read_updates_status_and_timestamp(
        self, test_db, user_id, notification_data
    ):
        """
        Feature: notification-system, Property 9: Mark as read updates status and timestamp
        Validates: Requirements 4.1, 4.2

        For any unread notification that is marked as read, the notification's status
        should change to "read" and read_at should be set to a timestamp close to the
        current time.
        """
        # Arrange
        repository = NotificationRepository(test_db)

        # Override user_id to ensure consistency
        notification_data.user_id = user_id

        # Create an unread notification
        notification = repository.create_notification(notification_data)
        assert notification.status == NotificationStatus.UNREAD
        assert notification.read_at is None

        # Record time before marking as read
        time_before = datetime.utcnow()

        # Act
        updated_notification = repository.mark_as_read(notification.id, user_id)

        # Record time after marking as read
        time_after = datetime.utcnow()

        # Assert - Status changed to READ
        assert (
            updated_notification.status == NotificationStatus.READ
        ), "Status should be READ after marking as read"

        # Assert - read_at timestamp is set
        assert (
            updated_notification.read_at is not None
        ), "read_at should be set after marking as read"

        # Assert - read_at is within reasonable time window
        assert (
            time_before <= updated_notification.read_at <= time_after
        ), "read_at should be close to current time"

    @given(
        user_id=user_id_strategy(),
        notification_data=notification_create_strategy(),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_10_mark_as_read_persists_changes(
        self, test_db, user_id, notification_data
    ):
        """
        Feature: notification-system, Property 10: Mark as read persists changes
        Validates: Requirements 4.5

        For any notification marked as read, querying the notification afterward
        should show status as "read" with a non-null read_at timestamp.
        """
        # Arrange
        repository = NotificationRepository(test_db)

        # Override user_id to ensure consistency
        notification_data.user_id = user_id

        # Create an unread notification
        notification = repository.create_notification(notification_data)
        notification_id = notification.id

        # Act - Mark as read
        repository.mark_as_read(notification_id, user_id)

        # Query the notification again to verify persistence
        retrieved_notification = repository.get_notification_by_id(
            notification_id, user_id
        )

        # Assert - Changes persisted
        assert (
            retrieved_notification.status == NotificationStatus.READ
        ), "Status should remain READ after retrieval"
        assert (
            retrieved_notification.read_at is not None
        ), "read_at should remain set after retrieval"
        assert isinstance(
            retrieved_notification.read_at, datetime
        ), "read_at should be a datetime object"


class TestBulkMarkAsReadProperties:
    """
    Property tests for bulk mark as read operations
    """

    @given(
        user_id=user_id_strategy(),
        unread_count=st.integers(min_value=1, max_value=10),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_11_bulk_mark_as_read_updates_all_unread(
        self, test_db, user_id, unread_count
    ):
        """
        Feature: notification-system, Property 11: Bulk mark as read updates all unread notifications
        Validates: Requirements 5.1, 5.2

        For any user with N unread notifications, marking all as read should result
        in all N notifications having status "read" and non-null read_at timestamps.
        """
        # Arrange
        repository = NotificationRepository(test_db)

        # Create unread notifications
        notification_ids = []
        for i in range(unread_count):
            notification_data = NotificationCreate(
                user_id=user_id,
                type=NotificationType.SYSTEM,
                priority=NotificationPriority.MEDIUM,
                title=f"Notification {i}",
                message=f"Message {i}",
                meta_data=None,
            )
            notification = repository.create_notification(notification_data)
            notification_ids.append(notification.id)

        # Act - Mark all as read
        updated_count = repository.mark_all_as_read(user_id)

        # Assert - All notifications are now read
        for notification_id in notification_ids:
            notification = repository.get_notification_by_id(notification_id, user_id)
            assert (
                notification.status == NotificationStatus.READ
            ), f"Notification {notification_id} should be READ"
            assert (
                notification.read_at is not None
            ), f"Notification {notification_id} should have read_at set"
            assert isinstance(
                notification.read_at, datetime
            ), f"read_at should be a datetime for notification {notification_id}"

    @given(
        user_id=user_id_strategy(),
        unread_count=st.integers(min_value=1, max_value=10),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_12_bulk_mark_as_read_returns_correct_count(
        self, test_db, user_id, unread_count
    ):
        """
        Feature: notification-system, Property 12: Bulk mark as read returns correct count
        Validates: Requirements 5.4

        For any user with N unread notifications, the mark-all-as-read operation
        should return a count equal to N.
        """
        # Arrange
        repository = NotificationRepository(test_db)

        # Create unread notifications
        for i in range(unread_count):
            notification_data = NotificationCreate(
                user_id=user_id,
                type=NotificationType.SYSTEM,
                priority=NotificationPriority.MEDIUM,
                title=f"Notification {i}",
                message=f"Message {i}",
                meta_data=None,
            )
            repository.create_notification(notification_data)

        # Act - Mark all as read
        updated_count = repository.mark_all_as_read(user_id)

        # Assert - Count matches number of unread notifications
        assert (
            updated_count == unread_count
        ), f"Should update exactly {unread_count} notifications, but updated {updated_count}"

    @given(
        user_id=user_id_strategy(),
        unread_count=st.integers(min_value=1, max_value=10),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_13_bulk_mark_as_read_persists_changes(
        self, test_db, user_id, unread_count
    ):
        """
        Feature: notification-system, Property 13: Bulk mark as read persists changes
        Validates: Requirements 5.5

        For any user who marks all notifications as read, subsequent queries
        should show zero unread notifications.
        """
        # Arrange
        repository = NotificationRepository(test_db)

        # Create unread notifications
        for i in range(unread_count):
            notification_data = NotificationCreate(
                user_id=user_id,
                type=NotificationType.SYSTEM,
                priority=NotificationPriority.MEDIUM,
                title=f"Notification {i}",
                message=f"Message {i}",
                meta_data=None,
            )
            repository.create_notification(notification_data)

        # Verify initial unread count
        initial_unread = repository.get_unread_count(user_id)
        assert (
            initial_unread == unread_count
        ), f"Should have {unread_count} unread notifications initially"

        # Act - Mark all as read
        repository.mark_all_as_read(user_id)

        # Assert - Unread count is now zero
        final_unread = repository.get_unread_count(user_id)
        assert (
            final_unread == 0
        ), "Should have 0 unread notifications after marking all as read"


class TestDeletionProperties:
    """
    Property tests for notification deletion
    """

    @given(
        user_id=user_id_strategy(),
        notification_data=notification_create_strategy(),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_14_deletion_removes_notification_permanently(
        self, test_db, user_id, notification_data
    ):
        """
        Feature: notification-system, Property 14: Deletion removes notification permanently
        Validates: Requirements 6.1, 6.4

        For any notification that is deleted, subsequent attempts to retrieve
        that notification by ID should fail with a not-found error.
        """
        from repositories.notification_repository import NotificationNotFoundError

        # Arrange
        repository = NotificationRepository(test_db)

        # Override user_id to ensure consistency
        notification_data.user_id = user_id

        # Create a notification
        notification = repository.create_notification(notification_data)
        notification_id = notification.id

        # Verify notification exists
        retrieved = repository.get_notification_by_id(notification_id, user_id)
        assert retrieved is not None, "Notification should exist before deletion"

        # Act - Delete the notification
        result = repository.delete_notification(notification_id, user_id)
        assert result is True, "Deletion should return True"

        # Assert - Attempting to retrieve should raise NotificationNotFoundError
        with pytest.raises(NotificationNotFoundError):
            repository.get_notification_by_id(notification_id, user_id)


class TestUnreadCountProperties:
    """
    Property tests for unread count operations
    """

    @given(
        user_id=user_id_strategy(),
        unread_count=st.integers(min_value=0, max_value=10),
        read_count=st.integers(min_value=0, max_value=10),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_15_unread_count_accuracy(
        self, test_db, user_id, unread_count, read_count
    ):
        """
        Feature: notification-system, Property 15: Unread count accuracy
        Validates: Requirements 7.1

        For any user, the unread count should equal the number of notifications
        with status "unread" belonging to that user.
        """
        # Clear any existing notifications
        from models import Notification
        from repositories.repository_config import query_cache

        test_db.query(Notification).delete()
        test_db.commit()
        query_cache.clear()

        # Arrange
        repository = NotificationRepository(test_db)

        # Create unread notifications
        for i in range(unread_count):
            notification_data = NotificationCreate(
                user_id=user_id,
                type=NotificationType.SYSTEM,
                priority=NotificationPriority.MEDIUM,
                title=f"Unread Notification {i}",
                message=f"Unread Message {i}",
                meta_data=None,
            )
            repository.create_notification(notification_data)

        # Create read notifications
        for i in range(read_count):
            notification_data = NotificationCreate(
                user_id=user_id,
                type=NotificationType.PERMISSION,
                priority=NotificationPriority.HIGH,
                title=f"Read Notification {i}",
                message=f"Read Message {i}",
                meta_data=None,
            )
            notification = repository.create_notification(notification_data)
            # Mark as read
            repository.mark_as_read(notification.id, user_id)

        # Act - Get unread count
        actual_unread_count = repository.get_unread_count(user_id)

        # Assert - Count matches expected unread count
        assert (
            actual_unread_count == unread_count
        ), f"Expected {unread_count} unread notifications, but got {actual_unread_count}"

    @given(
        user1_id=user_id_strategy(),
        user2_id=user_id_strategy(),
        user1_unread=st.integers(min_value=1, max_value=5),
        user2_unread=st.integers(min_value=1, max_value=5),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_16_unread_count_respects_user_isolation(
        self, test_db, user1_id, user2_id, user1_unread, user2_unread
    ):
        """
        Feature: notification-system, Property 16: Unread count respects user isolation
        Validates: Requirements 7.3

        For any user requesting their unread count, the count should only include
        notifications where user_id matches the requesting user's ID.
        """
        # Ensure users are different
        assume(user1_id != user2_id)

        # Clear any existing notifications
        from models import Notification
        from repositories.repository_config import query_cache

        test_db.query(Notification).delete()
        test_db.commit()
        query_cache.clear()

        # Arrange
        repository = NotificationRepository(test_db)

        # Create unread notifications for user1
        for i in range(user1_unread):
            notification_data = NotificationCreate(
                user_id=user1_id,
                type=NotificationType.SYSTEM,
                priority=NotificationPriority.MEDIUM,
                title=f"User1 Notification {i}",
                message=f"User1 Message {i}",
                meta_data=None,
            )
            repository.create_notification(notification_data)

        # Create unread notifications for user2
        for i in range(user2_unread):
            notification_data = NotificationCreate(
                user_id=user2_id,
                type=NotificationType.PERMISSION,
                priority=NotificationPriority.HIGH,
                title=f"User2 Notification {i}",
                message=f"User2 Message {i}",
                meta_data=None,
            )
            repository.create_notification(notification_data)

        # Act - Get unread counts for both users
        user1_count = repository.get_unread_count(user1_id)
        user2_count = repository.get_unread_count(user2_id)

        # Assert - Each user's count matches only their notifications
        assert (
            user1_count == user1_unread
        ), f"User1 should have {user1_unread} unread notifications, but got {user1_count}"
        assert (
            user2_count == user2_unread
        ), f"User2 should have {user2_unread} unread notifications, but got {user2_count}"


class TestFilterCorrectnessProperties:
    """
    Property tests for filter correctness
    """

    @given(
        user_id=user_id_strategy(),
        status_filter=st.sampled_from(
            [NotificationStatus.READ, NotificationStatus.UNREAD]
        ),
        notification_count=st.integers(min_value=2, max_value=10),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_6_status_filter_correctness(
        self, test_db, user_id, status_filter, notification_count
    ):
        """
        Feature: notification-system, Property 6: Status filter correctness
        Validates: Requirements 3.1

        For any status filter value (read/unread), all returned notifications
        should have a status matching the filter value.
        """
        # Clear any existing notifications
        from models import Notification
        from repositories.repository_config import query_cache

        test_db.query(Notification).delete()
        test_db.commit()
        query_cache.clear()

        # Arrange
        repository = NotificationRepository(test_db)

        # Create notifications with the target status
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

            # Mark as read if filter is READ
            if status_filter == NotificationStatus.READ:
                repository.mark_as_read(notification.id, user_id)

        # Create some notifications with opposite status
        opposite_status = (
            NotificationStatus.READ
            if status_filter == NotificationStatus.UNREAD
            else NotificationStatus.UNREAD
        )
        for i in range(notification_count):
            notification_data = NotificationCreate(
                user_id=user_id,
                type=NotificationType.PERMISSION,
                priority=NotificationPriority.HIGH,
                title=f"Opposite Notification {i}",
                message=f"Opposite Message {i}",
                meta_data=None,
            )
            notification = repository.create_notification(notification_data)

            # Mark as read if opposite status is READ
            if opposite_status == NotificationStatus.READ:
                repository.mark_as_read(notification.id, user_id)

        # Act - Filter by status
        filters = NotificationFilters(status=status_filter)
        filtered_notifications, total = repository.get_notifications_with_pagination(
            user_id=user_id, page=1, limit=100, filters=filters
        )

        # Assert - All returned notifications match the filter
        assert (
            len(filtered_notifications) == notification_count
        ), f"Should return {notification_count} notifications with status {status_filter}"

        for notification in filtered_notifications:
            assert (
                notification.status == status_filter
            ), f"All notifications should have status {status_filter}, but got {notification.status}"

    @given(
        user_id=user_id_strategy(),
        type_filter=notification_type_strategy(),
        notification_count=st.integers(min_value=2, max_value=10),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_7_type_filter_correctness(
        self, test_db, user_id, type_filter, notification_count
    ):
        """
        Feature: notification-system, Property 7: Type filter correctness
        Validates: Requirements 3.2

        For any notification type filter, all returned notifications should
        have a type matching the filter value.
        """
        # Clear any existing notifications
        from models import Notification
        from repositories.repository_config import query_cache

        test_db.query(Notification).delete()
        test_db.commit()
        query_cache.clear()

        # Arrange
        repository = NotificationRepository(test_db)

        # Create notifications with the target type
        for i in range(notification_count):
            notification_data = NotificationCreate(
                user_id=user_id,
                type=type_filter,
                priority=NotificationPriority.MEDIUM,
                title=f"Notification {i}",
                message=f"Message {i}",
                meta_data=None,
            )
            repository.create_notification(notification_data)

        # Create some notifications with different type
        other_types = [t for t in NotificationType if t != type_filter]
        if other_types:
            for i in range(notification_count):
                notification_data = NotificationCreate(
                    user_id=user_id,
                    type=other_types[0],
                    priority=NotificationPriority.HIGH,
                    title=f"Other Notification {i}",
                    message=f"Other Message {i}",
                    meta_data=None,
                )
                repository.create_notification(notification_data)

        # Act - Filter by type
        filters = NotificationFilters(type=type_filter)
        filtered_notifications, total = repository.get_notifications_with_pagination(
            user_id=user_id, page=1, limit=100, filters=filters
        )

        # Assert - All returned notifications match the filter
        assert (
            len(filtered_notifications) == notification_count
        ), f"Should return {notification_count} notifications with type {type_filter}"

        for notification in filtered_notifications:
            assert (
                notification.type == type_filter
            ), f"All notifications should have type {type_filter}, but got {notification.type}"

    @given(
        user_id=user_id_strategy(),
        status_filter=st.sampled_from(
            [NotificationStatus.READ, NotificationStatus.UNREAD]
        ),
        type_filter=notification_type_strategy(),
        matching_count=st.integers(min_value=1, max_value=5),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_8_multiple_filters_use_and_logic(
        self, test_db, user_id, status_filter, type_filter, matching_count
    ):
        """
        Feature: notification-system, Property 8: Multiple filters use AND logic
        Validates: Requirements 3.3

        For any combination of status and type filters, returned notifications
        should match both filter criteria simultaneously.
        """
        # Clear any existing notifications
        from models import Notification
        from repositories.repository_config import query_cache

        test_db.query(Notification).delete()
        test_db.commit()
        query_cache.clear()

        # Arrange
        repository = NotificationRepository(test_db)

        # Create notifications that match BOTH filters
        for i in range(matching_count):
            notification_data = NotificationCreate(
                user_id=user_id,
                type=type_filter,
                priority=NotificationPriority.MEDIUM,
                title=f"Matching Notification {i}",
                message=f"Matching Message {i}",
                meta_data=None,
            )
            notification = repository.create_notification(notification_data)

            # Mark as read if filter is READ
            if status_filter == NotificationStatus.READ:
                repository.mark_as_read(notification.id, user_id)

        # Create notifications that match only status
        for i in range(matching_count):
            other_types = [t for t in NotificationType if t != type_filter]
            if other_types:
                notification_data = NotificationCreate(
                    user_id=user_id,
                    type=other_types[0],
                    priority=NotificationPriority.HIGH,
                    title=f"Status Only Notification {i}",
                    message=f"Status Only Message {i}",
                    meta_data=None,
                )
                notification = repository.create_notification(notification_data)

                # Mark as read if filter is READ
                if status_filter == NotificationStatus.READ:
                    repository.mark_as_read(notification.id, user_id)

        # Create notifications that match only type
        opposite_status = (
            NotificationStatus.READ
            if status_filter == NotificationStatus.UNREAD
            else NotificationStatus.UNREAD
        )
        for i in range(matching_count):
            notification_data = NotificationCreate(
                user_id=user_id,
                type=type_filter,
                priority=NotificationPriority.LOW,
                title=f"Type Only Notification {i}",
                message=f"Type Only Message {i}",
                meta_data=None,
            )
            notification = repository.create_notification(notification_data)

            # Mark as read if opposite status is READ
            if opposite_status == NotificationStatus.READ:
                repository.mark_as_read(notification.id, user_id)

        # Act - Filter by both status and type
        filters = NotificationFilters(status=status_filter, type=type_filter)
        filtered_notifications, total = repository.get_notifications_with_pagination(
            user_id=user_id, page=1, limit=100, filters=filters
        )

        # Assert - All returned notifications match BOTH filters
        assert (
            len(filtered_notifications) == matching_count
        ), f"Should return {matching_count} notifications matching both filters"

        for notification in filtered_notifications:
            assert (
                notification.status == status_filter
            ), f"All notifications should have status {status_filter}"
            assert (
                notification.type == type_filter
            ), f"All notifications should have type {type_filter}"


class TestPaginationProperties:
    """
    Property tests for pagination
    """

    @given(
        user_id=user_id_strategy(),
        total_notifications=st.integers(min_value=5, max_value=20),
        page=st.integers(min_value=1, max_value=5),
        limit=st.integers(min_value=1, max_value=10),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_5_pagination_respects_boundaries(
        self, test_db, user_id, total_notifications, page, limit
    ):
        """
        Feature: notification-system, Property 5: Pagination respects boundaries
        Validates: Requirements 2.3

        For any valid page and limit parameters, the number of returned notifications
        should not exceed the limit, and the offset should correctly skip (page-1) * limit
        notifications.
        """
        # Clear any existing notifications
        from models import Notification
        from repositories.repository_config import query_cache

        test_db.query(Notification).delete()
        test_db.commit()
        query_cache.clear()

        # Arrange
        repository = NotificationRepository(test_db)

        # Create notifications
        for i in range(total_notifications):
            notification_data = NotificationCreate(
                user_id=user_id,
                type=NotificationType.SYSTEM,
                priority=NotificationPriority.MEDIUM,
                title=f"Notification {i}",
                message=f"Message {i}",
                meta_data=None,
            )
            repository.create_notification(notification_data)
            time.sleep(0.001)  # Ensure different timestamps

        # Act - Get paginated results
        filters = NotificationFilters()
        notifications, total = repository.get_notifications_with_pagination(
            user_id=user_id, page=page, limit=limit, filters=filters
        )

        # Assert - Number of results does not exceed limit
        assert (
            len(notifications) <= limit
        ), f"Should return at most {limit} notifications, but got {len(notifications)}"

        # Assert - Total count is correct
        assert (
            total == total_notifications
        ), f"Total should be {total_notifications}, but got {total}"

        # Calculate expected number of results
        offset = (page - 1) * limit
        expected_count = min(limit, max(0, total_notifications - offset))

        assert (
            len(notifications) == expected_count
        ), f"Expected {expected_count} notifications for page {page} with limit {limit}, but got {len(notifications)}"


class TestCleanupProperties:
    """
    Property tests for cleanup operations
    """

    @given(
        retention_days=st.integers(min_value=1, max_value=30),
        old_read_count=st.integers(min_value=1, max_value=5),
        old_unread_count=st.integers(min_value=1, max_value=5),
        recent_read_count=st.integers(min_value=1, max_value=5),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_26_cleanup_deletes_old_read_notifications_only(
        self,
        test_db,
        retention_days,
        old_read_count,
        old_unread_count,
        recent_read_count,
    ):
        """
        Feature: notification-system, Property 26: Cleanup deletes old read notifications only
        Validates: Requirements 10.1, 10.2, 10.3, 10.4

        For any cleanup operation with retention period R days, notifications that are
        (read AND older than R days) should be deleted, while notifications that are
        (unread OR newer than R days) should be preserved.
        """
        # Clear any existing notifications
        from models import Notification
        from repositories.repository_config import query_cache

        test_db.query(Notification).delete()
        test_db.commit()
        query_cache.clear()

        # Arrange
        repository = NotificationRepository(test_db)
        user_id = "testuser01"

        # Create old read notifications (should be deleted)
        old_date = datetime.utcnow() - timedelta(days=retention_days + 1)
        old_read_ids = []
        for i in range(old_read_count):
            notification = Notification(
                user_id=user_id,
                type=NotificationType.SYSTEM,
                priority=NotificationPriority.MEDIUM,
                title=f"Old Read {i}",
                message=f"Old Read Message {i}",
                status=NotificationStatus.READ,
                created_at=old_date,
                read_at=old_date,
            )
            test_db.add(notification)
            test_db.commit()
            test_db.refresh(notification)
            old_read_ids.append(notification.id)

        # Create old unread notifications (should be preserved)
        old_unread_ids = []
        for i in range(old_unread_count):
            notification = Notification(
                user_id=user_id,
                type=NotificationType.PERMISSION,
                priority=NotificationPriority.HIGH,
                title=f"Old Unread {i}",
                message=f"Old Unread Message {i}",
                status=NotificationStatus.UNREAD,
                created_at=old_date,
            )
            test_db.add(notification)
            test_db.commit()
            test_db.refresh(notification)
            old_unread_ids.append(notification.id)

        # Create recent read notifications (should be preserved)
        recent_date = datetime.utcnow() - timedelta(days=retention_days - 1)
        recent_read_ids = []
        for i in range(recent_read_count):
            notification = Notification(
                user_id=user_id,
                type=NotificationType.EXPORT,
                priority=NotificationPriority.MEDIUM,
                title=f"Recent Read {i}",
                message=f"Recent Read Message {i}",
                status=NotificationStatus.READ,
                created_at=recent_date,
                read_at=recent_date,
            )
            test_db.add(notification)
            test_db.commit()
            test_db.refresh(notification)
            recent_read_ids.append(notification.id)

        # Act - Run cleanup
        deleted_count = repository.delete_old_notifications(retention_days)

        # Assert - Correct number deleted
        assert (
            deleted_count == old_read_count
        ), f"Should delete {old_read_count} old read notifications, but deleted {deleted_count}"

        # Assert - Old read notifications are deleted
        for notification_id in old_read_ids:
            notification = (
                test_db.query(Notification)
                .filter(Notification.id == notification_id)
                .first()
            )
            assert (
                notification is None
            ), f"Old read notification {notification_id} should be deleted"

        # Assert - Old unread notifications are preserved
        for notification_id in old_unread_ids:
            notification = (
                test_db.query(Notification)
                .filter(Notification.id == notification_id)
                .first()
            )
            assert (
                notification is not None
            ), f"Old unread notification {notification_id} should be preserved"

        # Assert - Recent read notifications are preserved
        for notification_id in recent_read_ids:
            notification = (
                test_db.query(Notification)
                .filter(Notification.id == notification_id)
                .first()
            )
            assert (
                notification is not None
            ), f"Recent read notification {notification_id} should be preserved"


class TestEventTriggeredNotificationProperties:
    """
    Property tests for event-triggered notifications
    """

    @given(
        user_id=user_id_strategy(),
        action=st.sampled_from(["granted", "revoked"]),
        supplier_name=st.text(min_size=1, max_size=50),
        admin_username=st.text(min_size=1, max_size=50),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_17_permission_change_triggers_notification(
        self, test_db, user_id, action, supplier_name, admin_username
    ):
        """
        Feature: notification-system, Property 17: Permission change triggers notification
        Validates: Requirements 8.1

        For any user whose permissions are modified, a notification of type "permission"
        should be created for that user.
        """
        from services.notification_service import NotificationService

        # Arrange
        service = NotificationService(test_db)

        # Act - Trigger permission change notification
        notification = service.notify_permission_change(
            user_id=user_id,
            action=action,
            supplier_name=supplier_name,
            admin_username=admin_username,
        )

        # Assert - Notification was created
        assert notification is not None, "Notification should be created"
        assert notification.id is not None, "Notification should have an ID"

        # Assert - Notification has correct type
        assert (
            notification.type == NotificationType.PERMISSION
        ), "Notification type should be PERMISSION"

        # Assert - Notification belongs to correct user
        assert (
            notification.user_id == user_id
        ), "Notification should belong to the correct user"

        # Assert - Notification has high priority
        assert (
            notification.priority == NotificationPriority.HIGH
        ), "Permission change notifications should have HIGH priority"

        # Assert - Notification contains relevant information
        assert supplier_name in notification.message, "Message should mention supplier"
        assert action in notification.message, "Message should mention action"

    @given(
        user_id=user_id_strategy(),
        export_id=st.text(min_size=1, max_size=50),
        export_type=st.sampled_from(["hotel", "mapping", "location"]),
        file_path=st.text(min_size=1, max_size=100),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_18_export_completion_triggers_notification(
        self, test_db, user_id, export_id, export_type, file_path
    ):
        """
        Feature: notification-system, Property 18: Export completion triggers notification
        Validates: Requirements 8.2

        For any completed export job, a notification of type "export" should be
        created for the user who initiated the export.
        """
        from services.notification_service import NotificationService

        # Arrange
        service = NotificationService(test_db)

        # Act - Trigger export completion notification
        notification = service.notify_export_complete(
            user_id=user_id,
            export_id=export_id,
            export_type=export_type,
            file_path=file_path,
        )

        # Assert - Notification was created
        assert notification is not None, "Notification should be created"
        assert notification.id is not None, "Notification should have an ID"

        # Assert - Notification has correct type
        assert (
            notification.type == NotificationType.EXPORT
        ), "Notification type should be EXPORT"

        # Assert - Notification belongs to correct user
        assert (
            notification.user_id == user_id
        ), "Notification should belong to the correct user"

        # Assert - Notification has medium priority
        assert (
            notification.priority == NotificationPriority.MEDIUM
        ), "Export completion notifications should have MEDIUM priority"

        # Assert - Notification contains relevant information
        assert export_type in notification.message, "Message should mention export type"

    @given(
        user_id=user_id_strategy(),
        transaction_type=st.sampled_from(["received", "deducted", "allocated"]),
        points=st.integers(min_value=1, max_value=10000),
        from_user=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_19_point_transaction_triggers_notification(
        self, test_db, user_id, transaction_type, points, from_user
    ):
        """
        Feature: notification-system, Property 19: Point transaction triggers notification
        Validates: Requirements 8.3

        For any significant point balance change for a user, a notification of type
        "point" should be created for that user.
        """
        from services.notification_service import NotificationService

        # Arrange
        service = NotificationService(test_db)

        # Act - Trigger point transaction notification
        notification = service.notify_point_transaction(
            user_id=user_id,
            transaction_type=transaction_type,
            points=points,
            from_user=from_user,
        )

        # Assert - Notification was created
        assert notification is not None, "Notification should be created"
        assert notification.id is not None, "Notification should have an ID"

        # Assert - Notification has correct type
        assert (
            notification.type == NotificationType.POINT
        ), "Notification type should be POINT"

        # Assert - Notification belongs to correct user
        assert (
            notification.user_id == user_id
        ), "Notification should belong to the correct user"

        # Assert - Priority is appropriate for point amount
        if points >= 1000:
            assert (
                notification.priority == NotificationPriority.HIGH
            ), "Large point transactions should have HIGH priority"
        else:
            assert (
                notification.priority == NotificationPriority.MEDIUM
            ), "Small point transactions should have MEDIUM priority"

        # Assert - Notification contains relevant information
        assert str(points) in notification.message, "Message should mention points"

    @given(
        scheduled_at=st.datetimes(
            min_value=datetime(2024, 1, 1), max_value=datetime(2025, 12, 31)
        ),
        duration=st.text(min_size=1, max_size=50),
        description=st.text(min_size=1, max_size=200),
        active_user_count=st.integers(min_value=1, max_value=10),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_20_system_maintenance_broadcasts_to_all_active_users(
        self, test_db, scheduled_at, duration, description, active_user_count
    ):
        """
        Feature: notification-system, Property 20: System maintenance broadcasts to all active users
        Validates: Requirements 8.4

        For any system maintenance event, notifications should be created for all
        users with is_active=True.
        """
        from services.notification_service import NotificationService
        from models import User

        # Clear existing users and notifications
        test_db.query(User).delete()
        from models import Notification

        test_db.query(Notification).delete()
        test_db.commit()

        # Arrange - Create active users
        active_user_ids = []
        for i in range(active_user_count):
            user = User(
                id=f"user{i:06d}",
                username=f"activeuser{i}",
                email=f"active{i}@test.com",
                hashed_password="hashed",
                is_active=True,
            )
            test_db.add(user)
            active_user_ids.append(user.id)

        # Create some inactive users (should not receive notifications)
        for i in range(2):
            user = User(
                id=f"inact{i:05d}",
                username=f"inactiveuser{i}",
                email=f"inactive{i}@test.com",
                hashed_password="hashed",
                is_active=False,
            )
            test_db.add(user)

        test_db.commit()

        # Act - Trigger system maintenance notification
        service = NotificationService(test_db)
        notifications = service.notify_system_maintenance(
            scheduled_at=scheduled_at, duration=duration, description=description
        )

        # Assert - Correct number of notifications created
        assert (
            len(notifications) == active_user_count
        ), f"Should create {active_user_count} notifications for active users"

        # Assert - All notifications have correct type and priority
        for notification in notifications:
            assert (
                notification.type == NotificationType.MAINTENANCE
            ), "Notification type should be MAINTENANCE"
            assert (
                notification.priority == NotificationPriority.HIGH
            ), "Maintenance notifications should have HIGH priority"
            assert (
                notification.user_id in active_user_ids
            ), "Notification should belong to an active user"

        # Assert - All active users received a notification
        for user_id in active_user_ids:
            user_notifications = [n for n in notifications if n.user_id == user_id]
            assert (
                len(user_notifications) == 1
            ), f"User {user_id} should receive exactly one notification"

    @given(
        user_id=user_id_strategy(),
        event_type=st.sampled_from(["created", "expiring", "expired"]),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_21_api_key_events_trigger_notifications(
        self, test_db, user_id, event_type
    ):
        """
        Feature: notification-system, Property 21: API key events trigger notifications
        Validates: Requirements 8.5

        For any API key creation or expiration event for a user, a notification of
        type "api_key" should be created for that user.
        """
        from services.notification_service import NotificationService

        # Arrange
        service = NotificationService(test_db)
        expires_at = (
            datetime.utcnow() + timedelta(days=30) if event_type != "expired" else None
        )

        # Act - Trigger API key event notification
        notification = service.notify_api_key_event(
            user_id=user_id, event_type=event_type, expires_at=expires_at
        )

        # Assert - Notification was created
        assert notification is not None, "Notification should be created"
        assert notification.id is not None, "Notification should have an ID"

        # Assert - Notification has correct type
        assert (
            notification.type == NotificationType.API_KEY
        ), "Notification type should be API_KEY"

        # Assert - Notification belongs to correct user
        assert (
            notification.user_id == user_id
        ), "Notification should belong to the correct user"

        # Assert - Priority is appropriate for event type
        if event_type == "expired":
            assert (
                notification.priority == NotificationPriority.CRITICAL
            ), "Expired API key should have CRITICAL priority"
        elif event_type == "expiring":
            assert (
                notification.priority == NotificationPriority.HIGH
            ), "Expiring API key should have HIGH priority"
        else:
            assert (
                notification.priority == NotificationPriority.MEDIUM
            ), "Created API key should have MEDIUM priority"


class TestPriorityHandlingProperties:
    """
    Property tests for priority handling
    """

    @given(
        user_id=user_id_strategy(),
        priority=notification_priority_strategy(),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_22_priority_values_are_from_valid_set(
        self, test_db, user_id, priority
    ):
        """
        Feature: notification-system, Property 22: Priority values are from valid set
        Validates: Requirements 9.1

        For any created notification, the priority field should be one of:
        low, medium, high, or critical.
        """
        from repositories.notification_repository import NotificationRepository

        # Arrange
        repository = NotificationRepository(test_db)
        notification_data = NotificationCreate(
            user_id=user_id,
            type=NotificationType.SYSTEM,
            priority=priority,
            title="Test Notification",
            message="Test Message",
            meta_data=None,
        )

        # Act
        notification = repository.create_notification(notification_data)

        # Assert - Priority is from valid set
        valid_priorities = [
            NotificationPriority.LOW,
            NotificationPriority.MEDIUM,
            NotificationPriority.HIGH,
            NotificationPriority.CRITICAL,
        ]
        assert (
            notification.priority in valid_priorities
        ), f"Priority should be one of {[p.value for p in valid_priorities]}"

    @given(
        user_id=user_id_strategy(),
        priority=notification_priority_strategy(),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_23_priority_included_in_responses(
        self, test_db, user_id, priority
    ):
        """
        Feature: notification-system, Property 23: Priority included in responses
        Validates: Requirements 9.2

        For any notification returned by the API, the response should include a
        priority field with a valid priority value.
        """
        from repositories.notification_repository import NotificationRepository
        from schemas import NotificationResponse

        # Arrange
        repository = NotificationRepository(test_db)
        notification_data = NotificationCreate(
            user_id=user_id,
            type=NotificationType.SYSTEM,
            priority=priority,
            title="Test Notification",
            message="Test Message",
            meta_data=None,
        )

        # Act - Create notification and convert to response
        notification = repository.create_notification(notification_data)
        response = NotificationResponse.model_validate(notification)

        # Assert - Priority is included in response
        assert hasattr(response, "priority"), "Response should have priority field"
        assert response.priority is not None, "Priority should not be None"
        assert (
            response.priority == priority
        ), f"Priority should be {priority}, but got {response.priority}"

    @given(
        user_id=user_id_strategy(),
        notification_count=st.integers(min_value=4, max_value=8),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_24_priority_based_sorting_order(
        self, test_db, user_id, notification_count
    ):
        """
        Feature: notification-system, Property 24: Priority-based sorting order
        Validates: Requirements 9.3

        For any list of notifications sorted by priority, critical notifications
        should appear before high, high before medium, and medium before low.
        """
        from repositories.notification_repository import NotificationRepository

        # Clear any existing notifications
        from models import Notification
        from repositories.repository_config import query_cache

        test_db.query(Notification).delete()
        test_db.commit()
        query_cache.clear()

        # Arrange
        repository = NotificationRepository(test_db)

        # Create notifications with all priority levels
        priorities = [
            NotificationPriority.LOW,
            NotificationPriority.MEDIUM,
            NotificationPriority.HIGH,
            NotificationPriority.CRITICAL,
        ]

        # Create multiple notifications for each priority
        for priority in priorities:
            for i in range(notification_count // 4 + 1):
                notification_data = NotificationCreate(
                    user_id=user_id,
                    type=NotificationType.SYSTEM,
                    priority=priority,
                    title=f"{priority.value} Notification {i}",
                    message=f"{priority.value} Message {i}",
                    meta_data=None,
                )
                repository.create_notification(notification_data)

        # Act - Get notifications sorted by priority
        filters = NotificationFilters()
        notifications, total = repository.get_notifications_with_pagination(
            user_id=user_id,
            page=1,
            limit=100,
            filters=filters,
            sort_by="priority",
            sort_order="desc",
        )

        # Assert - Notifications are sorted by priority (critical first)
        priority_order = {
            NotificationPriority.CRITICAL: 4,
            NotificationPriority.HIGH: 3,
            NotificationPriority.MEDIUM: 2,
            NotificationPriority.LOW: 1,
        }

        for i in range(len(notifications) - 1):
            current_priority_value = priority_order[notifications[i].priority]
            next_priority_value = priority_order[notifications[i + 1].priority]

            assert (
                current_priority_value >= next_priority_value
            ), f"Notification {i} with priority {notifications[i].priority.value} should come before notification {i+1} with priority {notifications[i+1].priority.value}"

    @given(
        user_id=user_id_strategy(),
    )
    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_25_critical_priority_preservation(self, test_db, user_id):
        """
        Feature: notification-system, Property 25: Critical priority preservation
        Validates: Requirements 9.4

        For any notification created with critical priority, retrieving that
        notification should show priority as "critical".
        """
        from repositories.notification_repository import NotificationRepository

        # Arrange
        repository = NotificationRepository(test_db)
        notification_data = NotificationCreate(
            user_id=user_id,
            type=NotificationType.SYSTEM,
            priority=NotificationPriority.CRITICAL,
            title="Critical Notification",
            message="Critical Message",
            meta_data=None,
        )

        # Act - Create notification with critical priority
        notification = repository.create_notification(notification_data)
        notification_id = notification.id

        # Retrieve the notification
        retrieved_notification = repository.get_notification_by_id(
            notification_id, user_id
        )

        # Assert - Priority is preserved as CRITICAL
        assert (
            retrieved_notification.priority == NotificationPriority.CRITICAL
        ), "Priority should be preserved as CRITICAL"
