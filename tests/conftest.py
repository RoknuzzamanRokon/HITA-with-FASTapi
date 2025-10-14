"""
Test configuration and fixtures for user management tests.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base
from models import User, UserRole, UserPoint, PointTransaction, UserActivityLog, UserSession, UserProviderPermission


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session."""
    # Use in-memory SQLite database for testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "id": "user123456",
        "username": "testuser",
        "email": "test@example.com",
        "hashed_password": "hashed_password_123",
        "role": UserRole.GENERAL_USER,
        "is_active": True,
        "created_by": "admin",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }


@pytest.fixture
def sample_user(db_session, sample_user_data):
    """Create a sample user in the database."""
    user = User(**sample_user_data)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_user_with_points(db_session, sample_user):
    """Create a sample user with points."""
    user_points = UserPoint(
        user_id=sample_user.id,
        user_email=sample_user.email,
        total_points=1000,
        current_points=500,
        total_used_points=500
    )
    db_session.add(user_points)
    db_session.commit()
    db_session.refresh(user_points)
    return sample_user


@pytest.fixture
def sample_user_with_transactions(db_session, sample_user_with_points):
    """Create a sample user with point transactions."""
    # Create a recent transaction (within 7 days)
    recent_transaction = PointTransaction(
        giver_id=sample_user_with_points.id,
        giver_email=sample_user_with_points.email,
        receiver_id="receiver123",
        receiver_email="receiver@example.com",
        points=100,
        transaction_type="transfer",
        created_at=datetime.utcnow() - timedelta(days=2)
    )
    
    # Create an old transaction (more than 7 days ago)
    old_transaction = PointTransaction(
        giver_id=sample_user_with_points.id,
        giver_email=sample_user_with_points.email,
        receiver_id="receiver456",
        receiver_email="receiver2@example.com",
        points=50,
        transaction_type="transfer",
        created_at=datetime.utcnow() - timedelta(days=10)
    )
    
    db_session.add_all([recent_transaction, old_transaction])
    db_session.commit()
    return sample_user_with_points


@pytest.fixture
def sample_user_with_permissions(db_session, sample_user):
    """Create a sample user with provider permissions."""
    permission1 = UserProviderPermission(
        user_id=sample_user.id,
        provider_name="provider1"
    )
    permission2 = UserProviderPermission(
        user_id=sample_user.id,
        provider_name="provider2"
    )
    
    db_session.add_all([permission1, permission2])
    db_session.commit()
    return sample_user


@pytest.fixture
def sample_user_with_sessions(db_session, sample_user):
    """Create a sample user with sessions."""
    active_session = UserSession(
        id="session123",
        user_id=sample_user.id,
        created_at=datetime.utcnow() - timedelta(hours=2),
        last_activity=datetime.utcnow() - timedelta(minutes=30),
        expires_at=datetime.utcnow() + timedelta(hours=2),
        is_active=True
    )
    
    inactive_session = UserSession(
        id="session456",
        user_id=sample_user.id,
        created_at=datetime.utcnow() - timedelta(days=1),
        last_activity=datetime.utcnow() - timedelta(hours=12),
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_active=False
    )
    
    db_session.add_all([active_session, inactive_session])
    db_session.commit()
    return sample_user