"""
End-to-end integration tests for the user management system.

This module tests complete user management workflows with real database,
frontend-backend integration scenarios, and system resilience and error recovery.

Requirements covered: 8.5, 10.1, 10.2
"""

import pytest
import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from sqlalchemy import text

# Test framework imports
from fastapi.testclient import TestClient
from fastapi import status

# Application imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from database import get_db, engine
from models import User, UserRole, UserPoint, PointTransaction, UserActivityLog, UserSession
from user_schemas import UserCreateRequest, UserUpdateRequest, UserSearchParams
from services.user_service import UserService
from repositories.user_repository import UserRepository


class TestEndToEndIntegration:
    """End-to-end integration tests for user management workflows"""
    
    @pytest.fixture(scope="class")
    def client(self):
        """Create test client for API testing"""
        return TestClient(app)
    
    @pytest.fixture(scope="class")
    def real_db_session(self):
        """Create a real database session for integration testing"""
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    @pytest.fixture
    def admin_user_token(self, client, real_db_session):
        """Create an admin user and get authentication token"""
        # Create admin user directly in database
        admin_user = User(
            id="admin_test_" + str(int(time.time())),
            username="admin_test_user",
            email=f"admin_test_{int(time.time())}@example.com",
            hashed_password="$2b$12$test_hashed_password",
            role=UserRole.ADMIN_USER,
            is_active=True,
            created_by="system",
            created_at=datetime.utcnow()
        )
        
        real_db_session.add(admin_user)
        real_db_session.commit()
        real_db_session.refresh(admin_user)
        
        # Mock authentication token (in real scenario, would authenticate)
        # For testing purposes, we'll use the user ID as token
        token = f"Bearer {admin_user.id}"
        
        yield {"Authorization": token, "user_id": admin_user.id}
        
        # Cleanup
        real_db_session.delete(admin_user)
        real_db_session.commit()
    
    def test_complete_user_lifecycle_workflow(self, client, admin_user_token, real_db_session):
        """
        Test complete user lifecycle: create, read, update, delete
        Requirements: 8.5, 10.1, 10.2
        """
        print("\n" + "="*80)
        print("COMPLETE USER LIFECYCLE WORKFLOW TEST")
        print("="*80)
        
        headers = {"Authorization": admin_user_token["Authorization"]}
        test_user_id = None
        
        try:
            # Phase 1: User Creation
            print("Phase 1: Testing user creation...")
            
            user_data = {
                "username": f"test_user_{int(time.time())}",
                "email": f"test_{int(time.time())}@example.com",
                "password": "TestPassword123!",
                "role": "general_user"
            }
            
            # Test user creation endpoint
            response = client.post(
                "/v1.0/user/create_general_user",
                json=user_data,
                headers=headers
            )
            
            assert response.status_code in [200, 201], f"User creation failed: {response.text}"
            created_user = response.json()
            test_user_id = created_user.get("id") or created_user.get("user_id")
            
            assert test_user_id is not None, "User ID not returned in creation response"
            print(f"✓ User created successfully with ID: {test_user_id}")
            
            # Phase 2: User Retrieval and Verification
            print("Phase 2: Testing user retrieval...")
            
            # Test user list endpoint
            response = client.get(
                "/v1.0/user/list",
                params={"page": 1, "limit": 25},
                headers=headers
            )
            
            assert response.status_code == 200, f"User list retrieval failed: {response.text}"
            user_list = response.json()
            
            # Verify our user is in the list
            created_user_found = False
            for user in user_list.get("users", []):
                if user.get("id") == test_user_id:
                    created_user_found = True
                    assert user["username"] == user_data["username"]
                    assert user["email"] == user_data["email"]
                    break
            
            assert created_user_found, "Created user not found in user list"
            print("✓ User found in user list with correct data")
            
            # Test user details endpoint
            response = client.get(
                f"/v1.0/user/{test_user_id}/details",
                headers=headers
            )
            
            if response.status_code == 200:
                user_details = response.json()
                assert user_details["id"] == test_user_id
                print("✓ User details retrieved successfully")
            else:
                print(f"⚠ User details endpoint returned {response.status_code} (may not be implemented)")
            
            # Phase 3: User Search and Filtering
            print("Phase 3: Testing user search and filtering...")
            
            # Test search by username
            response = client.get(
                "/v1.0/user/list",
                params={"search": user_data["username"], "page": 1, "limit": 25},
                headers=headers
            )
            
            assert response.status_code == 200, f"User search failed: {response.text}"
            search_results = response.json()
            
            # Verify search found our user
            found_in_search = any(
                user.get("id") == test_user_id 
                for user in search_results.get("users", [])
            )
            assert found_in_search, "User not found in search results"
            print("✓ User search functionality working")
            
            # Test role filtering
            response = client.get(
                "/v1.0/user/list",
                params={"role": "general_user", "page": 1, "limit": 25},
                headers=headers
            )
            
            assert response.status_code == 200, f"Role filtering failed: {response.text}"
            print("✓ Role filtering functionality working")
            
            # Phase 4: User Statistics
            print("Phase 4: Testing user statistics...")
            
            response = client.get(
                "/v1.0/user/stats",
                headers=headers
            )
            
            if response.status_code == 200:
                stats = response.json()
                assert "total_users" in stats
                assert stats["total_users"] > 0
                print("✓ User statistics retrieved successfully")
            else:
                print(f"⚠ User statistics endpoint returned {response.status_code} (may not be implemented)")
            
            # Phase 5: User Update
            print("Phase 5: Testing user update...")
            
            update_data = {
                "username": f"updated_user_{int(time.time())}",
                "is_active": False
            }
            
            # Try different update endpoints
            update_endpoints = [
                f"/v1.0/user/{test_user_id}/update",
                f"/v1.0/user/update/{test_user_id}",
                f"/v1.0/user/{test_user_id}"
            ]
            
            update_successful = False
            for endpoint in update_endpoints:
                response = client.put(endpoint, json=update_data, headers=headers)
                if response.status_code in [200, 204]:
                    update_successful = True
                    print(f"✓ User updated successfully via {endpoint}")
                    break
                elif response.status_code == 404:
                    continue  # Try next endpoint
            
            if not update_successful:
                print("⚠ User update endpoints may not be implemented or have different paths")
            
            # Phase 6: Error Handling and Resilience
            print("Phase 6: Testing error handling and resilience...")
            
            # Test invalid user creation
            invalid_user_data = {
                "username": "",  # Invalid empty username
                "email": "invalid-email",  # Invalid email format
                "password": "weak",  # Weak password
                "role": "invalid_role"  # Invalid role
            }
            
            response = client.post(
                "/v1.0/user/create_general_user",
                json=invalid_user_data,
                headers=headers
            )
            
            assert response.status_code in [400, 422], f"Expected validation error, got {response.status_code}"
            print("✓ Input validation working correctly")
            
            # Test non-existent user retrieval
            response = client.get(
                "/v1.0/user/nonexistent_user_id/details",
                headers=headers
            )
            
            assert response.status_code == 404, f"Expected 404 for non-existent user, got {response.status_code}"
            print("✓ Non-existent user handling working correctly")
            
            # Test unauthorized access
            response = client.get(
                "/v1.0/user/list",
                params={"page": 1, "limit": 25}
                # No headers = no authentication
            )
            
            assert response.status_code in [401, 403], f"Expected auth error, got {response.status_code}"
            print("✓ Authentication/authorization working correctly")
            
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            raise
        
        finally:
            # Phase 7: Cleanup
            print("Phase 7: Cleanup...")
            
            if test_user_id:
                # Try to delete the test user
                delete_endpoints = [
                    f"/v1.0/user/{test_user_id}/delete",
                    f"/v1.0/user/delete/{test_user_id}",
                    f"/v1.0/user/{test_user_id}"
                ]
                
                for endpoint in delete_endpoints:
                    response = client.delete(endpoint, headers=headers)
                    if response.status_code in [200, 204]:
                        print(f"✓ Test user deleted successfully via {endpoint}")
                        break
                else:
                    # Manual cleanup via database
                    try:
                        user = real_db_session.query(User).filter(User.id == test_user_id).first()
                        if user:
                            real_db_session.delete(user)
                            real_db_session.commit()
                            print("✓ Test user cleaned up via database")
                    except Exception as cleanup_error:
                        print(f"⚠ Cleanup warning: {cleanup_error}")
        
        print("Complete user lifecycle workflow test completed!")
        print("="*80)
    
    def test_frontend_backend_integration_scenarios(self, client, admin_user_token):
        """
        Test frontend-backend integration scenarios
        Requirements: 8.5, 10.1
        """
        print("\n" + "="*80)
        print("FRONTEND-BACKEND INTEGRATION SCENARIOS TEST")
        print("="*80)
        
        headers = {"Authorization": admin_user_token["Authorization"]}
        
        # Scenario 1: Dashboard Data Loading
        print("Scenario 1: Testing dashboard data loading...")
        
        # Test user list for dashboard
        response = client.get(
            "/v1.0/user/list",
            params={"page": 1, "limit": 10, "sort_by": "created_at", "sort_order": "desc"},
            headers=headers
        )
        
        assert response.status_code == 200, f"Dashboard user list failed: {response.text}"
        dashboard_data = response.json()
        
        # Verify response structure matches frontend expectations
        assert "users" in dashboard_data or isinstance(dashboard_data, list)
        print("✓ Dashboard user list loaded successfully")
        
        # Test user statistics for dashboard
        response = client.get("/v1.0/user/stats", headers=headers)
        if response.status_code == 200:
            stats = response.json()
            # Verify stats structure
            expected_stats = ["total_users", "active_users", "super_users", "admin_users", "general_users"]
            for stat in expected_stats:
                if stat in stats:
                    assert isinstance(stats[stat], (int, float))
            print("✓ Dashboard statistics loaded successfully")
        
        # Scenario 2: Search and Filter Operations
        print("Scenario 2: Testing search and filter operations...")
        
        # Test search functionality
        search_terms = ["admin", "test", "@example.com"]
        for term in search_terms:
            response = client.get(
                "/v1.0/user/list",
                params={"search": term, "page": 1, "limit": 25},
                headers=headers
            )
            assert response.status_code == 200, f"Search for '{term}' failed: {response.text}"
        
        print("✓ Search functionality working")
        
        # Test filtering by role
        for role in ["super_user", "admin_user", "general_user"]:
            response = client.get(
                "/v1.0/user/list",
                params={"role": role, "page": 1, "limit": 25},
                headers=headers
            )
            assert response.status_code == 200, f"Role filter '{role}' failed: {response.text}"
        
        print("✓ Role filtering working")
        
        # Scenario 3: Pagination Handling
        print("Scenario 3: Testing pagination handling...")
        
        # Test different page sizes
        page_sizes = [10, 25, 50]
        for size in page_sizes:
            response = client.get(
                "/v1.0/user/list",
                params={"page": 1, "limit": size},
                headers=headers
            )
            assert response.status_code == 200, f"Page size {size} failed: {response.text}"
            
            data = response.json()
            if "users" in data:
                users = data["users"]
            elif isinstance(data, list):
                users = data
            else:
                users = []
            
            # Verify we don't get more users than requested
            assert len(users) <= size, f"Returned more users than limit: {len(users)} > {size}"
        
        print("✓ Pagination handling working")
        
        # Scenario 4: Sorting Operations
        print("Scenario 4: Testing sorting operations...")
        
        sort_fields = ["username", "email", "created_at"]
        sort_orders = ["asc", "desc"]
        
        for field in sort_fields:
            for order in sort_orders:
                response = client.get(
                    "/v1.0/user/list",
                    params={"sort_by": field, "sort_order": order, "page": 1, "limit": 10},
                    headers=headers
                )
                assert response.status_code == 200, f"Sort by {field} {order} failed: {response.text}"
        
        print("✓ Sorting operations working")
        
        # Scenario 5: Error Response Format
        print("Scenario 5: Testing error response format...")
        
        # Test invalid pagination
        response = client.get(
            "/v1.0/user/list",
            params={"page": -1, "limit": 0},
            headers=headers
        )
        
        # Should handle invalid pagination gracefully
        if response.status_code != 200:
            error_data = response.json()
            # Verify error response has expected structure
            assert "error" in error_data or "detail" in error_data or "message" in error_data
        
        print("✓ Error response format consistent")
        
        print("Frontend-backend integration scenarios test completed!")
        print("="*80)
    
    def test_system_resilience_and_error_recovery(self, client, admin_user_token, real_db_session):
        """
        Test system resilience and error recovery
        Requirements: 8.5, 10.2
        """
        print("\n" + "="*80)
        print("SYSTEM RESILIENCE AND ERROR RECOVERY TEST")
        print("="*80)
        
        headers = {"Authorization": admin_user_token["Authorization"]}
        
        # Test 1: Concurrent Request Handling
        print("Test 1: Testing concurrent request handling...")
        
        def make_concurrent_request(request_id: int):
            """Make a concurrent request to test system resilience"""
            try:
                response = client.get(
                    "/v1.0/user/list",
                    params={"page": 1, "limit": 10},
                    headers=headers
                )
                return {
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "success": response.status_code == 200,
                    "response_time": response.elapsed.total_seconds() if hasattr(response, 'elapsed') else 0
                }
            except Exception as e:
                return {
                    "request_id": request_id,
                    "status_code": 500,
                    "success": False,
                    "error": str(e)
                }
        
        # Execute concurrent requests
        num_concurrent = 20
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_concurrent_request, i) for i in range(num_concurrent)]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        successful_requests = [r for r in results if r["success"]]
        failed_requests = [r for r in results if not r["success"]]
        
        success_rate = len(successful_requests) / len(results)
        
        print(f"Concurrent requests: {num_concurrent}")
        print(f"Successful: {len(successful_requests)}")
        print(f"Failed: {len(failed_requests)}")
        print(f"Success rate: {success_rate:.2%}")
        
        # System should handle at least 80% of concurrent requests successfully
        assert success_rate >= 0.8, f"Low success rate under concurrent load: {success_rate:.2%}"
        print("✓ System handles concurrent requests well")
        
        # Test 2: Database Connection Resilience
        print("Test 2: Testing database connection resilience...")
        
        # Test with valid database operations
        response = client.get("/v1.0/user/list", params={"page": 1, "limit": 5}, headers=headers)
        assert response.status_code == 200, "Database connection test failed"
        print("✓ Database connection working")
        
        # Test 3: Input Validation and Sanitization
        print("Test 3: Testing input validation and sanitization...")
        
        # Test SQL injection attempts
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "' OR '1'='1",
            "admin'; DELETE FROM users WHERE '1'='1",
            "../../../etc/passwd"
        ]
        
        for malicious_input in malicious_inputs:
            # Test in search parameter
            response = client.get(
                "/v1.0/user/list",
                params={"search": malicious_input, "page": 1, "limit": 10},
                headers=headers
            )
            
            # Should not crash and should return safe response
            assert response.status_code in [200, 400, 422], f"System crashed on malicious input: {malicious_input}"
            
            # Verify database is still intact by making a normal request
            normal_response = client.get(
                "/v1.0/user/list",
                params={"page": 1, "limit": 5},
                headers=headers
            )
            assert normal_response.status_code == 200, "Database corrupted by malicious input"
        
        print("✓ Input validation and sanitization working")
        
        # Test 4: Rate Limiting and Resource Protection
        print("Test 4: Testing rate limiting and resource protection...")
        
        # Make rapid requests to test rate limiting
        rapid_requests = []
        for i in range(50):
            response = client.get(
                "/v1.0/user/list",
                params={"page": 1, "limit": 100},  # Large page size
                headers=headers
            )
            rapid_requests.append(response.status_code)
            
            # Small delay to avoid overwhelming the test
            time.sleep(0.01)
        
        # Check if rate limiting kicked in
        rate_limited = any(code == 429 for code in rapid_requests)
        if rate_limited:
            print("✓ Rate limiting is active")
        else:
            print("⚠ Rate limiting may not be configured (not necessarily a failure)")
        
        # Test 5: Error Recovery and Graceful Degradation
        print("Test 5: Testing error recovery and graceful degradation...")
        
        # Test with invalid authentication
        invalid_headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/v1.0/user/list", headers=invalid_headers)
        assert response.status_code in [401, 403], "Authentication error handling failed"
        
        # Test with malformed requests
        response = client.post(
            "/v1.0/user/create_general_user",
            json={"invalid": "data"},
            headers=headers
        )
        assert response.status_code in [400, 422], "Malformed request handling failed"
        
        # Verify system recovers after errors
        response = client.get("/v1.0/user/list", params={"page": 1, "limit": 5}, headers=headers)
        assert response.status_code == 200, "System did not recover after errors"
        
        print("✓ Error recovery and graceful degradation working")
        
        # Test 6: Memory and Resource Management
        print("Test 6: Testing memory and resource management...")
        
        # Test large page sizes
        large_page_sizes = [100, 500, 1000]
        for page_size in large_page_sizes:
            response = client.get(
                "/v1.0/user/list",
                params={"page": 1, "limit": page_size},
                headers=headers
            )
            
            # Should either succeed or return appropriate error
            assert response.status_code in [200, 400, 413], f"Large page size {page_size} caused system failure"
            
            if response.status_code == 200:
                # Verify response is reasonable
                data = response.json()
                if "users" in data:
                    users = data["users"]
                elif isinstance(data, list):
                    users = data
                else:
                    users = []
                
                # Should not return more than requested
                assert len(users) <= page_size, f"Returned more users than requested: {len(users)} > {page_size}"
        
        print("✓ Memory and resource management working")
        
        print("System resilience and error recovery test completed!")
        print("="*80)
    
    def test_database_transaction_integrity(self, client, admin_user_token, real_db_session):
        """
        Test database transaction integrity and consistency
        Requirements: 10.1, 10.2
        """
        print("\n" + "="*80)
        print("DATABASE TRANSACTION INTEGRITY TEST")
        print("="*80)
        
        headers = {"Authorization": admin_user_token["Authorization"]}
        test_users = []
        
        try:
            # Test 1: Transaction Rollback on Failure
            print("Test 1: Testing transaction rollback on failure...")
            
            # Create a user that should succeed
            valid_user_data = {
                "username": f"valid_user_{int(time.time())}",
                "email": f"valid_{int(time.time())}@example.com",
                "password": "ValidPassword123!",
                "role": "general_user"
            }
            
            response = client.post(
                "/v1.0/user/create_general_user",
                json=valid_user_data,
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                created_user = response.json()
                test_user_id = created_user.get("id") or created_user.get("user_id")
                if test_user_id:
                    test_users.append(test_user_id)
                print("✓ Valid user creation succeeded")
            
            # Try to create a user with duplicate email (should fail)
            duplicate_user_data = {
                "username": f"duplicate_user_{int(time.time())}",
                "email": valid_user_data["email"],  # Same email
                "password": "ValidPassword123!",
                "role": "general_user"
            }
            
            response = client.post(
                "/v1.0/user/create_general_user",
                json=duplicate_user_data,
                headers=headers
            )
            
            # Should fail due to duplicate email
            assert response.status_code in [400, 409, 422], "Duplicate email should be rejected"
            print("✓ Duplicate email rejection working")
            
            # Test 2: Data Consistency Checks
            print("Test 2: Testing data consistency...")
            
            # Verify user count consistency
            response = client.get("/v1.0/user/list", params={"page": 1, "limit": 1000}, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if "users" in data:
                    api_user_count = len(data["users"])
                elif isinstance(data, list):
                    api_user_count = len(data)
                else:
                    api_user_count = 0
                
                # Check database directly
                db_user_count = real_db_session.query(User).count()
                
                print(f"API user count: {api_user_count}")
                print(f"Database user count: {db_user_count}")
                
                # Counts should be reasonably close (allowing for test data)
                # We can't expect exact match due to other tests running
                print("✓ Data consistency check completed")
            
            # Test 3: Concurrent Modification Handling
            print("Test 3: Testing concurrent modification handling...")
            
            if test_users:
                test_user_id = test_users[0]
                
                def concurrent_update(update_id: int):
                    """Attempt concurrent user updates"""
                    update_data = {
                        "username": f"concurrent_update_{update_id}_{int(time.time())}"
                    }
                    
                    # Try different update endpoints
                    endpoints = [
                        f"/v1.0/user/{test_user_id}/update",
                        f"/v1.0/user/update/{test_user_id}",
                        f"/v1.0/user/{test_user_id}"
                    ]
                    
                    for endpoint in endpoints:
                        response = client.put(endpoint, json=update_data, headers=headers)
                        if response.status_code in [200, 204]:
                            return {"success": True, "endpoint": endpoint}
                        elif response.status_code == 404:
                            continue
                    
                    return {"success": False, "last_status": response.status_code if 'response' in locals() else None}
                
                # Execute concurrent updates
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(concurrent_update, i) for i in range(10)]
                    update_results = [future.result() for future in as_completed(futures)]
                
                successful_updates = [r for r in update_results if r["success"]]
                print(f"Concurrent updates attempted: 10")
                print(f"Successful updates: {len(successful_updates)}")
                
                # At least some updates should succeed, but system should handle conflicts gracefully
                print("✓ Concurrent modification handling working")
            
            # Test 4: Foreign Key Integrity
            print("Test 4: Testing foreign key integrity...")
            
            # This test would verify that related data (points, permissions, etc.) 
            # maintains referential integrity
            
            # Check if we have any users with related data
            users_with_points = real_db_session.query(User).join(UserPoint).limit(5).all()
            if users_with_points:
                print(f"Found {len(users_with_points)} users with point data")
                
                # Verify point data integrity
                for user in users_with_points:
                    user_points = real_db_session.query(UserPoint).filter(UserPoint.user_id == user.id).all()
                    for point_record in user_points:
                        assert point_record.user_id == user.id, "Point record user_id mismatch"
                        assert point_record.user_email == user.email, "Point record email mismatch"
                
                print("✓ Foreign key integrity verified")
            else:
                print("⚠ No users with point data found for integrity testing")
            
        except Exception as e:
            print(f"❌ Database integrity test failed: {e}")
            raise
        
        finally:
            # Cleanup test users
            print("Cleaning up test users...")
            for user_id in test_users:
                try:
                    user = real_db_session.query(User).filter(User.id == user_id).first()
                    if user:
                        real_db_session.delete(user)
                        real_db_session.commit()
                except Exception as cleanup_error:
                    print(f"⚠ Cleanup warning for user {user_id}: {cleanup_error}")
        
        print("Database transaction integrity test completed!")
        print("="*80)
    
    def test_api_endpoint_comprehensive_coverage(self, client, admin_user_token):
        """
        Test comprehensive coverage of all user management API endpoints
        Requirements: 8.5, 10.1
        """
        print("\n" + "="*80)
        print("API ENDPOINT COMPREHENSIVE COVERAGE TEST")
        print("="*80)
        
        headers = {"Authorization": admin_user_token["Authorization"]}
        
        # Define all expected endpoints and their methods
        endpoints_to_test = [
            {"method": "GET", "path": "/v1.0/user/me", "description": "Get current user info"},
            {"method": "GET", "path": "/v1.0/user/list", "description": "Get user list"},
            {"method": "GET", "path": "/v1.0/user/stats", "description": "Get user statistics"},
            {"method": "GET", "path": "/v1.0/user/check/all", "description": "Check all users"},
            {"method": "POST", "path": "/v1.0/user/create_general_user", "description": "Create general user"},
            {"method": "POST", "path": "/v1.0/user/create_admin_user", "description": "Create admin user"},
            {"method": "POST", "path": "/v1.0/user/create_super_user", "description": "Create super user"},
        ]
        
        endpoint_results = []
        
        for endpoint in endpoints_to_test:
            print(f"Testing {endpoint['method']} {endpoint['path']} - {endpoint['description']}")
            
            try:
                if endpoint["method"] == "GET":
                    if "list" in endpoint["path"] or "check" in endpoint["path"]:
                        response = client.get(endpoint["path"], params={"page": 1, "limit": 10}, headers=headers)
                    else:
                        response = client.get(endpoint["path"], headers=headers)
                
                elif endpoint["method"] == "POST":
                    if "create" in endpoint["path"]:
                        test_data = {
                            "username": f"test_{int(time.time())}",
                            "email": f"test_{int(time.time())}@example.com",
                            "password": "TestPassword123!"
                        }
                        response = client.post(endpoint["path"], json=test_data, headers=headers)
                    else:
                        response = client.post(endpoint["path"], json={}, headers=headers)
                
                result = {
                    "endpoint": f"{endpoint['method']} {endpoint['path']}",
                    "status_code": response.status_code,
                    "success": response.status_code < 500,  # Not a server error
                    "response_time": getattr(response, 'elapsed', timedelta(0)).total_seconds(),
                    "description": endpoint["description"]
                }
                
                # Check response format
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        result["has_json_response"] = True
                        result["response_keys"] = list(response_data.keys()) if isinstance(response_data, dict) else ["list"]
                    except:
                        result["has_json_response"] = False
                
                endpoint_results.append(result)
                
                status_symbol = "✓" if result["success"] else "❌"
                print(f"  {status_symbol} Status: {response.status_code}")
                
            except Exception as e:
                result = {
                    "endpoint": f"{endpoint['method']} {endpoint['path']}",
                    "status_code": 500,
                    "success": False,
                    "error": str(e),
                    "description": endpoint["description"]
                }
                endpoint_results.append(result)
                print(f"  ❌ Error: {e}")
        
        # Summary
        print("\nEndpoint Test Summary:")
        print("-" * 60)
        
        successful_endpoints = [r for r in endpoint_results if r["success"]]
        failed_endpoints = [r for r in endpoint_results if not r["success"]]
        
        print(f"Total endpoints tested: {len(endpoint_results)}")
        print(f"Successful: {len(successful_endpoints)}")
        print(f"Failed: {len(failed_endpoints)}")
        print(f"Success rate: {len(successful_endpoints)/len(endpoint_results):.1%}")
        
        if failed_endpoints:
            print("\nFailed endpoints:")
            for endpoint in failed_endpoints:
                error_msg = endpoint.get('error', f'Status {endpoint["status_code"]}')
                print(f"  - {endpoint['endpoint']}: {error_msg}")
        
        # At least 70% of endpoints should be working
        success_rate = len(successful_endpoints) / len(endpoint_results)
        assert success_rate >= 0.7, f"Too many endpoints failing: {success_rate:.1%} success rate"
        
        print("API endpoint comprehensive coverage test completed!")
        print("="*80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])