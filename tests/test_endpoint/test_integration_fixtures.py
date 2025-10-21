"""
Additional fixtures and utilities for end-to-end integration testing.

This module provides specialized fixtures for testing complete workflows,
frontend-backend integration, and system resilience scenarios.
"""

import pytest
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, get_db, engine
from models import User, UserRole, UserPoint, PointTransaction, UserActivityLog, UserSession, UserProviderPermission


@pytest.fixture(scope="session")
def integration_test_db():
    """Create a separate test database for integration tests"""
    # Use a separate test database file
    test_db_path = "test_integration.db"
    test_engine = create_engine(f"sqlite:///{test_db_path}", echo=False)
    
    # Create all tables
    Base.metadata.create_all(bind=test_engine)
    
    # Create session factory
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    yield test_engine, TestSessionLocal
    
    # Cleanup
    try:
        os.remove(test_db_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def integration_db_session(integration_test_db):
    """Create a database session for integration tests"""
    engine, SessionLocal = integration_test_db
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_user_dataset(integration_db_session):
    """Create a comprehensive dataset of users for integration testing"""
    users_data = []
    
    # Create different types of users
    user_types = [
        {"role": UserRole.SUPER_USER, "count": 2, "prefix": "super"},
        {"role": UserRole.ADMIN_USER, "count": 5, "prefix": "admin"},
        {"role": UserRole.GENERAL_USER, "count": 20, "prefix": "general"}
    ]
    
    created_users = []
    
    for user_type in user_types:
        for i in range(user_type["count"]):
            timestamp = int(time.time()) + i
            user = User(
                id=f"{user_type['prefix']}_test_{timestamp}_{i}",
                username=f"{user_type['prefix']}_user_{timestamp}_{i}",
                email=f"{user_type['prefix']}_test_{timestamp}_{i}@example.com",
                hashed_password="$2b$12$test_hashed_password",
                role=user_type["role"],
                is_active=i % 4 != 0,  # Make some inactive
                created_by="integration_test",
                created_at=datetime.utcnow() - timedelta(days=i),
                updated_at=datetime.utcnow() - timedelta(days=i//2)
            )
            
            integration_db_session.add(user)
            created_users.append(user)
    
    integration_db_session.commit()
    
    # Refresh all users to get their IDs
    for user in created_users:
        integration_db_session.refresh(user)
    
    yield created_users
    
    # Cleanup
    for user in created_users:
        try:
            integration_db_session.delete(user)
        except:
            pass
    
    try:
        integration_db_session.commit()
    except:
        integration_db_session.rollback()


@pytest.fixture
def sample_user_with_complete_data(integration_db_session):
    """Create a user with complete related data (points, transactions, sessions, permissions)"""
    timestamp = int(time.time())
    
    # Create user
    user = User(
        id=f"complete_user_{timestamp}",
        username=f"complete_user_{timestamp}",
        email=f"complete_test_{timestamp}@example.com",
        hashed_password="$2b$12$test_hashed_password",
        role=UserRole.GENERAL_USER,
        is_active=True,
        created_by="integration_test",
        created_at=datetime.utcnow() - timedelta(days=30),
        updated_at=datetime.utcnow() - timedelta(days=1)
    )
    
    integration_db_session.add(user)
    integration_db_session.commit()
    integration_db_session.refresh(user)
    
    # Add user points
    user_points = UserPoint(
        user_id=user.id,
        user_email=user.email,
        total_points=5000,
        current_points=2500,
        total_used_points=2500
    )
    integration_db_session.add(user_points)
    
    # Add point transactions
    transactions = []
    for i in range(10):
        # Some as giver, some as receiver
        if i % 2 == 0:
            transaction = PointTransaction(
                giver_id=user.id,
                giver_email=user.email,
                receiver_id=f"receiver_{i}",
                receiver_email=f"receiver_{i}@example.com",
                points=100 + i * 10,
                transaction_type="transfer",
                created_at=datetime.utcnow() - timedelta(days=i)
            )
        else:
            transaction = PointTransaction(
                giver_id=f"giver_{i}",
                giver_email=f"giver_{i}@example.com",
                receiver_id=user.id,
                receiver_email=user.email,
                points=50 + i * 5,
                transaction_type="transfer",
                created_at=datetime.utcnow() - timedelta(days=i)
            )
        
        transactions.append(transaction)
        integration_db_session.add(transaction)
    
    # Add user sessions
    sessions = []
    for i in range(5):
        session = UserSession(
            id=f"session_{user.id}_{i}",
            user_id=user.id,
            created_at=datetime.utcnow() - timedelta(hours=i*2),
            last_activity=datetime.utcnow() - timedelta(hours=i),
            expires_at=datetime.utcnow() + timedelta(hours=24-i),
            is_active=i < 2  # First 2 sessions are active
        )
        sessions.append(session)
        integration_db_session.add(session)
    
    # Add provider permissions
    permissions = []
    providers = ["provider_a", "provider_b", "provider_c"]
    for provider in providers:
        permission = UserProviderPermission(
            user_id=user.id,
            provider_name=provider
        )
        permissions.append(permission)
        integration_db_session.add(permission)
    
    # Add activity logs
    activities = []
    activity_types = ["login", "logout", "point_transfer", "profile_update", "permission_change"]
    for i, activity_type in enumerate(activity_types):
        activity = UserActivityLog(
            user_id=user.id,
            action=activity_type,
            details={"test": True, "integration": True, "sequence": i},
            ip_address=f"192.168.1.{100+i}",
            user_agent=f"TestAgent/{i}.0",
            created_at=datetime.utcnow() - timedelta(hours=i)
        )
        activities.append(activity)
        integration_db_session.add(activity)
    
    integration_db_session.commit()
    
    # Refresh to get all relationships
    integration_db_session.refresh(user)
    
    yield {
        "user": user,
        "points": user_points,
        "transactions": transactions,
        "sessions": sessions,
        "permissions": permissions,
        "activities": activities
    }
    
    # Cleanup
    cleanup_objects = [user_points] + transactions + sessions + permissions + activities + [user]
    for obj in cleanup_objects:
        try:
            integration_db_session.delete(obj)
        except:
            pass
    
    try:
        integration_db_session.commit()
    except:
        integration_db_session.rollback()


@pytest.fixture
def mock_frontend_requests():
    """Mock typical frontend request patterns"""
    return {
        "dashboard_load": [
            {"endpoint": "/v1.0/user/list", "params": {"page": 1, "limit": 10}},
            {"endpoint": "/v1.0/user/stats", "params": {}},
        ],
        "user_search": [
            {"endpoint": "/v1.0/user/list", "params": {"search": "admin", "page": 1, "limit": 25}},
            {"endpoint": "/v1.0/user/list", "params": {"search": "@example.com", "page": 1, "limit": 25}},
        ],
        "user_filtering": [
            {"endpoint": "/v1.0/user/list", "params": {"role": "general_user", "page": 1, "limit": 25}},
            {"endpoint": "/v1.0/user/list", "params": {"is_active": True, "page": 1, "limit": 25}},
            {"endpoint": "/v1.0/user/list", "params": {"role": "admin_user", "is_active": False, "page": 1, "limit": 25}},
        ],
        "pagination_scenarios": [
            {"endpoint": "/v1.0/user/list", "params": {"page": 1, "limit": 10}},
            {"endpoint": "/v1.0/user/list", "params": {"page": 2, "limit": 10}},
            {"endpoint": "/v1.0/user/list", "params": {"page": 1, "limit": 50}},
            {"endpoint": "/v1.0/user/list", "params": {"page": 1, "limit": 100}},
        ],
        "sorting_scenarios": [
            {"endpoint": "/v1.0/user/list", "params": {"sort_by": "username", "sort_order": "asc", "page": 1, "limit": 25}},
            {"endpoint": "/v1.0/user/list", "params": {"sort_by": "created_at", "sort_order": "desc", "page": 1, "limit": 25}},
            {"endpoint": "/v1.0/user/list", "params": {"sort_by": "email", "sort_order": "asc", "page": 1, "limit": 25}},
        ]
    }


@pytest.fixture
def performance_test_data():
    """Data for performance testing scenarios"""
    return {
        "concurrent_users": 20,
        "requests_per_user": 10,
        "max_response_time": 5.0,  # seconds
        "min_success_rate": 0.95,  # 95%
        "large_page_sizes": [100, 500, 1000],
        "stress_test_duration": 30,  # seconds
    }


@pytest.fixture
def security_test_payloads():
    """Security test payloads for resilience testing"""
    return {
        "sql_injection": [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin'; DELETE FROM users WHERE '1'='1",
            "' UNION SELECT * FROM users --",
            "1' OR '1'='1' --",
        ],
        "xss_payloads": [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "';alert('xss');//",
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        ],
        "command_injection": [
            "; ls -la",
            "| whoami",
            "&& cat /etc/passwd",
            "`id`",
            "$(whoami)",
        ],
        "buffer_overflow": [
            "A" * 1000,
            "A" * 10000,
            "A" * 100000,
        ]
    }


class IntegrationTestHelper:
    """Helper class for integration testing utilities"""
    
    @staticmethod
    def create_test_user_data(prefix: str = "test", role: str = "general_user") -> Dict[str, Any]:
        """Create test user data with unique values"""
        timestamp = int(time.time())
        return {
            "username": f"{prefix}_user_{timestamp}",
            "email": f"{prefix}_test_{timestamp}@example.com",
            "password": "TestPassword123!",
            "role": role
        }
    
    @staticmethod
    def validate_user_response_structure(response_data: Dict[str, Any], response_type: str = "list") -> bool:
        """Validate user response structure matches expected format"""
        if response_type == "list":
            if isinstance(response_data, list):
                return True
            elif isinstance(response_data, dict) and "users" in response_data:
                return isinstance(response_data["users"], list)
        
        elif response_type == "single":
            required_fields = ["id", "username", "email", "role"]
            return all(field in response_data for field in required_fields)
        
        elif response_type == "stats":
            expected_stats = ["total_users", "active_users"]
            return any(stat in response_data for stat in expected_stats)
        
        return False
    
    @staticmethod
    def measure_response_time(func, *args, **kwargs) -> tuple:
        """Measure function execution time"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        return result, end_time - start_time
    
    @staticmethod
    def generate_load_test_requests(base_endpoint: str, num_requests: int = 100) -> List[Dict[str, Any]]:
        """Generate a list of requests for load testing"""
        requests = []
        
        for i in range(num_requests):
            # Vary the parameters to simulate real usage
            page = (i % 10) + 1
            limit = [10, 25, 50][i % 3]
            
            request = {
                "endpoint": base_endpoint,
                "params": {"page": page, "limit": limit},
                "request_id": i
            }
            
            # Add search parameter occasionally
            if i % 5 == 0:
                request["params"]["search"] = f"test_{i}"
            
            # Add role filter occasionally
            if i % 7 == 0:
                roles = ["super_user", "admin_user", "general_user"]
                request["params"]["role"] = roles[i % 3]
            
            requests.append(request)
        
        return requests
    
    @staticmethod
    def analyze_response_patterns(responses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze response patterns for performance insights"""
        if not responses:
            return {"error": "No responses to analyze"}
        
        status_codes = [r.get("status_code", 0) for r in responses]
        response_times = [r.get("response_time", 0) for r in responses if r.get("response_time")]
        
        analysis = {
            "total_requests": len(responses),
            "success_count": len([r for r in responses if r.get("success", False)]),
            "error_count": len([r for r in responses if not r.get("success", True)]),
            "status_code_distribution": {},
            "response_time_stats": {}
        }
        
        # Status code distribution
        for code in set(status_codes):
            analysis["status_code_distribution"][code] = status_codes.count(code)
        
        # Response time statistics
        if response_times:
            analysis["response_time_stats"] = {
                "min": min(response_times),
                "max": max(response_times),
                "avg": sum(response_times) / len(response_times),
                "count": len(response_times)
            }
        
        # Success rate
        analysis["success_rate"] = analysis["success_count"] / analysis["total_requests"]
        
        return analysis


@pytest.fixture
def integration_test_helper():
    """Provide the integration test helper class"""
    return IntegrationTestHelper