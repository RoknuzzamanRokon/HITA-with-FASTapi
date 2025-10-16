#!/usr/bin/env python3
"""
Test script to verify that superusers and admin users are exempt from point deductions
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

def test_endpoint_with_point_deduction(token: str, endpoint: str) -> dict:
    """Test an endpoint that normally deducts points"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
        
        return {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "endpoint": endpoint
        }
        
    except Exception as e:
        print(f"❌ Error testing endpoint {endpoint}: {e}")
        return {"status_code": 500, "success": False, "endpoint": endpoint}

def test_point_exemption():
    """Test point exemption for different user types"""
    
    print("🧪 Testing Point Exemption for Super Users and Admin Users")
    print("=" * 60)
    
    # Endpoints that normally deduct points for general users
    test_endpoints = [
        "/v1.0/contents/hotels",
        "/v1.0/contents/hotels/details/me",
        "/v1.0/contents/hotels/search"
    ]
    
    for user_type, credentials in TEST_USERS.items():
        print(f"\n🔍 Testing {user_type.upper()} USER")
        print("-" * 30)
        
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
        
        # Test endpoints that should deduct points
        for endpoint in test_endpoints:
            print(f"\n📡 Testing endpoint: {endpoint}")
            
            # Make request
            result = test_endpoint_with_point_deduction(token, endpoint)
            
            if result["success"]:
                print(f"✅ Request successful")
                
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
                    print("❌ Failed to check points after request")
            else:
                print(f"❌ Request failed: {result['status_code']}")
    
    print("\n" + "=" * 60)
    print("🎯 POINT EXEMPTION TEST SUMMARY")
    print("=" * 60)
    print("✅ Super Users: Should be exempt from ALL point deductions")
    print("✅ Admin Users: Should be exempt from ALL point deductions") 
    print("💸 General Users: Should have points deducted per request")
    print("\nKey Benefits:")
    print("• Super users have unlimited access without point concerns")
    print("• Admin users can manage system without point limitations")
    print("• Point system only applies to general users")

def test_point_service_exemption():
    """Test point service exemption logic"""
    print("\n🔧 Testing Point Service Exemption Logic")
    print("-" * 40)
    
    # This would require direct database access or a special test endpoint
    # For now, we'll just document the expected behavior
    
    print("📋 Point Service Exemption Rules:")
    print("1. deduct_points() checks user role before deduction")
    print("2. Super users and admin users return True without deduction")
    print("3. Only general users have actual point deductions")
    print("4. Transaction logs reflect exemption status")

if __name__ == "__main__":
    test_point_exemption()
    test_point_service_exemption()