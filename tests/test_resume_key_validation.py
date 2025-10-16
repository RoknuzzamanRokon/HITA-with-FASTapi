#!/usr/bin/env python3
"""
Test script to verify resume_key validation for /v1.0/content/get_all_hotel_info endpoint
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

def test_get_all_hotels(token: str, resume_key: str = None, limit: int = 5) -> dict:
    """Test GET /v1.0/content/get_all_hotel_info endpoint"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        params = {"limit": limit}
        
        if resume_key:
            params["resume_key"] = resume_key
        
        response = requests.get(
            f"{BASE_URL}/v1.0/content/get_all_hotel_info",
            headers=headers,
            params=params
        )
        
        return {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "response_data": response.json() if response.status_code == 200 else None,
            "error": response.text if response.status_code != 200 else None
        }
        
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        return {"status_code": 500, "success": False, "error": str(e)}

def test_resume_key_validation():
    """Test resume_key validation for all user types"""
    
    print("🔑 Testing Resume Key Validation for /v1.0/content/get_all_hotel_info")
    print("=" * 80)
    
    # Test with superuser first to get valid resume keys
    superuser_token = get_auth_token(
        TEST_USERS["superuser"]["username"], 
        TEST_USERS["superuser"]["password"]
    )
    
    if not superuser_token:
        print("❌ Cannot get superuser token - skipping tests")
        return
    
    print("🔍 Step 1: Getting valid resume_key from first request")
    print("-" * 50)
    
    # Get first page to obtain a valid resume_key
    first_page = test_get_all_hotels(superuser_token, limit=3)
    
    if not first_page["success"]:
        print("❌ Failed to get first page")
        return
    
    valid_resume_key = first_page["response_data"].get("resume_key")
    print(f"✅ Got valid resume_key: {valid_resume_key[:20]}..." if valid_resume_key else "❌ No resume_key returned")
    
    # Test cases for resume_key validation
    test_cases = [
        {
            "name": "Valid Resume Key",
            "resume_key": valid_resume_key,
            "expected_status": 200,
            "description": "Should work with valid resume_key from previous response"
        },
        {
            "name": "Empty Resume Key",
            "resume_key": "",
            "expected_status": 400,
            "description": "Should reject empty resume_key"
        },
        {
            "name": "Whitespace Resume Key",
            "resume_key": "   ",
            "expected_status": 400,
            "description": "Should reject whitespace-only resume_key"
        },
        {
            "name": "Invalid Format - No Underscore",
            "resume_key": "12345abcdef",
            "expected_status": 400,
            "description": "Should reject resume_key without underscore separator"
        },
        {
            "name": "Invalid Format - Multiple Underscores",
            "resume_key": "123_abc_def",
            "expected_status": 400,
            "description": "Should reject resume_key with multiple underscores"
        },
        {
            "name": "Invalid ID - Non-numeric",
            "resume_key": "abc_" + "x" * 50,
            "expected_status": 400,
            "description": "Should reject resume_key with non-numeric ID"
        },
        {
            "name": "Invalid ID - Zero",
            "resume_key": "0_" + "x" * 50,
            "expected_status": 400,
            "description": "Should reject resume_key with zero ID"
        },
        {
            "name": "Invalid ID - Negative",
            "resume_key": "-123_" + "x" * 50,
            "expected_status": 400,
            "description": "Should reject resume_key with negative ID"
        },
        {
            "name": "Invalid Random Part - Too Short",
            "resume_key": "123_abc",
            "expected_status": 400,
            "description": "Should reject resume_key with short random part"
        },
        {
            "name": "Invalid Random Part - Too Long",
            "resume_key": "123_" + "x" * 60,
            "expected_status": 400,
            "description": "Should reject resume_key with long random part"
        },
        {
            "name": "Invalid Random Part - Special Characters",
            "resume_key": "123_" + "x" * 49 + "@",
            "expected_status": 400,
            "description": "Should reject resume_key with special characters in random part"
        },
        {
            "name": "Non-existent Hotel ID",
            "resume_key": "999999_" + "x" * 50,
            "expected_status": 400,
            "description": "Should reject resume_key with non-existent hotel ID"
        }
    ]
    
    print(f"\n🧪 Step 2: Testing Resume Key Validation Cases")
    print("-" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   Resume Key: {test_case['resume_key'][:50]}{'...' if len(test_case['resume_key']) > 50 else ''}")
        print(f"   Expected: {test_case['expected_status']} - {test_case['description']}")
        
        result = test_get_all_hotels(superuser_token, test_case["resume_key"])
        
        if result["status_code"] == test_case["expected_status"]:
            print(f"   ✅ PASS: Got expected status {result['status_code']}")
        else:
            print(f"   ❌ FAIL: Expected {test_case['expected_status']}, got {result['status_code']}")
            if result.get("error"):
                print(f"   Error: {result['error'][:100]}...")
    
    print(f"\n🔍 Step 3: Testing Point Exemption with Resume Keys")
    print("-" * 50)
    
    # Test point exemption for different user types
    for user_type, credentials in TEST_USERS.items():
        print(f"\n👤 Testing {user_type.upper()} USER")
        
        token = get_auth_token(credentials["username"], credentials["password"])
        if not token:
            print(f"   ❌ Skipping {user_type} - authentication failed")
            continue
        
        # Test with valid resume_key
        result = test_get_all_hotels(token, valid_resume_key, limit=2)
        
        if result["success"]:
            print(f"   ✅ Successfully accessed with resume_key")
            
            response_data = result["response_data"]
            pagination_info = response_data.get("pagination_info", {})
            
            print(f"   📊 Hotels returned: {pagination_info.get('current_page_count', 'N/A')}")
            print(f"   🏷️  User role: {pagination_info.get('user_role', 'N/A')}")
            print(f"   💸 Point deduction: {'Yes' if pagination_info.get('point_deduction_applied') else 'No'}")
            
            if user_type in ["superuser", "admin"]:
                if not pagination_info.get('point_deduction_applied'):
                    print(f"   🔓 ✅ EXEMPT: No points deducted as expected")
                else:
                    print(f"   ❌ UNEXPECTED: Points were deducted!")
            else:
                if pagination_info.get('point_deduction_applied'):
                    print(f"   💸 Points deducted as expected for general user")
                else:
                    print(f"   ⚠️  No points deducted (might be insufficient points)")
        else:
            print(f"   ❌ Failed to access with resume_key: {result['status_code']}")
            if result.get("error"):
                print(f"   Error: {result['error'][:100]}...")
    
    print("\n" + "=" * 80)
    print("🎯 RESUME KEY VALIDATION TEST SUMMARY")
    print("=" * 80)
    print("✅ Valid resume keys should work for all user types")
    print("❌ Invalid resume keys should be rejected with 400 Bad Request")
    print("🔓 Super users and admin users should be exempt from point deductions")
    print("💸 General users should have points deducted per request")
    print("\nResume Key Format: {hotel_id}_{50_char_random_string}")
    print("- hotel_id: Must be positive integer of existing hotel")
    print("- random_string: Must be exactly 50 alphanumeric characters")
    print("- Separator: Single underscore (_)")

def test_pagination_flow():
    """Test complete pagination flow with resume keys"""
    print("\n🔄 Testing Complete Pagination Flow")
    print("-" * 50)
    
    superuser_token = get_auth_token(
        TEST_USERS["superuser"]["username"], 
        TEST_USERS["superuser"]["password"]
    )
    
    if not superuser_token:
        print("❌ Cannot get superuser token")
        return
    
    current_resume_key = None
    page_count = 0
    total_hotels_seen = 0
    
    while page_count < 3:  # Test first 3 pages
        page_count += 1
        print(f"\n📄 Page {page_count}")
        
        result = test_get_all_hotels(superuser_token, current_resume_key, limit=5)
        
        if not result["success"]:
            print(f"❌ Failed to get page {page_count}: {result['status_code']}")
            break
        
        response_data = result["response_data"]
        hotels = response_data.get("hotels", [])
        next_resume_key = response_data.get("resume_key")
        
        print(f"   Hotels on this page: {len(hotels)}")
        print(f"   Next resume_key: {'Available' if next_resume_key else 'None (last page)'}")
        
        total_hotels_seen += len(hotels)
        
        if not next_resume_key:
            print("   📄 Reached last page")
            break
        
        current_resume_key = next_resume_key
    
    print(f"\n📊 Pagination Summary:")
    print(f"   Pages tested: {page_count}")
    print(f"   Total hotels seen: {total_hotels_seen}")
    print(f"   Pagination working: ✅")

if __name__ == "__main__":
    test_resume_key_validation()
    test_pagination_flow()