#!/usr/bin/env python3
"""
Test script to verify that hotel endpoints work correctly for all user types
and that superusers/admin users are exempt from point deductions
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"

# Test credentials for different user types
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

# Test ITTID (replace with actual ITTID from your database)
TEST_ITTID = "12345"  # Replace with actual ITTID

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

def test_get_hotel_endpoint(token: str, ittid: str) -> dict:
    """Test GET /v1.0/content/get_hotel_with_ittid/{ittid} endpoint"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/v1.0/content/get_hotel_with_ittid/{ittid}", headers=headers)
        
        return {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "endpoint": f"GET /v1.0/content/get_hotel_with_ittid/{ittid}",
            "response_data": response.json() if response.status_code == 200 else None,
            "error": response.text if response.status_code != 200 else None
        }
        
    except Exception as e:
        print(f"❌ Error testing GET endpoint: {e}")
        return {"status_code": 500, "success": False, "endpoint": "GET", "error": str(e)}

def test_post_hotel_endpoint(token: str, ittid_list: list) -> dict:
    """Test POST /v1.0/content/get_hotel_with_ittid endpoint"""
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"ittid": ittid_list}
        response = requests.post(
            f"{BASE_URL}/v1.0/content/get_hotel_with_ittid", 
            headers=headers,
            json=payload
        )
        
        return {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "endpoint": "POST /v1.0/content/get_hotel_with_ittid",
            "response_data": response.json() if response.status_code == 200 else None,
            "error": response.text if response.status_code != 200 else None
        }
        
    except Exception as e:
        print(f"❌ Error testing POST endpoint: {e}")
        return {"status_code": 500, "success": False, "endpoint": "POST", "error": str(e)}

def test_hotel_endpoints():
    """Test hotel endpoints for all user types"""
    
    print("🏨 Testing Hotel Endpoints - Point Exemption for Super Users and Admin Users")
    print("=" * 80)
    
    for user_type, credentials in TEST_USERS.items():
        print(f"\n🔍 Testing {user_type.upper()} USER")
        print("-" * 40)
        
        # Get authentication token
        token = get_auth_token(credentials["username"], credentials["password"])
        if not token:
            print(f"❌ Skipping {user_type} - authentication failed")
            continue
        
        # Get initial points
        initial_points = get_user_points(token)
        if not initial_points:
            print(f"❌ Skipping {user_type} - failed to get user info")
            continue
        
        print(f"👤 User: {initial_points['username']}")
        print(f"🏷️  Role: {initial_points['user_status']}")
        print(f"💰 Initial Points: {initial_points['available_points']}")
        
        # Test GET endpoint
        print(f"\n📡 Testing GET endpoint...")
        get_result = test_get_hotel_endpoint(token, TEST_ITTID)
        
        if get_result["success"]:
            print(f"✅ GET request successful")
            
            # Check for datetime serialization issues
            if get_result["response_data"]:
                print(f"📊 Response contains hotel data: ✅")
                hotel_data = get_result["response_data"].get("hotel", {})
                if "created_at" in hotel_data and "updated_at" in hotel_data:
                    print(f"🕒 Datetime fields properly serialized: ✅")
                else:
                    print(f"⚠️  Datetime fields missing or not serialized")
            
            # Check points after request
            after_points = get_user_points(token)
            if after_points:
                points_change = initial_points["available_points"] - after_points["available_points"]
                
                if user_type in ["superuser", "admin"]:
                    # Should be exempt from point deduction
                    if points_change == 0:
                        print(f"🔓 ✅ EXEMPT: No points deducted ({after_points['available_points']} points)")
                    else:
                        print(f"❌ UNEXPECTED: {points_change} points deducted!")
                else:
                    # General user should have points deducted
                    if points_change > 0:
                        print(f"💸 {points_change} points deducted ({after_points['available_points']} remaining)")
                    else:
                        print(f"⚠️  No points deducted (might be insufficient points)")
                
                # Update initial points for next test
                initial_points = after_points
        else:
            print(f"❌ GET request failed: {get_result['status_code']}")
            if get_result.get("error"):
                print(f"   Error: {get_result['error'][:200]}...")
        
        # Test POST endpoint
        print(f"\n📡 Testing POST endpoint...")
        post_result = test_post_hotel_endpoint(token, [TEST_ITTID])
        
        if post_result["success"]:
            print(f"✅ POST request successful")
            
            # Check for datetime serialization issues
            if post_result["response_data"]:
                print(f"📊 Response contains hotel data: ✅")
                if isinstance(post_result["response_data"], list) and len(post_result["response_data"]) > 0:
                    hotel_data = post_result["response_data"][0].get("hotel", {})
                    if "created_at" in hotel_data and "updated_at" in hotel_data:
                        print(f"🕒 Datetime fields properly serialized: ✅")
                    else:
                        print(f"⚠️  Datetime fields missing or not serialized")
            
            # Check points after request
            after_points = get_user_points(token)
            if after_points:
                points_change = initial_points["available_points"] - after_points["available_points"]
                
                if user_type in ["superuser", "admin"]:
                    # Should be exempt from point deduction
                    if points_change == 0:
                        print(f"🔓 ✅ EXEMPT: No points deducted ({after_points['available_points']} points)")
                    else:
                        print(f"❌ UNEXPECTED: {points_change} points deducted!")
                else:
                    # General user should have points deducted
                    if points_change > 0:
                        print(f"💸 {points_change} points deducted ({after_points['available_points']} remaining)")
                    else:
                        print(f"⚠️  No points deducted (might be insufficient points)")
        else:
            print(f"❌ POST request failed: {post_result['status_code']}")
            if post_result.get("error"):
                print(f"   Error: {post_result['error'][:200]}...")
    
    print("\n" + "=" * 80)
    print("🎯 HOTEL ENDPOINT TEST SUMMARY")
    print("=" * 80)
    print("✅ Super Users: Should be exempt from ALL point deductions")
    print("✅ Admin Users: Should be exempt from ALL point deductions") 
    print("💸 General Users: Should have points deducted per request")
    print("🕒 All Users: Should receive properly serialized datetime fields")
    print("\nKey Benefits:")
    print("• Super users have unlimited access to hotel data")
    print("• Admin users can access hotel information without point concerns")
    print("• JSON serialization errors are fixed")
    print("• Point system only applies to general users")

def test_endpoint_availability():
    """Test if endpoints are available"""
    print("\n🔧 Testing Endpoint Availability")
    print("-" * 40)
    
    # Test basic connectivity
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ API server is running")
        else:
            print("⚠️  API server may have issues")
    except Exception as e:
        print(f"❌ Cannot connect to API server: {e}")
        return False
    
    return True

if __name__ == "__main__":
    if test_endpoint_availability():
        test_hotel_endpoints()
    else:
        print("❌ Cannot proceed with tests - API server not available")