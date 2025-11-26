"""
Integration tests for notification API endpoints

These tests verify the complete API behavior including authentication,
authorization, error handling, pagination, and filtering.
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import status
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock

from fastapi import FastAPI
from database import get_db
from models import (
    Base,
    User,
    UserRole,
    Notification,
    NotificationType,
    NotificationPriority,
    NotificationStatus,
)
from routes.auth import get_current_active_user
from routes.notifications import router as notifications_router


# Test database setup
@pytest.fixture(scope="function")
def test_db_engine():
    """Create a test database engine"""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db_session(test_db_engine):
    """Create a test database session"""
    from repositories.repository_config import query_cache

    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_db_engine
    )
    session = TestingSessionLocal()
    try:
        # Clear all tables before each test
        session.query(Notification).delete()
        session.query(User).delete()
        session.commit()

        # Clear query cache to avoid stale results
        query_cache.clear()

        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def test_app():
    """Create a test FastAPI app with notification routes"""
    app = FastAPI()
    app.include_router(notifications_router)
    return app


@pytest.fixture(scope="function")
def test_client(test_app, test_db_session):
    """Create a test client with database override"""

    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    test_app.dependency_overrides[get_db] = override_get_db

    yield TestClient(test_app)

    test_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(test_db_session):
    """Create a test user"""
    user = User(
        id="testuser01",
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password",
        role=UserRole.GENERAL_USER,
        is_active=True,
    )
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def another_user(test_db_session):
    """Create another test user for isolation tests"""
    user = User(
        id="otheruser1",
        username="otheruser",
        email="other@example.com",
        hashed_password="hashed_password",
        role=UserRole.GENERAL_USER,
        is_active=True,
    )
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def authenticated_client(test_app, test_client, test_user):
    """Create an authenticated test client"""

    def override_get_current_active_user():
        return test_user

    test_app.dependency_overrides[get_current_active_user] = (
        override_get_current_active_user
    )

    yield test_client

    # Clean up the override
    if get_current_active_user in test_app.dependency_overrides:
        del test_app.dependency_overrides[get_current_active_user]


def create_notification(db_session, user_id, **kwargs):
    """Helper function to create a notification"""
    notification = Notification(
        user_id=user_id,
        type=kwargs.get("type", NotificationType.SYSTEM),
        priority=kwargs.get("priority", NotificationPriority.MEDIUM),
        title=kwargs.get("title", "Test Notification"),
        message=kwargs.get("message", "Test message"),
        status=kwargs.get("status", NotificationStatus.UNREAD),
        meta_data=kwargs.get("meta_data"),
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)
    return notification


class TestAuthenticationRequirements:
    """Test that all endpoints require authentication"""

    def test_get_notifications_requires_auth(self, test_client):
        """GET /notifications should return 401 without authentication"""
        response = test_client.get("/v1.0/notifications/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_unread_count_requires_auth(self, test_client):
        """GET /notifications/unread-count should return 401 without authentication"""
        response = test_client.get("/v1.0/notifications/unread-count")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_mark_notification_read_requires_auth(self, test_client):
        """PUT /notifications/{id}/read should return 401 without authentication"""
        response = test_client.put("/v1.0/notifications/1/read")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_mark_all_read_requires_auth(self, test_client):
        """PUT /notifications/mark-all-read should return 401 without authentication"""
        response = test_client.put("/v1.0/notifications/mark-all-read")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_notification_requires_auth(self, test_client):
        """DELETE /notifications/{id} should return 401 without authentication"""
        response = test_client.delete("/v1.0/notifications/1")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAuthorizationUserIsolation:
    """Test that users can only access their own notifications"""

    def test_user_can_only_see_own_notifications(
        self, authenticated_client, test_user, another_user, test_db_session
    ):
        """Users should only see their own notifications"""
        # Create notifications for test_user
        create_notification(test_db_session, test_user.id, title="User 1 Notification")

        # Create notifications for another_user
        create_notification(
            test_db_session, another_user.id, title="User 2 Notification"
        )

        # Get notifications as test_user
        response = authenticated_client.get("/v1.0/notifications/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should only see own notification
        assert data["total"] == 1
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["user_id"] == test_user.id
        assert data["notifications"][0]["title"] == "User 1 Notification"

    def test_cannot_mark_another_users_notification_as_read(
        self, authenticated_client, test_user, another_user, test_db_session
    ):
        """Users cannot mark another user's notification as read"""
        # Create notification for another_user
        notification = create_notification(
            test_db_session, another_user.id, title="Other User Notification"
        )

        # Try to mark it as read as test_user
        response = authenticated_client.put(
            f"/v1.0/notifications/{notification.id}/read"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "permission" in response.json()["detail"].lower()

    def test_cannot_delete_another_users_notification(
        self, authenticated_client, test_user, another_user, test_db_session
    ):
        """Users cannot delete another user's notification"""
        # Create notification for another_user
        notification = create_notification(
            test_db_session, another_user.id, title="Other User Notification"
        )

        # Try to delete it as test_user
        response = authenticated_client.delete(f"/v1.0/notifications/{notification.id}")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "permission" in response.json()["detail"].lower()

    def test_unread_count_only_includes_own_notifications(
        self, authenticated_client, test_user, another_user, test_db_session
    ):
        """Unread count should only include user's own notifications"""
        # Create unread notifications for test_user
        create_notification(
            test_db_session, test_user.id, status=NotificationStatus.UNREAD
        )
        create_notification(
            test_db_session, test_user.id, status=NotificationStatus.UNREAD
        )

        # Create unread notifications for another_user
        create_notification(
            test_db_session, another_user.id, status=NotificationStatus.UNREAD
        )
        create_notification(
            test_db_session, another_user.id, status=NotificationStatus.UNREAD
        )
        create_notification(
            test_db_session, another_user.id, status=NotificationStatus.UNREAD
        )

        # Get unread count as test_user
        response = authenticated_client.get("/v1.0/notifications/unread-count")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should only count own notifications
        assert data["unread_count"] == 2


class TestErrorResponses:
    """Test error response handling"""

    def test_404_notification_not_found_on_mark_read(
        self, authenticated_client, test_user
    ):
        """Should return 404 when marking non-existent notification as read"""
        response = authenticated_client.put("/v1.0/notifications/99999/read")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_404_notification_not_found_on_delete(
        self, authenticated_client, test_user
    ):
        """Should return 404 when deleting non-existent notification"""
        response = authenticated_client.delete("/v1.0/notifications/99999")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_422_invalid_status_filter(self, authenticated_client):
        """Should return 422 for invalid status filter value"""
        response = authenticated_client.get(
            "/v1.0/notifications/?status=invalid_status"
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_422_invalid_type_filter(self, authenticated_client):
        """Should return 422 for invalid type filter value"""
        response = authenticated_client.get("/v1.0/notifications/?type=invalid_type")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_422_invalid_priority_filter(self, authenticated_client):
        """Should return 422 for invalid priority filter value"""
        response = authenticated_client.get(
            "/v1.0/notifications/?priority=invalid_priority"
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_422_invalid_page_parameter(self, authenticated_client):
        """Should return 422 for invalid page parameter (< 1)"""
        response = authenticated_client.get("/v1.0/notifications/?page=0")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_422_invalid_limit_parameter(self, authenticated_client):
        """Should return 422 for invalid limit parameter (> 100)"""
        response = authenticated_client.get("/v1.0/notifications/?limit=101")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_422_invalid_sort_by_parameter(self, authenticated_client):
        """Should return 422 for invalid sort_by parameter"""
        response = authenticated_client.get(
            "/v1.0/notifications/?sort_by=invalid_field"
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_422_invalid_sort_order_parameter(self, authenticated_client):
        """Should return 422 for invalid sort_order parameter"""
        response = authenticated_client.get(
            "/v1.0/notifications/?sort_order=invalid_order"
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestPaginationEdgeCases:
    """Test pagination edge cases"""

    def test_empty_result_set(self, authenticated_client, test_user):
        """Should handle empty result set correctly"""
        response = authenticated_client.get("/v1.0/notifications/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["notifications"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["total_pages"] == 0

    def test_first_page(self, authenticated_client, test_user, test_db_session):
        """Should correctly return first page"""
        # Create 5 notifications
        for i in range(5):
            create_notification(
                test_db_session, test_user.id, title=f"Notification {i}"
            )

        response = authenticated_client.get("/v1.0/notifications/?page=1&limit=3")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["notifications"]) == 3
        assert data["page"] == 1
        assert data["limit"] == 3
        assert data["total"] == 5
        assert data["total_pages"] == 2

    def test_last_page_partial(self, authenticated_client, test_user, test_db_session):
        """Should correctly return last page with partial results"""
        # Create 5 notifications
        for i in range(5):
            create_notification(
                test_db_session, test_user.id, title=f"Notification {i}"
            )

        response = authenticated_client.get("/v1.0/notifications/?page=2&limit=3")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["notifications"]) == 2  # Only 2 remaining
        assert data["page"] == 2
        assert data["limit"] == 3
        assert data["total"] == 5
        assert data["total_pages"] == 2

    def test_page_beyond_total_pages(
        self, authenticated_client, test_user, test_db_session
    ):
        """Should return empty results for page beyond total pages"""
        # Create 3 notifications
        for i in range(3):
            create_notification(
                test_db_session, test_user.id, title=f"Notification {i}"
            )

        response = authenticated_client.get("/v1.0/notifications/?page=10&limit=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["notifications"] == []
        assert data["page"] == 10
        assert data["total"] == 3

    def test_default_pagination_values(
        self, authenticated_client, test_user, test_db_session
    ):
        """Should use default pagination values when not specified"""
        # Create 30 notifications
        for i in range(30):
            create_notification(
                test_db_session, test_user.id, title=f"Notification {i}"
            )

        response = authenticated_client.get("/v1.0/notifications/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["page"] == 1
        assert data["limit"] == 25  # Default limit
        assert len(data["notifications"]) == 25
        assert data["total"] == 30

    def test_max_limit_enforced(self, authenticated_client, test_user, test_db_session):
        """Should enforce maximum limit of 100"""
        # Create 150 notifications
        for i in range(150):
            create_notification(
                test_db_session, test_user.id, title=f"Notification {i}"
            )

        # Try to request more than 100
        response = authenticated_client.get("/v1.0/notifications/?limit=100")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["notifications"]) == 100
        assert data["limit"] == 100


class TestFilterCombinations:
    """Test various filter combinations"""

    def test_status_filter_unread(
        self, authenticated_client, test_user, test_db_session
    ):
        """Should filter by unread status"""
        # Create mix of read and unread
        create_notification(
            test_db_session,
            test_user.id,
            status=NotificationStatus.UNREAD,
            title="Unread 1",
        )
        create_notification(
            test_db_session,
            test_user.id,
            status=NotificationStatus.UNREAD,
            title="Unread 2",
        )
        create_notification(
            test_db_session,
            test_user.id,
            status=NotificationStatus.READ,
            title="Read 1",
        )

        response = authenticated_client.get("/v1.0/notifications/?status=unread")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] == 2
        assert all(n["status"] == "unread" for n in data["notifications"])

    def test_status_filter_read(self, authenticated_client, test_user, test_db_session):
        """Should filter by read status"""
        # Create mix of read and unread
        create_notification(
            test_db_session,
            test_user.id,
            status=NotificationStatus.UNREAD,
            title="Unread 1",
        )
        create_notification(
            test_db_session,
            test_user.id,
            status=NotificationStatus.READ,
            title="Read 1",
        )
        create_notification(
            test_db_session,
            test_user.id,
            status=NotificationStatus.READ,
            title="Read 2",
        )

        response = authenticated_client.get("/v1.0/notifications/?status=read")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] == 2
        assert all(n["status"] == "read" for n in data["notifications"])

    def test_type_filter(self, authenticated_client, test_user, test_db_session):
        """Should filter by notification type"""
        # Create different types
        create_notification(test_db_session, test_user.id, type=NotificationType.SYSTEM)
        create_notification(
            test_db_session, test_user.id, type=NotificationType.PERMISSION
        )
        create_notification(
            test_db_session, test_user.id, type=NotificationType.PERMISSION
        )
        create_notification(test_db_session, test_user.id, type=NotificationType.EXPORT)

        response = authenticated_client.get("/v1.0/notifications/?type=permission")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] == 2
        assert all(n["type"] == "permission" for n in data["notifications"])

    def test_priority_filter(self, authenticated_client, test_user, test_db_session):
        """Should filter by priority"""
        # Create different priorities
        create_notification(
            test_db_session, test_user.id, priority=NotificationPriority.LOW
        )
        create_notification(
            test_db_session, test_user.id, priority=NotificationPriority.HIGH
        )
        create_notification(
            test_db_session, test_user.id, priority=NotificationPriority.HIGH
        )
        create_notification(
            test_db_session, test_user.id, priority=NotificationPriority.CRITICAL
        )

        response = authenticated_client.get("/v1.0/notifications/?priority=high")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] == 2
        assert all(n["priority"] == "high" for n in data["notifications"])

    def test_combined_status_and_type_filter(
        self, authenticated_client, test_user, test_db_session
    ):
        """Should apply multiple filters with AND logic"""
        # Create various combinations
        create_notification(
            test_db_session,
            test_user.id,
            status=NotificationStatus.UNREAD,
            type=NotificationType.SYSTEM,
        )
        create_notification(
            test_db_session,
            test_user.id,
            status=NotificationStatus.UNREAD,
            type=NotificationType.PERMISSION,
        )
        create_notification(
            test_db_session,
            test_user.id,
            status=NotificationStatus.READ,
            type=NotificationType.PERMISSION,
        )

        response = authenticated_client.get(
            "/v1.0/notifications/?status=unread&type=permission"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] == 1
        assert data["notifications"][0]["status"] == "unread"
        assert data["notifications"][0]["type"] == "permission"

    def test_combined_all_filters(
        self, authenticated_client, test_user, test_db_session
    ):
        """Should apply all filters together"""
        # Create various combinations
        create_notification(
            test_db_session,
            test_user.id,
            status=NotificationStatus.UNREAD,
            type=NotificationType.PERMISSION,
            priority=NotificationPriority.HIGH,
        )
        create_notification(
            test_db_session,
            test_user.id,
            status=NotificationStatus.UNREAD,
            type=NotificationType.PERMISSION,
            priority=NotificationPriority.LOW,
        )
        create_notification(
            test_db_session,
            test_user.id,
            status=NotificationStatus.READ,
            type=NotificationType.PERMISSION,
            priority=NotificationPriority.HIGH,
        )

        response = authenticated_client.get(
            "/v1.0/notifications/?status=unread&type=permission&priority=high"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] == 1
        assert data["notifications"][0]["status"] == "unread"
        assert data["notifications"][0]["type"] == "permission"
        assert data["notifications"][0]["priority"] == "high"

    def test_no_results_with_filters(
        self, authenticated_client, test_user, test_db_session
    ):
        """Should return empty results when filters match nothing"""
        # Create some notifications
        create_notification(
            test_db_session,
            test_user.id,
            status=NotificationStatus.UNREAD,
            type=NotificationType.SYSTEM,
        )

        # Filter for combination that doesn't exist
        response = authenticated_client.get(
            "/v1.0/notifications/?status=read&type=permission"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] == 0
        assert data["notifications"] == []


class TestCompleteWorkflows:
    """Test complete notification workflows"""

    def test_create_mark_read_workflow(
        self, authenticated_client, test_user, test_db_session
    ):
        """Test complete workflow: create -> retrieve -> mark as read -> verify"""
        # Create notification
        notification = create_notification(
            test_db_session,
            test_user.id,
            title="Test Workflow",
            status=NotificationStatus.UNREAD,
        )

        # Retrieve and verify unread
        response = authenticated_client.get("/v1.0/notifications/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["unread_count"] == 1
        assert data["notifications"][0]["status"] == "unread"

        # Mark as read
        response = authenticated_client.put(
            f"/v1.0/notifications/{notification.id}/read"
        )
        assert response.status_code == status.HTTP_200_OK
        read_data = response.json()
        assert read_data["status"] == "read"
        assert read_data["read_at"] is not None

        # Verify read status persisted
        response = authenticated_client.get("/v1.0/notifications/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["unread_count"] == 0
        assert data["notifications"][0]["status"] == "read"

    def test_mark_all_read_workflow(
        self, authenticated_client, test_user, test_db_session
    ):
        """Test mark all as read workflow"""
        # Create multiple unread notifications
        for i in range(5):
            create_notification(
                test_db_session,
                test_user.id,
                title=f"Notification {i}",
                status=NotificationStatus.UNREAD,
            )

        # Verify unread count
        response = authenticated_client.get("/v1.0/notifications/unread-count")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["unread_count"] == 5

        # Mark all as read
        response = authenticated_client.put("/v1.0/notifications/mark-all-read")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["updated_count"] == 5

        # Verify all are now read
        response = authenticated_client.get("/v1.0/notifications/unread-count")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["unread_count"] == 0

    def test_delete_notification_workflow(
        self, authenticated_client, test_user, test_db_session
    ):
        """Test delete notification workflow"""
        # Create notification
        notification = create_notification(
            test_db_session, test_user.id, title="To Be Deleted"
        )

        # Verify it exists
        response = authenticated_client.get("/v1.0/notifications/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 1

        # Delete it
        response = authenticated_client.delete(f"/v1.0/notifications/{notification.id}")
        assert response.status_code == status.HTTP_200_OK
        assert "deleted successfully" in response.json()["message"]

        # Verify it's gone
        response = authenticated_client.get("/v1.0/notifications/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 0
