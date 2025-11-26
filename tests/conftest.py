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
