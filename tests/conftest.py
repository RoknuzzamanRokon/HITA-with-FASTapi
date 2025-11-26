"""
Pytest configuration and fixtures for notification tests
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from database import get_db


@pytest.fixture(scope="function")
def test_db():
    """Create a test database for each test function"""
    # Use in-memory SQLite database for tests
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def notification_repository(test_db):
    """Create a NotificationRepository instance with test database"""
    from repositories.notification_repository import NotificationRepository

    return NotificationRepository(test_db)


@pytest.fixture(scope="function")
def test_users(test_db):
    """Create test users for integration tests"""
    from models import User, UserRole
    from datetime import datetime

    # Create super user
    super_user = User(
        id="super00001",
        username="super_admin",
        email="super@test.com",
        hashed_password="hashed_password",
        role=UserRole.SUPER_USER,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    # Create admin user
    admin_user = User(
        id="admin00001",
        username="admin_user",
        email="admin@test.com",
        hashed_password="hashed_password",
        role=UserRole.ADMIN_USER,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    # Create general user
    general_user = User(
        id="general001",
        username="general_user",
        email="general@test.com",
        hashed_password="hashed_password",
        role=UserRole.GENERAL_USER,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    test_db.add(super_user)
    test_db.add(admin_user)
    test_db.add(general_user)
    test_db.commit()

    return {"super": super_user, "admin": admin_user, "general": general_user}
