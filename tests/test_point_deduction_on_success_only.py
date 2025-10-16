#!/usr/bin/env python3
"""
Test script to verify that points are only deducted on SUCCESSFUL requests
for /v1.0/content/get_hotel_with_ittid/{ittid} endpoint
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"

# Test credentials
TEST_USERS = {
    "superuser": {
        "username": "superadmin",  # Replace with actual superuser
        "password": "your_password"
    },
    "admin": {
        "username": "admin_user",  # Replace with actual admin user
        "password": "your_password"
    },
    "general": {
        "username": "general_user",  # Replace with actual general user
        "password": "your_password"
    }
}

# Test ITTIDs for different scenarios
TEST_CASES = {
    "valid_accessible": "12345",      # ITTID that exists, has suppliers, and user has access
    "valid_no_access": "67890",       # ITTID that exists, has suppliers, but user has no access
    "valid_no_suppliers": "11111",    # ITTID that exists but has no suppliers
    "invalid_ittid": "99999",         # ITTID that doesn't exist
}

def get_auth_token(username: str, password: str) -> str:
    """Get authentication token"""
    try:
        response = requests.post(
            f"{BASE_URL}/v1.0/auth/login",
            data={"username": username, "password": password}
        )
        
        if response.status_code == 200:
            token_data = response.json()
            return token_data.get("access_token")
        else:
            print(f"❌ Login failed for {username}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Login error for {username}: {e}")
        return None

def get_user_points(token: str) -> dict:
    """Get current user's point information"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/v1.0/user/me", headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            return {
                "available_points": user_data.get("available_points", 0),
                "total_points": user_data.get("total_points", 0),
                "user_status": user_data.get("user_status", "unknown"),
                "username": user_data.get("username", "unknown")
            }
        else:
            print(f"❌ Failed to get user info: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error getting user info: {e}")
        return None

