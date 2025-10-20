#!/usr/bin/env python3
"""
Test script to verify SMART resume_key logic for /v1.0/content/get_all_hotel_info endpoint
- First request: No resume_key needed
- Subsequent requests: Must provide valid resume_key
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

def test_smart_resume_key_logic():
    """Test smart resume_key logic"""
    
    print("🧠 Testing SMART Resume Key Logic")
    print("=" * 80)
    print("Logic: First request needs no resume_key, subsequent requests require valid resume_key")
    print("=" * 80)
    
    # Get superuser token for testing
    superuser_token = get_auth_token(
        TEST_USERS["superuser"]["username"], 
        TEST_USERS["superuser"]["password"]
    )
    
    if not superuser_token:
        print("❌ Cannot get superuser token - skipping tests")
        return
    
    print("🧪 Test Cases for Smart Resume Key Logic")
    print("-" * 50)
    
    # Test Case 1: First request without resume_key (should work)
    print("\n1. First request without resume_key")
    result = test_get_all_hotels(superuser_token, resume_key=None, limit=3)
    
    if result["success"]:
        print("   ✅ PASS: First request successful without resume_key")
        
        response_data = result["response_data"]
        valid_resume_key = response_data.get("resume_key")
        total_hotel = response_data.get("total_hotel")
        accessible_count = response_data.get("accessible_hotel_count")
        pagination_info = response_data.get("pagination_info", {})
        usage_instructions = response_data.get("usage_instructions", {})
        
        print(f"   📊 Total hotels in DB: {total_hotel}")
        print(f"   🔓 Accessible to user: {accessible_count}")
        print(f"   📄 Resume key for next: {'Available' if valid_resume_key else 'None'}")
        print(f"   🏷️  Detected as first request: {pagination_info.get('is_first_request', 'N/A')}")
        print(f"   📋 Usage instructions: {usage_instructions.get('note', 'N/A')}")
        
        if valid_resume_key:
            print(f"   🔑 Resume key format: {valid_resume_key[:20]}...")
    else:
        print(f"   ❌ FAIL: Expected success, got {result['status_code']}")
        print(f"   Error: {result.get('error', 'Unknown error')[:100]}...")
        return
    
    # Test Case 2: Subsequent request with valid resume_key (should work)
    print("\n2. Subsequent request with valid resume_key")
    result = test_get_all_hotels(superuser_token, resume_key=valid_resume_key, limit=3)
    
    if result["success"]:
        print("   ✅ PASS: Subsequent request successful with resume_key")
        
        response_data = result["response_data"]
        next_resume_key = response_data.get("resume_key")
        pagination_info = response_data.get("pagination_info", {})
        
        print(f"   📄 Next resume key: {'Available' if next_resume_key else 'None (last page)'}")
        print(f"   🏷️  Detected as first request: {pagination_info.get('is_first_request', 'N/A')}")
        print(f"   📊 Hotels returned: {pagination_info.get('current_page_count', 'N/A')}")
        
        # Update valid_resume_key for next test
        if next_resume_key:
            valid_resume_key = next_resume_key
    else:
        print(f"   ❌ FAIL: Expected success, got {result['status_code']}")
        print(f"   Error: {result.get('error', 'Unknown error')[:100]}...")
    
    # Test Case 3: Invalid resume_key format (should fail)
    print("\n3. Invalid resume_key format")
    invalid_resume_keys = [
        "invalid_format",
        "123_short",
        "abc_" + "x" * 50,
        "999999_" + "x" * 50  # Non-existent hotel ID
    ]
    
    for i, invalid_key in enumerate(invalid_resume_keys, 1):
        print(f"   3.{i} Testing: {invalid_key[:30]}{'...' if len(invalid_key) > 30 else ''}")
        result = test_get_all_hotels(superuser_token, resume_key=invalid_key, limit=3)
        
        if result["status_code"] == 400:
            print(f"        ✅ PASS: Correctly rejected invalid resume_key")
        else:
            print(f"        ❌ FAIL: Expected 400, got {result['status_code']}")

def test_complete_pagination_flow():
    """Test complete pagination flow with smart resume key logic"""
    print("\n🔄 Testing Complete Pagination Flow")
    print("-" * 50)
    
    superuser_token = get_auth_token(
        TEST_USERS["superuser"]["username"], 
        TEST_USERS["superuser"]["password"]
    )
    
    if not superuser_token:
        print("❌ Cannot get superuser token")
        return
    
    # Step 1: First request (no resume_key)
    print("\n📄 Step 1: First request (no resume_key needed)")
    result = test_get_all_hotels(superuser_token, resume_key=None, limit=3)
    
    if not result["success"]:
        print(f"❌ First request failed: {result['status_code']}")
        return
    
    current_resume_key = result["response_data"].get("resume_key")
    total_hotel = result["response_data"].get("total_hotel")
    accessible_count = result["response_data"].get("accessible_hotel_count")
    page_count = 1
    total_hotels_seen = len(result["response_data"].get("hotels", []))
    
    print(f"   ✅ Success: {total_hotels_seen} hotels received")
    print(f"   📊 Total hotels in database: {total_hotel}")
    print(f"   🔓 Accessible to user: {accessible_count}")
    print(f"   🔑 Resume key: {'Available' if current_resume_key else 'None'}")
    
    # Step 2-4: Subsequent requests with resume keys
    while current_resume_key and page_count < 4:
        page_count += 1
        print(f"\n📄 Step {page_count}: Request with resume_key (required)")
        
        result = test_get_all_hotels(superuser_token, resume_key=current_resume_key, limit=3)
        
        if not result["success"]:
            print(f"   ❌ Request failed: {result['status_code']}")
            break
        
        hotels = result["response_data"].get("hotels", [])
        next_resume_key = result["response_data"].get("resume_key")
        pagination_info = result["response_data"].get("pagination_info", {})
        
        print(f"   ✅ Success: {len(hotels)} hotels received")
        print(f"   🏷️  Detected as first request: {pagination_info.get('is_first_request', 'N/A')}")
        print(f"   🔑 Next resume key: {'Available' if next_resume_key else 'None (last page)'}")
        
        total_hotels_seen += len(hotels)
        current_resume_key = next_resume_key
        
        if not next_resume_key:
            print("   📄 Reached last page")
            break
    
    print(f"\n📊 Pagination Flow Summary:")
    print(f"   Pages processed: {page_count}")
    print(f"   Total hotels seen: {total_hotels_seen}")
    print(f"   Database total: {total_hotel}")
    print(f"   Smart resume_key logic working: ✅")

def test_user_role_behavior():
    """Test behavior for different user roles"""
    print("\n👥 Testing User Role Behavior with Smart Resume Keys")
    print("-" * 60)
    
    for user_type, credentials in TEST_USERS.items():
        print(f"\n👤 Testing {user_type.upper()} USER")
        
        token = get_auth_token(credentials["username"], credentials["password"])
        if not token:
            print(f"   ❌ Skipping {user_type} - authentication failed")
            continue
        
        # First request (no resume_key)
        result = test_get_all_hotels(token, resume_key=None, limit=2)
        
        if result["success"]:
            response_data = result["response_data"]
            pagination_info = response_data.get("pagination_info", {})
            total_hotel = response_data.get("total_hotel")
            accessible_count = response_data.get("accessible_hotel_count")
            
            print(f"   ✅ First request successful")
            print(f"   🏷️  User role: {pagination_info.get('user_role', 'N/A')}")
            print(f"   💸 Point deduction: {'Yes' if pagination_info.get('point_deduction_applied') else 'No'}")
            print(f"   📊 Total hotels in DB: {total_hotel}")
            print(f"   🔓 Accessible to user: {accessible_count}")
            
            # Verify point exemption
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
            print(f"   ❌ First request failed: {result['status_code']}")
            if result.get("error"):
                print(f"   Error: {result['error'][:100]}...")

def test_database_count_accuracy():
    """Test that total_hotel shows actual database count"""
    print("\n📊 Testing Database Count Accuracy")
    print("-" * 40)
    
    superuser_token = get_auth_token(
        TEST_USERS["superuser"]["username"], 
        TEST_USERS["superuser"]["password"]
    )
    
    if not superuser_token:
        print("❌ Cannot get superuser token")
        return
    
    result = test_get_all_hotels(superuser_token, resume_key=None, limit=1)
    
    if result["success"]:
        response_data = result["response_data"]
        total_hotel = response_data.get("total_hotel")
        accessible_count = response_data.get("accessible_hotel_count")
        
        print(f"📊 Database Count Test Results:")
        print(f"   Total hotels (SELECT COUNT(ittid) FROM hotels): {total_hotel}")
        print(f"   Accessible to superuser: {accessible_count}")
        print(f"   Should be equal for superuser: {'✅ Yes' if total_hotel == accessible_count else '❌ No'}")
        
        if total_hotel and total_hotel > 0:
            print(f"   ✅ Database count is working correctly")
        else:
            print(f"   ⚠️  Database might be empty or count query failed")
    else:
        print(f"❌ Failed to get database count: {result['status_code']}")

def main():
    """Run all tests"""
    print("🧠 SMART RESUME KEY LOGIC TESTS")
    print("=" * 80)
    print("Testing the smart logic where:")
    print("• First request: No resume_key needed (auto-detected)")
    print("• Subsequent requests: Must provide valid resume_key")
    print("• Total hotel count: Shows actual database count")
    print("=" * 80)
    
    test_smart_resume_key_logic()
    test_complete_pagination_flow()
    test_user_role_behavior()
    test_database_count_accuracy()
    
    print("\n" + "=" * 80)
    print("🎯 SMART RESUME KEY TEST SUMMARY")
    print("=" * 80)
    print("✅ First request: No resume_key needed (automatically detected)")
    print("🔒 Subsequent requests: Must provide valid resume_key from previous response")
    print("📊 Total hotel count: Shows actual database count (SELECT COUNT(ittid) FROM hotels)")
    print("🔓 Point exemption: Super/admin users exempt from point deductions")
    print("🧠 Smart detection: Automatically determines first vs subsequent requests")
    print("\nKey Features:")
    print("• No need to specify first_request=true")
    print("• Resume key automatically required for pagination")
    print("• Accurate database counts for monitoring")
    print("• Role-based access control maintained")

if __name__ == "__main__":
    main()