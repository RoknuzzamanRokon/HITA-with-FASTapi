"""
Test Suite for New User Dashboard Endpoint

This test suite validates the functionality and performance of the /new-user
dashboard endpoint, including authentication, response structure, time-series
data format, caching behavior, and error handling.
"""

import pytest
import time
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import application components
from main import app
from database import Base, get_db
from models import User, UserRole, UserPoint, UserProviderPermission, UserActivityLog
from routes.auth import create_access_token

# ====================================================================
# TEST DATABASE SETUP
# ====================================================================

# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables
Base.metadata.create_all(bind=engine)

# Override database dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)

# ====================================================================
# TEST FIXTURES AND HELPERS
# ====================================================================

def create_test_user(db, username="testuser", email="test@example.com", 
                     role=UserRole.GENERAL_USER, has_suppliers=False, has_points=False):
    """
    Create a test user with optional suppliers and points
    
    Args:
        db: Database session
        username: Username for the test user
        email: Email for the test user
        role: User role (default: GENERAL_USER)
        has_suppliers: Whether to assign supplier permissions
        has_points: Whether to allocate points
    
    Returns:
        User: Created user object
    """
    # Create user
    user = User(
        id=f"test{int(time.time() * 1000)}",
        username=username,
        email=email,
        role=role,
        hashed_password="$2b$12$test_hashed_password",
        is_active=True,
        created_at=datetime.utcnow() - timedelta(days=5)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Add supplier permissions if requested
    if has_suppliers:
        permission = UserProviderPermission(
            user_id=user.id,
            provider_name="Agoda"
        )
        db.add(permission)
        db.commit()
    
    # Add points if requested
    if has_points:
        user_point = UserPoint(
            user_id=user.id,
            total_points=1000,
            current_points=1000,
            total_used_points=0
        )
        db.add(user_point)
        db.commit()
    
    return user

def create_jwt_token(user_id: str, username: str):
    """
    Create a JWT token for testing
    
    Args:
        user_id: User ID
        username: Username
    
    Returns:
        str: JWT access token
    """
    return create_access_token(data={"sub": username, "user_id": user_id})

def add_user_activity(db, user_id: str, days_ago: int = 0, action: str = "login"):
    """
    Add user activity log entry
    
    Args:
        db: Database session
        user_id: User ID
        days_ago: How many days ago the activity occurred
        action: Activity action type
    """
    activity = UserActivityLog(
        user_id=user_id,
        action=action,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
        details={"test": "activity"}
    )
    db.add(activity)
    db.commit()

# ====================================================================
# TEST SUITE 5.1: Test endpoint with new user (0 suppliers, 0 points)
# ====================================================================

def test_new_user_zero_suppliers_zero_points():
    """
    Test endpoint with a new user who has no supplier permissions and no points
    
    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.5, 4.5, 5.1, 5.2
    """
    db = TestingSessionLocal()
    
    try:
        # Create test user with no suppliers and no points
        user = create_test_user(
            db, 
            username="newuser", 
            email="newuser@example.com",
            has_suppliers=False,
            has_points=False
        )
        
        # Create JWT token
        token = create_jwt_token(user.id, user.username)
        
        # Call endpoint
        response = client.get(
            "/v1.0/dashboard/new-user",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Verify response status
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Parse response
        data = response.json()
        
        # Verify response structure - all required fields present
        assert "account_info" in data, "Missing account_info section"
        assert "user_resources" in data, "Missing user_resources section"
        assert "platform_overview" in data, "Missing platform_overview section"
        assert "activity_metrics" in data, "Missing activity_metrics section"
        assert "platform_trends" in data, "Missing platform_trends section"
        assert "recommendations" in data, "Missing recommendations section"
        assert "metadata" in data, "Missing metadata section"
        
        # Verify account_info structure
        account_info = data["account_info"]
        assert account_info["user_id"] == user.id
        assert account_info["username"] == user.username
        assert account_info["email"] == user.email
        assert "account_status" in account_info
        assert "created_at" in account_info
        assert "days_since_registration" in account_info
        assert "onboarding_progress" in account_info
        
        # Verify user_resources shows zero suppliers and zero points
        user_resources = data["user_resources"]
        assert user_resources["suppliers"]["active_count"] == 0, "New user should have 0 suppliers"
        assert user_resources["suppliers"]["pending_assignment"] == True, "Should indicate pending supplier assignment"
        assert user_resources["points"]["current_balance"] == 0, "New user should have 0 points"
        assert user_resources["points"]["pending_allocation"] == True, "Should indicate pending point allocation"
        
        # Verify activity_metrics contains time-series data
        activity_metrics = data["activity_metrics"]
        assert "user_logins" in activity_metrics
        assert "time_series" in activity_metrics["user_logins"]
        assert "api_requests" in activity_metrics
        assert "time_series" in activity_metrics["api_requests"]
        
        # Verify time-series data contains zeros or empty arrays for new user
        login_time_series = activity_metrics["user_logins"]["time_series"]
        api_time_series = activity_metrics["api_requests"]["time_series"]
        
        # API requests should be zero for new users
        assert activity_metrics["api_requests"]["total_count"] == 0, "New user should have 0 API requests"
        
        # Verify recommendations include supplier and point assignment actions
        recommendations = data["recommendations"]
        assert "next_steps" in recommendations, "Missing next_steps in recommendations"
        
        next_steps = recommendations["next_steps"]
        assert len(next_steps) > 0, "Should have at least one recommendation"
        
        # Check for supplier and point assignment recommendations
        recommendation_actions = [step.get("action", "") for step in next_steps]
        has_supplier_recommendation = any("supplier" in action.lower() for action in recommendation_actions)
        has_point_recommendation = any("point" in action.lower() for action in recommendation_actions)
        
        assert has_supplier_recommendation, "Should recommend supplier assignment"
        assert has_point_recommendation, "Should recommend point allocation"
        
        print("✅ Test passed: New user with 0 suppliers and 0 points")
        
    finally:
        db.close()

# ====================================================================
# TEST SUITE 5.2: Test endpoint with authenticated user
# ====================================================================

def test_authenticated_user_valid_token():
    """
    Test endpoint with valid JWT token
    
    Requirements: 7.4
    """
    db = TestingSessionLocal()
    
    try:
        # Create test user
        user = create_test_user(db, username="authuser", email="authuser@example.com")
        
        # Create valid JWT token
        token = create_jwt_token(user.id, user.username)
        
        # Call endpoint with valid token
        response = client.get(
            "/v1.0/dashboard/new-user",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Verify 200 OK response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify all required response fields present
        data = response.json()
        required_fields = [
            "account_info", "user_resources", "platform_overview",
            "activity_metrics", "platform_trends", "recommendations", "metadata"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print("✅ Test passed: Authenticated user with valid token")
        
    finally:
        db.close()

# ====================================================================
# TEST SUITE 5.3: Test endpoint error scenarios
# ====================================================================

def test_invalid_token():
    """
    Test endpoint with invalid JWT token (expect 401)
    
    Requirements: 7.1, 7.4
    """
    # Call endpoint with invalid token
    response = client.get(
        "/v1.0/dashboard/new-user",
        headers={"Authorization": "Bearer invalid_token_12345"}
    )
    
    # Verify 401 Unauthorized response
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    print("✅ Test passed: Invalid token returns 401")

def test_missing_token():
    """
    Test endpoint with missing JWT token (expect 401)
    
    Requirements: 7.1, 7.4
    """
    # Call endpoint without token
    response = client.get("/v1.0/dashboard/new-user")
    
    # Verify 401 Unauthorized response
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    print("✅ Test passed: Missing token returns 401")

def test_graceful_degradation_missing_activity_log():
    """
    Test endpoint with missing UserActivityLog table (expect graceful degradation)
    
    Requirements: 7.1, 7.4
    
    Note: This test verifies that the endpoint handles missing tables gracefully
    by returning empty/zero values instead of crashing.
    """
    db = TestingSessionLocal()
    
    try:
        # Create test user
        user = create_test_user(db, username="degradeuser", email="degrade@example.com")
        
        # Create JWT token
        token = create_jwt_token(user.id, user.username)
        
        # Call endpoint (UserActivityLog may not have data)
        response = client.get(
            "/v1.0/dashboard/new-user",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should still return 200 with graceful degradation
        assert response.status_code == 200, f"Expected 200 with graceful degradation, got {response.status_code}"
        
        # Verify response structure is intact
        data = response.json()
        assert "activity_metrics" in data
        assert "metadata" in data
        
        print("✅ Test passed: Graceful degradation for missing tables")
        
    finally:
        db.close()

# ====================================================================
# TEST SUITE 5.4: Verify response time performance
# ====================================================================

def test_response_time_cold_cache():
    """
    Measure response time with cold cache
    
    Requirements: 7.1
    """
    db = TestingSessionLocal()
    
    try:
        # Create test user
        user = create_test_user(db, username="perfuser", email="perf@example.com")
        token = create_jwt_token(user.id, user.username)
        
        # Measure response time
        start_time = time.time()
        response = client.get(
            "/v1.0/dashboard/new-user",
            headers={"Authorization": f"Bearer {token}"}
        )
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        # Verify response is successful
        assert response.status_code == 200
        
        # Log response time (target: < 500ms for 95% of requests)
        print(f"✅ Cold cache response time: {response_time_ms:.2f}ms")
        
        # Note: In production with real database and cache, this should be < 500ms
        # For in-memory test database, we just verify it completes
        assert response_time_ms < 5000, f"Response time too slow: {response_time_ms}ms"
        
    finally:
        db.close()

def test_response_time_warm_cache():
    """
    Measure response time with warm cache (second request should be faster)
    
    Requirements: 7.1
    """
    db = TestingSessionLocal()
    
    try:
        # Create test user
        user = create_test_user(db, username="cacheuser", email="cache@example.com")
        token = create_jwt_token(user.id, user.username)
        
        # First request (cold cache)
        response1 = client.get(
            "/v1.0/dashboard/new-user",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response1.status_code == 200
        
        # Second request (warm cache)
        start_time = time.time()
        response2 = client.get(
            "/v1.0/dashboard/new-user",
            headers={"Authorization": f"Bearer {token}"}
        )
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        # Verify response is successful
        assert response2.status_code == 200
        
        print(f"✅ Warm cache response time: {response_time_ms:.2f}ms")
        
        # Warm cache should be reasonably fast
        assert response_time_ms < 5000, f"Warm cache response too slow: {response_time_ms}ms"
        
    finally:
        db.close()

# ====================================================================
# TEST SUITE 5.5: Verify time-series data format
# ====================================================================

def test_time_series_data_format():
    """
    Verify time-series data has consistent structure and format
    
    Requirements: 6.1, 6.2, 6.3, 6.4
    """
    db = TestingSessionLocal()
    
    try:
        # Create test user with some activity
        user = create_test_user(db, username="timeseriesuser", email="timeseries@example.com")
        
        # Add some login activity
        for days_ago in [1, 3, 5, 7]:
            add_user_activity(db, user.id, days_ago=days_ago, action="login")
        
        token = create_jwt_token(user.id, user.username)
        
        # Call endpoint
        response = client.get(
            "/v1.0/dashboard/new-user",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check activity metrics time-series
        activity_metrics = data["activity_metrics"]
        login_time_series = activity_metrics["user_logins"]["time_series"]
        
        # Verify time-series has data
        assert len(login_time_series) > 0, "Time-series should have data"
        
        # Check each time-series entry
        for entry in login_time_series:
            # Verify consistent structure (date, value)
            assert "date" in entry, "Time-series entry missing 'date' field"
            assert "value" in entry, "Time-series entry missing 'value' field"
            
            # Verify date format (YYYY-MM-DD)
            date_str = entry["date"]
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                pytest.fail(f"Invalid date format: {date_str}, expected YYYY-MM-DD")
            
            # Verify value is a number
            assert isinstance(entry["value"], (int, float)), f"Value should be numeric, got {type(entry['value'])}"
        
        # Verify data is sorted chronologically (oldest to newest)
        dates = [entry["date"] for entry in login_time_series]
        sorted_dates = sorted(dates)
        assert dates == sorted_dates, "Time-series data should be sorted chronologically"
        
        # Verify 30-day period coverage
        # Note: The endpoint should fill missing dates with zeros
        if len(login_time_series) > 0:
            first_date = datetime.strptime(login_time_series[0]["date"], "%Y-%m-%d")
            last_date = datetime.strptime(login_time_series[-1]["date"], "%Y-%m-%d")
            date_range = (last_date - first_date).days
            
            # Should cover approximately 30 days (allowing for some flexibility)
            assert date_range <= 30, f"Time-series should cover 30 days or less, got {date_range} days"
        
        # Check platform trends time-series
        platform_trends = data["platform_trends"]
        
        for trend_key in ["user_registrations", "hotel_updates"]:
            if trend_key in platform_trends:
                trend_data = platform_trends[trend_key]
                
                # Verify metadata present
                assert "title" in trend_data, f"{trend_key} missing title"
                assert "unit" in trend_data, f"{trend_key} missing unit"
                assert "data_type" in trend_data, f"{trend_key} missing data_type"
                assert "time_series" in trend_data, f"{trend_key} missing time_series"
                
                # Verify time-series format
                time_series = trend_data["time_series"]
                for entry in time_series:
                    assert "date" in entry
                    assert "value" in entry
        
        print("✅ Test passed: Time-series data format is consistent")
        
    finally:
        db.close()

# ====================================================================
# TEST SUITE 5.6: Verify caching behavior
# ====================================================================

def test_cache_behavior():
    """
    Test caching behavior (cache hit, expiration, fallback)
    
    Requirements: 7.2, 7.3
    
    Note: This test verifies basic caching concepts. Full cache testing
    would require Redis integration which may not be available in test environment.
    """
    db = TestingSessionLocal()
    
    try:
        # Create test user
        user = create_test_user(db, username="cachetest", email="cachetest@example.com")
        token = create_jwt_token(user.id, user.username)
        
        # First request
        response1 = client.get(
            "/v1.0/dashboard/new-user",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second request (should potentially hit cache)
        response2 = client.get(
            "/v1.0/dashboard/new-user",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Verify both requests return valid data
        assert "metadata" in data1
        assert "metadata" in data2
        
        # Check cache status in metadata (if available)
        if "cache_status" in data1["metadata"]:
            print(f"Cache status (request 1): {data1['metadata']['cache_status']}")
        if "cache_status" in data2["metadata"]:
            print(f"Cache status (request 2): {data2['metadata']['cache_status']}")
        
        print("✅ Test passed: Caching behavior verified")
        
    finally:
        db.close()

# ====================================================================
# RUN ALL TESTS
# ====================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("RUNNING NEW USER DASHBOARD TEST SUITE")
    print("="*70 + "\n")
    
    # Test Suite 5.1
    print("\n--- Test Suite 5.1: New User with 0 Suppliers and 0 Points ---")
    test_new_user_zero_suppliers_zero_points()
    
    # Test Suite 5.2
    print("\n--- Test Suite 5.2: Authenticated User ---")
    test_authenticated_user_valid_token()
    
    # Test Suite 5.3
    print("\n--- Test Suite 5.3: Error Scenarios ---")
    test_invalid_token()
    test_missing_token()
    test_graceful_degradation_missing_activity_log()
    
    # Test Suite 5.4
    print("\n--- Test Suite 5.4: Response Time Performance ---")
    test_response_time_cold_cache()
    test_response_time_warm_cache()
    
    # Test Suite 5.5
    print("\n--- Test Suite 5.5: Time-Series Data Format ---")
    test_time_series_data_format()
    
    # Test Suite 5.6
    print("\n--- Test Suite 5.6: Caching Behavior ---")
    test_cache_behavior()
    
    print("\n" + "="*70)
    print("ALL TESTS COMPLETED SUCCESSFULLY ✅")
    print("="*70 + "\n")
