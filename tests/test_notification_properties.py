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
