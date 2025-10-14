"""
Unit tests for SQLAlchemy models and their computed properties.

This module tests the User model's hybrid properties and computed fields
to ensure they work correctly with various data scenarios.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from models import (
    User, UserRole, UserPoint, PointTransaction, UserActivityLog, 
    UserSession, UserProviderPermission
)


class TestUserModel:
    """Test cases for the User model and its properties."""
    
    def test_user_creation_basic(self, db_session, sample_user_data):
        """Test basic user creation with required fields."""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        assert user.id == sample_user_data["id"]
        assert user.username == sample_user_data["username"]
        assert user.email == sample_user_data["email"]
        assert user.role == UserRole.GENERAL_USER
        assert user.is_active is True
        assert user.created_by == "admin"
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)
    
    def test_user_creation_with_defaults(self, db_session):
        """Test user creation with default values."""
        user = User(
            id="user789012",
            username="defaultuser",
            email="default@example.com",
            hashed_password="hashed_pass"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        assert user.role == UserRole.GENERAL_USER  # Default role
        assert user.is_active is True  # Default active status
        assert user.created_by is None  # Default None
        assert user.api_key is None  # Default None
    
    def test_user_role_enum_values(self, db_session):
        """Test that all user role enum values work correctly."""
        roles_to_test = [
            (UserRole.SUPER_USER, "super_user"),
            (UserRole.ADMIN_USER, "admin_user"),
            (UserRole.GENERAL_USER, "general_user")
        ]
        
        for role_enum, role_value in roles_to_test:
            user = User(
                id=f"user{role_value}",
                username=f"user_{role_value}",
                email=f"{role_value}@example.com",
                hashed_password="hashed_pass",
                role=role_enum
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            
            assert user.role == role_enum
            # In SQLAlchemy, the role is stored as string, so we compare with the enum value
            assert user.role == role_value or user.role.value == role_value
    
    def test_current_point_balance_with_points(self, db_session, sample_user_with_points):
        """Test current_point_balance property with user points."""
        # Refresh the user to ensure relationships are loaded
        db_session.refresh(sample_user_with_points)
        
        assert sample_user_with_points.current_point_balance == 500
    
    def test_current_point_balance_without_points(self, db_session, sample_user):
        """Test current_point_balance property without user points."""
        assert sample_user.current_point_balance == 0
    
    def test_total_point_balance_with_points(self, db_session, sample_user_with_points):
        """Test total_point_balance property with user points."""
        db_session.refresh(sample_user_with_points)
        
        assert sample_user_with_points.total_point_balance == 1000
    
    def test_total_point_balance_without_points(self, db_session, sample_user):
        """Test total_point_balance property without user points."""
        assert sample_user.total_point_balance == 0
    
    def test_activity_status_with_recent_transactions(self, db_session, sample_user_with_transactions):
        """Test activity_status property with recent transactions."""
        db_session.refresh(sample_user_with_transactions)
        
        # The user should be "Active" because they have transactions within 7 days
        assert sample_user_with_transactions.activity_status == "Active"
    
    def test_activity_status_without_recent_transactions(self, db_session, sample_user):
        """Test activity_status property without recent transactions."""
        # Create only old transactions (more than 7 days ago)
        old_transaction = PointTransaction(
            giver_id=sample_user.id,
            giver_email=sample_user.email,
            receiver_id="receiver789",
            receiver_email="old@example.com",
            points=25,
            transaction_type="transfer",
            created_at=datetime.utcnow() - timedelta(days=15)
        )
        db_session.add(old_transaction)
        db_session.commit()
        db_session.refresh(sample_user)
        
        assert sample_user.activity_status == "Inactive"
    
    def test_activity_status_no_transactions(self, db_session, sample_user):
        """Test activity_status property with no transactions."""
        assert sample_user.activity_status == "Inactive"
    
    def test_active_supplier_list_with_permissions(self, db_session, sample_user_with_permissions):
        """Test active_supplier_list property with provider permissions."""
        db_session.refresh(sample_user_with_permissions)
        
        supplier_list = sample_user_with_permissions.active_supplier_list
        assert len(supplier_list) == 2
        assert "provider1" in supplier_list
        assert "provider2" in supplier_list
    
    def test_active_supplier_list_without_permissions(self, db_session, sample_user):
        """Test active_supplier_list property without provider permissions."""
        supplier_list = sample_user.active_supplier_list
        assert len(supplier_list) == 0
        assert supplier_list == []
    
    def test_total_requests_with_transactions(self, db_session, sample_user_with_transactions):
        """Test total_requests property with sent and received transactions."""
        # Add a received transaction
        received_transaction = PointTransaction(
            giver_id="giver123",
            giver_email="giver@example.com",
            receiver_id=sample_user_with_transactions.id,
            receiver_email=sample_user_with_transactions.email,
            points=200,
            transaction_type="transfer",
            created_at=datetime.utcnow() - timedelta(days=1)
        )
        db_session.add(received_transaction)
        db_session.commit()
        db_session.refresh(sample_user_with_transactions)
        
        # Should have 2 sent transactions + 1 received transaction = 3 total
        assert sample_user_with_transactions.total_requests == 3
    
    def test_total_requests_without_transactions(self, db_session, sample_user):
        """Test total_requests property without transactions."""
        assert sample_user.total_requests == 0
    
    def test_paid_status_with_current_points(self, db_session, sample_user_with_points):
        """Test paid_status property when user has current points."""
        db_session.refresh(sample_user_with_points)
        
        # User has 500 current points, so should be "Paid"
        assert sample_user_with_points.paid_status == "Paid"
    
    def test_paid_status_used_points(self, db_session, sample_user):
        """Test paid_status property when user has used all points."""
        # Create user points with 0 current but some total points
        user_points = UserPoint(
            user_id=sample_user.id,
            user_email=sample_user.email,
            total_points=1000,
            current_points=0,
            total_used_points=1000
        )
        db_session.add(user_points)
        db_session.commit()
        db_session.refresh(sample_user)
        
        assert sample_user.paid_status == "Used"
    
    def test_paid_status_unpaid(self, db_session, sample_user):
        """Test paid_status property when user has no points."""
        assert sample_user.paid_status == "Unpaid"
    
    def test_last_login_with_sessions(self, db_session, sample_user_with_sessions):
        """Test last_login property with user sessions."""
        db_session.refresh(sample_user_with_sessions)
        
        last_login = sample_user_with_sessions.last_login
        assert last_login is not None
        assert isinstance(last_login, datetime)
        
        # Should return the most recent session's last_activity
        # The active session has more recent activity than the inactive one
        expected_time = datetime.utcnow() - timedelta(minutes=30)
        time_diff = abs((last_login - expected_time).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance
    
    def test_last_login_without_sessions(self, db_session, sample_user):
        """Test last_login property without user sessions."""
        assert sample_user.last_login is None
    
    def test_user_relationships_loading(self, db_session, sample_user_with_transactions, sample_user_with_permissions, sample_user_with_sessions):
        """Test that all user relationships load correctly."""
        # Create a comprehensive user with all relationships
        comprehensive_user = sample_user_with_transactions
        
        # Add permissions
        permission = UserProviderPermission(
            user_id=comprehensive_user.id,
            provider_name="comprehensive_provider"
        )
        db_session.add(permission)
        
        # Add session
        session = UserSession(
            id="comp_session",
            user_id=comprehensive_user.id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
            is_active=True
        )
        db_session.add(session)
        
        # Add activity log
        activity_log = UserActivityLog(
            user_id=comprehensive_user.id,
            action="test_action",
            details={"test": "data"},
            created_at=datetime.utcnow()
        )
        db_session.add(activity_log)
        
        db_session.commit()
        db_session.refresh(comprehensive_user)
        
        # Test all relationships are accessible
        assert len(comprehensive_user.sent_transactions) >= 2
        assert len(comprehensive_user.received_transactions) >= 0
        assert len(comprehensive_user.user_points) >= 1
        assert len(comprehensive_user.provider_permissions) >= 1
        assert len(comprehensive_user.sessions) >= 1
        assert len(comprehensive_user.activity_logs) >= 1


class TestUserModelEdgeCases:
    """Test edge cases and error conditions for the User model."""
    
    def test_user_with_multiple_point_records(self, db_session, sample_user):
        """Test user behavior with UserPoint record (normal case since user_id is primary key)."""
        # Create a UserPoint record for the user
        user_points = UserPoint(
            user_id=sample_user.id,
            user_email=sample_user.email,
            total_points=1000,
            current_points=500,
            total_used_points=500
        )
        
        db_session.add(user_points)
        db_session.commit()
        db_session.refresh(sample_user)
        
        # Should use the UserPoint record
        assert sample_user.current_point_balance == 500
        assert sample_user.total_point_balance == 1000
        
        # Test updating the same record
        user_points.current_points = 300
        user_points.total_used_points = 700
        db_session.commit()
        db_session.refresh(sample_user)
        
        # Should reflect the updated values
        assert sample_user.current_point_balance == 300
        assert sample_user.total_point_balance == 1000
    
    def test_user_with_expired_sessions(self, db_session, sample_user):
        """Test last_login with expired sessions."""
        expired_session = UserSession(
            id="expired_session",
            user_id=sample_user.id,
            created_at=datetime.utcnow() - timedelta(days=2),
            last_activity=datetime.utcnow() - timedelta(days=1),
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired
            is_active=False
        )
        
        db_session.add(expired_session)
        db_session.commit()
        db_session.refresh(sample_user)
        
        # Should still return the last activity time even if session is expired
        last_login = sample_user.last_login
        assert last_login is not None
        expected_time = datetime.utcnow() - timedelta(days=1)
        time_diff = abs((last_login - expected_time).total_seconds())
        assert time_diff < 3600  # Within 1 hour tolerance
    
    def test_user_activity_status_boundary_conditions(self, db_session, sample_user):
        """Test activity status at the 7-day boundary."""
        # Transaction exactly 7 days ago
        boundary_transaction = PointTransaction(
            giver_id=sample_user.id,
            giver_email=sample_user.email,
            receiver_id="boundary_receiver",
            receiver_email="boundary@example.com",
            points=100,
            transaction_type="transfer",
            created_at=datetime.utcnow() - timedelta(days=7, seconds=1)  # Just over 7 days
        )
        
        db_session.add(boundary_transaction)
        db_session.commit()
        db_session.refresh(sample_user)
        
        # Should be "Inactive" because transaction is more than 7 days old
        assert sample_user.activity_status == "Inactive"
        
        # Now add a transaction just under 7 days
        recent_transaction = PointTransaction(
            giver_id=sample_user.id,
            giver_email=sample_user.email,
            receiver_id="recent_receiver",
            receiver_email="recent@example.com",
            points=50,
            transaction_type="transfer",
            created_at=datetime.utcnow() - timedelta(days=6, hours=23)  # Just under 7 days
        )
        
        db_session.add(recent_transaction)
        db_session.commit()
        db_session.refresh(sample_user)
        
        # Should now be "Active"
        assert sample_user.activity_status == "Active"
    
    def test_user_with_zero_points_edge_cases(self, db_session, sample_user):
        """Test paid status with various zero-point scenarios."""
        # Case 1: UserPoint record with all zeros
        user_points = UserPoint(
            user_id=sample_user.id,
            user_email=sample_user.email,
            total_points=0,
            current_points=0,
            total_used_points=0
        )
        db_session.add(user_points)
        db_session.commit()
        db_session.refresh(sample_user)
        
        assert sample_user.paid_status == "Unpaid"
        
        # Case 2: Negative current points (shouldn't happen but test anyway)
        user_points.current_points = -100
        db_session.commit()
        db_session.refresh(sample_user)
        
        # Still should be "Unpaid" since current_points <= 0
        assert sample_user.paid_status == "Unpaid"


class TestUserModelPerformance:
    """Test performance-related aspects of User model properties."""
    
    def test_hybrid_properties_with_large_datasets(self, db_session, sample_user):
        """Test hybrid properties performance with larger datasets."""
        # Create many transactions
        transactions = []
        for i in range(50):
            transaction = PointTransaction(
                giver_id=sample_user.id,
                giver_email=sample_user.email,
                receiver_id=f"receiver{i}",
                receiver_email=f"receiver{i}@example.com",
                points=10,
                transaction_type="transfer",
                created_at=datetime.utcnow() - timedelta(days=i % 14)  # Mix of recent and old
            )
            transactions.append(transaction)
        
        db_session.add_all(transactions)
        
        # Create many provider permissions
        permissions = []
        for i in range(20):
            permission = UserProviderPermission(
                user_id=sample_user.id,
                provider_name=f"provider{i}"
            )
            permissions.append(permission)
        
        db_session.add_all(permissions)
        
        # Create many sessions
        sessions = []
        for i in range(10):
            session = UserSession(
                id=f"session{i}",
                user_id=sample_user.id,
                created_at=datetime.utcnow() - timedelta(hours=i),
                last_activity=datetime.utcnow() - timedelta(minutes=i*10),
                expires_at=datetime.utcnow() + timedelta(hours=1),
                is_active=i % 2 == 0
            )
            sessions.append(session)
        
        db_session.add_all(sessions)
        db_session.commit()
        db_session.refresh(sample_user)
        
        # Test that properties still work correctly with larger datasets
        assert sample_user.total_requests == 50  # All transactions
        assert len(sample_user.active_supplier_list) == 20  # All providers
        assert sample_user.activity_status == "Active"  # Has recent transactions
        assert sample_user.last_login is not None  # Has sessions
    
    def test_multiple_users_hybrid_properties(self, db_session):
        """Test hybrid properties work correctly across multiple users."""
        users = []
        for i in range(5):
            user = User(
                id=f"user{i:06d}",
                username=f"testuser{i}",
                email=f"test{i}@example.com",
                hashed_password=f"hashed_pass_{i}",
                role=UserRole.GENERAL_USER
            )
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        
        # Add different data for each user
        for i, user in enumerate(users):
            # Different point balances
            user_points = UserPoint(
                user_id=user.id,
                user_email=user.email,
                total_points=1000 * (i + 1),
                current_points=100 * (i + 1),
                total_used_points=900 * (i + 1)
            )
            db_session.add(user_points)
            
            # Different transaction patterns
            if i % 2 == 0:  # Even users have recent activity
                transaction = PointTransaction(
                    giver_id=user.id,
                    giver_email=user.email,
                    receiver_id="common_receiver",
                    receiver_email="common@example.com",
                    points=50,
                    transaction_type="transfer",
                    created_at=datetime.utcnow() - timedelta(days=1)
                )
                db_session.add(transaction)
        
        db_session.commit()
        
        # Refresh all users and test their properties
        for i, user in enumerate(users):
            db_session.refresh(user)
            
            # Test point balances are correct for each user
            assert user.current_point_balance == 100 * (i + 1)
            assert user.total_point_balance == 1000 * (i + 1)
            assert user.paid_status == "Paid"  # All have current points
            
            # Test activity status based on transaction pattern
            if i % 2 == 0:
                assert user.activity_status == "Active"
            else:
                assert user.activity_status == "Inactive"