def test_get_hotel_by_ittid(token: str, ittid: str) -> dict:
    """Test GET /v1.0/content/get_hotel_with_ittid/{ittid} endpoint"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/v1.0/content/get_hotel_with_ittid/{ittid}",
            headers=headers
        )
        
        return {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "response_data": response.json() if response.status_code == 200 else None,
            "error": response.text if response.status_code != 200 else None,
            "ittid": ittid
        }
        
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        return {"status_code": 500, "success": False, "error": str(e), "ittid": ittid}

def test_point_deduction_on_success_only():
    """Test that points are only deducted on successful requests"""
    
    print("💸 Testing Point Deduction ONLY on Successful Requests")
    print("=" * 80)
    print("Verifying that points are NOT deducted when requests fail due to:")
    print("• Hotel not found (404)")
    print("• No active suppliers (404)")
    print("• No user access to suppliers (403)")
    print("• Other permission errors (403)")
    print("=" * 80)
    
    # Test with general user (who has point deductions)
    general_token = get_auth_token(
        TEST_USERS["general"]["username"], 
        TEST_USERS["general"]["password"]
    )
    
    if not general_token:
        print("❌ Cannot get general user token - skipping tests")
        return
    
    print("👤 Testing with GENERAL USER (subject to point deductions)")
    print("-" * 60)
    
    # Get initial points
    initial_points = get_user_points(general_token)
    if not initial_points:
        print("❌ Cannot get initial points - skipping tests")
        return
    
    print(f"💰 Initial Points: {initial_points['available_points']}")
    print(f"👤 User: {initial_points['username']} ({initial_points['user_status']})")
    
    test_scenarios = [
        {
            "name": "Invalid ITTID (Hotel Not Found)",
            "ittid": TEST_CASES["invalid_ittid"],
            "expected_status": 404,
            "should_deduct_points": False,
            "description": "Should NOT deduct points when hotel doesn't exist"
        },
        {
            "name": "Valid ITTID with No Suppliers",
            "ittid": TEST_CASES["valid_no_suppliers"],
            "expected_status": 404,
            "should_deduct_points": False,
            "description": "Should NOT deduct points when hotel has no active suppliers"
        },
        {
            "name": "Valid ITTID with No User Access",
            "ittid": TEST_CASES["valid_no_access"],
            "expected_status": 403,
            "should_deduct_points": False,
            "description": "Should NOT deduct points when user lacks supplier permissions"
        },
        {
            "name": "Valid ITTID with User Access",
            "ittid": TEST_CASES["valid_accessible"],
            "expected_status": 200,
            "should_deduct_points": True,
            "description": "Should deduct points ONLY when request is successful"
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n🧪 Test {i}: {scenario['name']}")
        print(f"   ITTID: {scenario['ittid']}")
        print(f"   Expected: {scenario['expected_status']} - {scenario['description']}")
        
        # Get points before request
        before_points = get_user_points(general_token)
        if not before_points:
            print("   ❌ Cannot get points before request")
            continue
        
        # Make request
        result = test_get_hotel_by_ittid(general_token, scenario["ittid"])
        
        # Get points after request
        after_points = get_user_points(general_token)
        if not after_points:
            print("   ❌ Cannot get points after request")
            continue
        
        # Calculate point change
        points_deducted = before_points["available_points"] - after_points["available_points"]
        
        # Verify response status
        if result["status_code"] == scenario["expected_status"]:
            print(f"   ✅ Status Code: {result['status_code']} (as expected)")
        else:
            print(f"   ⚠️  Status Code: {result['status_code']} (expected {scenario['expected_status']})")
        
        # Verify point deduction behavior
        if scenario["should_deduct_points"]:
            if points_deducted > 0:
                print(f"   ✅ Points Deducted: {points_deducted} (as expected for successful request)")
                print(f"   💰 Points: {before_points['available_points']} → {after_points['available_points']}")
            else:
                print(f"   ❌ FAIL: No points deducted on successful request")
        else:
            if points_deducted == 0:
                print(f"   ✅ Points NOT Deducted: 0 (as expected for failed request)")
                print(f"   💰 Points: {before_points['available_points']} (unchanged)")
            else:
                print(f"   ❌ FAIL: {points_deducted} points deducted on failed request!")
                print(f"   💰 Points: {before_points['available_points']} → {after_points['available_points']}")
        
        # Show error message for failed requests
        if not result["success"] and result.get("error"):
            try:
                error_detail = json.loads(result["error"]).get("detail", "")
                print(f"   📝 Error: {error_detail[:100]}{'...' if len(error_detail) > 100 else ''}")
            except:
                print(f"   📝 Error: {result['error'][:100]}{'...' if len(result['error']) > 100 else ''}")

def test_privileged_user_exemption():
    """Test that privileged users are exempt from point deductions"""
    print("\n🔓 Testing Privileged User Point Exemption")
    print("-" * 50)
    
    for user_type in ["superuser", "admin"]:
        print(f"\n👤 Testing {user_type.upper()} USER")
        
        token = get_auth_token(
            TEST_USERS[user_type]["username"], 
            TEST_USERS[user_type]["password"]
        )
        
        if not token:
            print(f"   ❌ Skipping {user_type} - authentication failed")
            continue
        
        # Get initial points
        initial_points = get_user_points(token)
        if not initial_points:
            print(f"   ❌ Cannot get initial points for {user_type}")
            continue
        
        print(f"   💰 Initial Points: {initial_points['available_points']}")
        
        # Test successful request
        result = test_get_hotel_by_ittid(token, TEST_CASES["valid_accessible"])
        
        # Get points after request
        after_points = get_user_points(token)
        if not after_points:
            print(f"   ❌ Cannot get points after request for {user_type}")
            continue
        
        points_change = initial_points["available_points"] - after_points["available_points"]
        
        if result["success"]:
            print(f"   ✅ Request successful")
            if points_change == 0:
                print(f"   ✅ No points deducted (exempt as expected)")
                print(f"   💰 Points: {initial_points['available_points']} (unchanged)")
            else:
                print(f"   ❌ UNEXPECTED: {points_change} points deducted for privileged user!")
        else:
            print(f"   ❌ Request failed: {result['status_code']}")

def test_error_response_format():
    """Test that error responses have the expected format"""
    print("\n📋 Testing Error Response Format")
    print("-" * 40)
    
    general_token = get_auth_token(
        TEST_USERS["general"]["username"], 
        TEST_USERS["general"]["password"]
    )
    
    if not general_token:
        print("❌ Cannot get general user token")
        return
    
    # Test different error scenarios
    error_tests = [
        {
            "name": "Hotel Not Found",
            "ittid": TEST_CASES["invalid_ittid"],
            "expected_status": 404
        },
        {
            "name": "No Active Suppliers",
            "ittid": TEST_CASES["valid_no_suppliers"],
            "expected_status": 404
        },
        {
            "name": "No User Access",
            "ittid": TEST_CASES["valid_no_access"],
            "expected_status": 403
        }
    ]
    
    for test in error_tests:
        print(f"\n🧪 {test['name']}")
        result = test_get_hotel_by_ittid(general_token, test["ittid"])
        
        if result["status_code"] == test["expected_status"]:
            print(f"   ✅ Status: {result['status_code']}")
            
            if result.get("error"):
                try:
                    error_data = json.loads(result["error"])
                    if "detail" in error_data:
                        print(f"   ✅ Error format: Standard FastAPI format")
                        print(f"   📝 Message: {error_data['detail'][:80]}...")
                    else:
                        print(f"   ⚠️  Error format: Non-standard format")
                except:
                    print(f"   ⚠️  Error format: Could not parse JSON")
        else:
            print(f"   ❌ Unexpected status: {result['status_code']}")

def main():
    """Run all tests"""
    print("💸 POINT DEDUCTION ON SUCCESS ONLY - TESTS")
    print("=" * 80)
    print("Testing that points are ONLY deducted when requests are successful")
    print("and NOT deducted when requests fail due to various errors")
    print("=" * 80)
    
    test_point_deduction_on_success_only()
    test_privileged_user_exemption()
    test_error_response_format()
    
    print("\n" + "=" * 80)
    print("🎯 POINT DEDUCTION TEST SUMMARY")
    print("=" * 80)
    print("✅ Successful requests (200): Points deducted for general users")
    print("❌ Failed requests (4xx/5xx): NO points deducted for any user")
    print("🔓 Privileged users: NO points deducted regardless of success/failure")
    print("📋 Error responses: Proper format with clear messages")
    print("\nKey Principles:")
    print("• Points are only deducted when users successfully receive data")
    print("• Failed requests (errors) should never deduct points")
    print("• Privileged users are always exempt from point deductions")
    print("• Error messages provide clear guidance for resolution")

if __name__ == "__main__":
    main()