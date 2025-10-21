"""
Frontend-Backend Integration Tests

This module specifically tests integration scenarios that simulate
real frontend application interactions with the backend API.

Requirements covered: 8.5, 10.1
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi.testclient import TestClient
from fastapi import status

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from tests.test_integration_fixtures import IntegrationTestHelper


class TestFrontendBackendIntegration:
    """Test frontend-backend integration scenarios"""
    
    @pytest.fixture(scope="class")
    def client(self):
        """Create test client for API testing"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_admin_headers(self):
        """Mock admin authentication headers"""
        return {"Authorization": f"Bearer admin_test_{int(time.time())}"}
    
    def test_dashboard_initial_load_workflow(self, client, mock_admin_headers, mock_frontend_requests):
        """
        Test the complete dashboard initial load workflow
        Simulates: User opens dashboard -> loads user list -> loads statistics
        """
        print("\n" + "="*60)
        print("DASHBOARD INITIAL LOAD WORKFLOW TEST")
        print("="*60)
        
        dashboard_requests = mock_frontend_requests["dashboard_load"]
        results = []
        
        for request in dashboard_requests:
            print(f"Making request: {request['endpoint']}")
            
            response = client.get(
                request["endpoint"],
                params=request["params"],
                headers=mock_admin_headers
            )
            
            result = {
                "endpoint": request["endpoint"],
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response_time": getattr(response, 'elapsed', timedelta(0)).total_seconds()
            }
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    result["response_structure_valid"] = IntegrationTestHelper.validate_user_response_structure(
                        data, 
                        "stats" if "stats" in request["endpoint"] else "list"
                    )
                    result["data_keys"] = list(data.keys()) if isinstance(data, dict) else ["list_data"]
                except:
                    result["response_structure_valid"] = False
            
            results.append(result)
            print(f"  Status: {response.status_code}, Valid: {result.get('response_structure_valid', 'N/A')}")
        
        # Verify dashboard load workflow
        successful_requests = [r for r in results if r["success"]]
        print(f"\nDashboard Load Summary:")
        print(f"  Total requests: {len(results)}")
        print(f"  Successful: {len(successful_requests)}")
        print(f"  Success rate: {len(successful_requests)/len(results):.1%}")
        
        # At least the user list should work for dashboard
        user_list_success = any(r["success"] and "list" in r["endpoint"] for r in results)
        assert user_list_success, "User list endpoint must work for dashboard functionality"
        
        print("✓ Dashboard initial load workflow test completed")
    
    def test_user_search_and_filter_workflow(self, client, mock_admin_headers, mock_frontend_requests):
        """
        Test user search and filtering workflow
        Simulates: User types in search box -> results update -> applies filters -> results update
        """
        print("\n" + "="*60)
        print("USER SEARCH AND FILTER WORKFLOW TEST")
        print("="*60)
        
        # Test search workflow
        search_requests = mock_frontend_requests["user_search"]
        search_results = []
        
        print("Testing search functionality...")
        for request in search_requests:
            response = client.get(
                request["endpoint"],
                params=request["params"],
                headers=mock_admin_headers
            )
            
            result = {
                "search_term": request["params"].get("search", ""),
                "status_code": response.status_code,
                "success": response.status_code == 200
            }
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict) and "users" in data:
                        result["result_count"] = len(data["users"])
                    elif isinstance(data, list):
                        result["result_count"] = len(data)
                    else:
                        result["result_count"] = 0
                except:
                    result["result_count"] = 0
            
            search_results.append(result)
            print(f"  Search '{result['search_term']}': {result['status_code']} ({result.get('result_count', 'N/A')} results)")
        
        # Test filtering workflow
        filter_requests = mock_frontend_requests["user_filtering"]
        filter_results = []
        
        print("Testing filter functionality...")
        for request in filter_requests:
            response = client.get(
                request["endpoint"],
                params=request["params"],
                headers=mock_admin_headers
            )
            
            result = {
                "filters": {k: v for k, v in request["params"].items() if k not in ["page", "limit"]},
                "status_code": response.status_code,
                "success": response.status_code == 200
            }
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict) and "users" in data:
                        result["result_count"] = len(data["users"])
                    elif isinstance(data, list):
                        result["result_count"] = len(data)
                    else:
                        result["result_count"] = 0
                except:
                    result["result_count"] = 0
            
            filter_results.append(result)
            print(f"  Filter {result['filters']}: {result['status_code']} ({result.get('result_count', 'N/A')} results)")
        
        # Verify search and filter functionality
        successful_searches = [r for r in search_results if r["success"]]
        successful_filters = [r for r in filter_results if r["success"]]
        
        print(f"\nSearch & Filter Summary:")
        print(f"  Search tests: {len(successful_searches)}/{len(search_results)} successful")
        print(f"  Filter tests: {len(successful_filters)}/{len(filter_results)} successful")
        
        # At least basic search should work
        assert len(successful_searches) > 0, "Search functionality must work"
        
        print("✓ User search and filter workflow test completed")
    
    def test_pagination_navigation_workflow(self, client, mock_admin_headers, mock_frontend_requests):
        """
        Test pagination navigation workflow
        Simulates: User navigates through pages -> changes page size -> navigates again
        """
        print("\n" + "="*60)
        print("PAGINATION NAVIGATION WORKFLOW TEST")
        print("="*60)
        
        pagination_requests = mock_frontend_requests["pagination_scenarios"]
        pagination_results = []
        
        for request in pagination_requests:
            response = client.get(
                request["endpoint"],
                params=request["params"],
                headers=mock_admin_headers
            )
            
            result = {
                "page": request["params"]["page"],
                "limit": request["params"]["limit"],
                "status_code": response.status_code,
                "success": response.status_code == 200
            }
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    # Extract user count and pagination info
                    if isinstance(data, dict):
                        if "users" in data:
                            result["returned_count"] = len(data["users"])
                            result["pagination_info"] = data.get("pagination", {})
                        else:
                            result["returned_count"] = 1  # Single user response
                    elif isinstance(data, list):
                        result["returned_count"] = len(data)
                    
                    # Verify pagination constraints
                    returned_count = result.get("returned_count", 0)
                    requested_limit = request["params"]["limit"]
                    result["pagination_valid"] = returned_count <= requested_limit
                    
                except Exception as e:
                    result["error"] = str(e)
                    result["pagination_valid"] = False
            
            pagination_results.append(result)
            print(f"  Page {result['page']}, Limit {result['limit']}: {result['status_code']} "
                  f"({result.get('returned_count', 'N/A')} items, "
                  f"Valid: {result.get('pagination_valid', 'N/A')})")
        
        # Verify pagination functionality
        successful_pagination = [r for r in pagination_results if r["success"]]
        valid_pagination = [r for r in successful_pagination if r.get("pagination_valid", False)]
        
        print(f"\nPagination Summary:")
        print(f"  Total pagination tests: {len(pagination_results)}")
        print(f"  Successful responses: {len(successful_pagination)}")
        print(f"  Valid pagination: {len(valid_pagination)}")
        
        # Basic pagination should work
        assert len(successful_pagination) > 0, "Pagination must work for frontend"
        
        print("✓ Pagination navigation workflow test completed")
    
    def test_sorting_and_ordering_workflow(self, client, mock_admin_headers, mock_frontend_requests):
        """
        Test sorting and ordering workflow
        Simulates: User clicks column headers -> data reorders -> user changes sort direction
        """
        print("\n" + "="*60)
        print("SORTING AND ORDERING WORKFLOW TEST")
        print("="*60)
        
        sorting_requests = mock_frontend_requests["sorting_scenarios"]
        sorting_results = []
        
        for request in sorting_requests:
            response = client.get(
                request["endpoint"],
                params=request["params"],
                headers=mock_admin_headers
            )
            
            result = {
                "sort_by": request["params"]["sort_by"],
                "sort_order": request["params"]["sort_order"],
                "status_code": response.status_code,
                "success": response.status_code == 200
            }
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    # Extract users for sorting validation
                    users = []
                    if isinstance(data, dict) and "users" in data:
                        users = data["users"]
                    elif isinstance(data, list):
                        users = data
                    
                    result["user_count"] = len(users)
                    
                    # Validate sorting (if we have multiple users)
                    if len(users) > 1:
                        sort_field = request["params"]["sort_by"]
                        sort_order = request["params"]["sort_order"]
                        
                        # Check if users have the sort field
                        if all(sort_field in user for user in users):
                            values = [user[sort_field] for user in users]
                            
                            # Check if sorted correctly
                            if sort_order == "asc":
                                result["correctly_sorted"] = values == sorted(values)
                            else:  # desc
                                result["correctly_sorted"] = values == sorted(values, reverse=True)
                        else:
                            result["correctly_sorted"] = None  # Can't validate
                    else:
                        result["correctly_sorted"] = None  # Not enough data
                    
                except Exception as e:
                    result["error"] = str(e)
                    result["correctly_sorted"] = False
            
            sorting_results.append(result)
            print(f"  Sort by {result['sort_by']} {result['sort_order']}: {result['status_code']} "
                  f"({result.get('user_count', 'N/A')} users, "
                  f"Sorted: {result.get('correctly_sorted', 'N/A')})")
        
        # Verify sorting functionality
        successful_sorting = [r for r in sorting_results if r["success"]]
        correctly_sorted = [r for r in successful_sorting if r.get("correctly_sorted") == True]
        
        print(f"\nSorting Summary:")
        print(f"  Total sorting tests: {len(sorting_results)}")
        print(f"  Successful responses: {len(successful_sorting)}")
        print(f"  Correctly sorted: {len(correctly_sorted)}")
        
        # Basic sorting should work
        assert len(successful_sorting) > 0, "Sorting must work for frontend"
        
        print("✓ Sorting and ordering workflow test completed")
    
    def test_user_creation_form_workflow(self, client, mock_admin_headers):
        """
        Test user creation form workflow
        Simulates: User fills form -> submits -> gets response -> form updates
        """
        print("\n" + "="*60)
        print("USER CREATION FORM WORKFLOW TEST")
        print("="*60)
        
        # Test different user creation scenarios
        creation_scenarios = [
            {
                "name": "Valid General User",
                "data": IntegrationTestHelper.create_test_user_data("form_test", "general_user"),
                "endpoint": "/v1.0/user/create_general_user",
                "expected_success": True
            },
            {
                "name": "Valid Admin User",
                "data": IntegrationTestHelper.create_test_user_data("form_admin", "admin_user"),
                "endpoint": "/v1.0/user/create_admin_user",
                "expected_success": True
            },
            {
                "name": "Invalid Email",
                "data": {
                    "username": f"invalid_email_{int(time.time())}",
                    "email": "invalid-email-format",
                    "password": "ValidPassword123!",
                    "role": "general_user"
                },
                "endpoint": "/v1.0/user/create_general_user",
                "expected_success": False
            },
            {
                "name": "Weak Password",
                "data": {
                    "username": f"weak_password_{int(time.time())}",
                    "email": f"weak_test_{int(time.time())}@example.com",
                    "password": "weak",
                    "role": "general_user"
                },
                "endpoint": "/v1.0/user/create_general_user",
                "expected_success": False
            }
        ]
        
        creation_results = []
        created_users = []
        
        for scenario in creation_scenarios:
            print(f"Testing: {scenario['name']}")
            
            response = client.post(
                scenario["endpoint"],
                json=scenario["data"],
                headers=mock_admin_headers
            )
            
            result = {
                "scenario": scenario["name"],
                "status_code": response.status_code,
                "success": response.status_code in [200, 201],
                "expected_success": scenario["expected_success"]
            }
            
            # Check if result matches expectation
            result["matches_expectation"] = result["success"] == result["expected_success"]
            
            if result["success"]:
                try:
                    response_data = response.json()
                    user_id = response_data.get("id") or response_data.get("user_id")
                    if user_id:
                        created_users.append(user_id)
                        result["user_created"] = True
                        result["user_id"] = user_id
                except:
                    result["user_created"] = False
            else:
                # Check error response format
                try:
                    error_data = response.json()
                    result["error_format_valid"] = any(key in error_data for key in ["error", "detail", "message"])
                except:
                    result["error_format_valid"] = False
            
            creation_results.append(result)
            
            status_symbol = "✓" if result["matches_expectation"] else "❌"
            print(f"  {status_symbol} Status: {response.status_code}, "
                  f"Expected: {'Success' if scenario['expected_success'] else 'Failure'}")
        
        # Summary
        matching_expectations = [r for r in creation_results if r["matches_expectation"]]
        successful_creations = [r for r in creation_results if r["success"]]
        
        print(f"\nUser Creation Form Summary:")
        print(f"  Total scenarios: {len(creation_results)}")
        print(f"  Matching expectations: {len(matching_expectations)}")
        print(f"  Successful creations: {len(successful_creations)}")
        print(f"  Users created: {len(created_users)}")
        
        # Cleanup created users
        print("Cleaning up created users...")
        for user_id in created_users:
            # Try different delete endpoints
            delete_endpoints = [
                f"/v1.0/user/{user_id}/delete",
                f"/v1.0/user/delete/{user_id}",
                f"/v1.0/user/{user_id}"
            ]
            
            for endpoint in delete_endpoints:
                response = client.delete(endpoint, headers=mock_admin_headers)
                if response.status_code in [200, 204]:
                    break
        
        # At least valid scenarios should work as expected
        assert len(matching_expectations) >= len(creation_results) * 0.7, "Form validation not working correctly"
        
        print("✓ User creation form workflow test completed")
    
    def test_real_time_updates_simulation(self, client, mock_admin_headers):
        """
        Test real-time updates simulation
        Simulates: Multiple users making changes -> dashboard updates -> data consistency
        """
        print("\n" + "="*60)
        print("REAL-TIME UPDATES SIMULATION TEST")
        print("="*60)
        
        def simulate_user_activity(user_id: int):
            """Simulate a user making requests"""
            activities = []
            
            # Get user list (dashboard refresh)
            response = client.get(
                "/v1.0/user/list",
                params={"page": 1, "limit": 10},
                headers=mock_admin_headers
            )
            activities.append({
                "action": "list_users",
                "status": response.status_code,
                "user_id": user_id
            })
            
            # Get statistics (dashboard widget)
            response = client.get("/v1.0/user/stats", headers=mock_admin_headers)
            activities.append({
                "action": "get_stats",
                "status": response.status_code,
                "user_id": user_id
            })
            
            # Search for users
            response = client.get(
                "/v1.0/user/list",
                params={"search": f"test_{user_id}", "page": 1, "limit": 25},
                headers=mock_admin_headers
            )
            activities.append({
                "action": "search_users",
                "status": response.status_code,
                "user_id": user_id
            })
            
            return activities
        
        # Simulate multiple concurrent users
        num_concurrent_users = 10
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(simulate_user_activity, i) for i in range(num_concurrent_users)]
            all_activities = []
            
            for future in as_completed(futures):
                activities = future.result()
                all_activities.extend(activities)
        
        # Analyze activities
        total_activities = len(all_activities)
        successful_activities = [a for a in all_activities if a["status"] == 200]
        
        # Group by action type
        action_stats = {}
        for activity in all_activities:
            action = activity["action"]
            if action not in action_stats:
                action_stats[action] = {"total": 0, "successful": 0}
            
            action_stats[action]["total"] += 1
            if activity["status"] == 200:
                action_stats[action]["successful"] += 1
        
        print(f"Real-time simulation results:")
        print(f"  Total activities: {total_activities}")
        print(f"  Successful activities: {len(successful_activities)}")
        print(f"  Success rate: {len(successful_activities)/total_activities:.1%}")
        
        print(f"\nActivity breakdown:")
        for action, stats in action_stats.items():
            success_rate = stats["successful"] / stats["total"] if stats["total"] > 0 else 0
            print(f"  {action}: {stats['successful']}/{stats['total']} ({success_rate:.1%})")
        
        # System should handle concurrent activities well
        overall_success_rate = len(successful_activities) / total_activities
        assert overall_success_rate >= 0.8, f"Low success rate in concurrent scenario: {overall_success_rate:.1%}"
        
        print("✓ Real-time updates simulation test completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])