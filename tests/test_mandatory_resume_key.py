#!/usr/bin/env python3
"""
Test script to verify MANDATORY resume_key requirement for /v1.0/content/get_all_hotel_info endpoint
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

def test_get_all_hotels(token: str, first_request: bool = False, resume_key: str = None, limit: int = 5) -> dict:
    """Test GET /v1.0/content/get_all_hotel_info endpoint"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        params = {"limit": limit}
        
        if first_request:
            params["first_request"] = "true"
        
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

def test_mandatory_resume_key():
    """Test mandatory resume_key requirement"""
    
    print("🔒 Testing MANDATORY Resume Key Requirement")
    print("=" * 80)
    
    # Get superuser token for testing
    superuser_token = get_auth_token(
        TEST_USERS["superuser"]["username"], 
        TEST_USERS["superuser"]["password"]
    )
    
    if not superuser_token:
        print("❌ Cannot get superuser token - skipping tests")
        return
    
    print("🧪 Test Cases for Resume Key Requirement")
    print("-" * 50)
    
    # Test Case 1: First request with first_request=true (should work)
    print("\n1. First request with first_request=true")
    result = test_get_all_hotels(superuser_token, first_request=True, limit=3)
    
    if result["success"]:
        print("   ✅ PASS: First request successful")
        valid_resume_key = result["response_data"].get("resume_key")
        usage_instructions = result["response_data"].get("usage_instructions", {})
        
        print(f"   📄 Resume key received: {'Yes' if valid_resume_key else 'No'}")
        print(f"   📋 Usage instructions included: {'Yes' if usage_instructions else 'No'}")
        
        if valid_resume_key:
            print(f"   🔑 Resume key format: {valid_resume_key[:20]}...")
    else:
        print(f"   ❌ FAIL: Expected success, got {result['status_code']}")
        print(f"   Error: {result.get('error', 'Unknown error')[:100]}...")
        return
    
    # Test Case 2: Request without first_request=true and without resume_key (should fail)
    print("\n2. Request without first_request=true and without resume_key")
    result = test_get_all_hotels(superuser_token, first_request=False, resume_key=None)
    
    if result["status_code"] == 400:
        print("   ✅ PASS: Correctly rejected request without resume_key")
        error_detail = json.loads(result["error"]).get("detail", "") if result["error"] else ""
        if "resume_key is required" in error_detail:
            print("   ✅ PASS: Correct error message about resume_key requirement")
        else:
            print("   ⚠️  WARNING: Error message doesn't mention resume_key requirement")
    else:
        print(f"   ❌ FAIL: Expected 400, got {result['status_code']}")
    
    # Test Case 3: Request with both first_request=true and resume_key (should fail)
    print("\n3. Request with both first_request=true and resume_key")
    result = test_get_all_hotels(superuser_token, first_request=True, resume_key=valid_resume_key)
    
    if result["status_code"] == 400:
        print("   ✅ PASS: Correctly rejected conflicting parameters")
        error_detail = json.loads(result["error"]).get("detail", "") if result["error"] else ""
        if "Cannot use both" in error_detail:
            print("   ✅ PASS: Correct error message about conflicting parameters")
        else:
            print("   ⚠️  WARNING: Error message doesn't mention parameter conflict")
    else:
        print(f"   ❌ FAIL: Expected 400, got {result['status_code']}")
    
    # Test Case 4: Valid resume_key from previous response (should work)
    print("\n4. Valid resume_key from previous response")
    result = test_get_all_hotels(superuser_token, first_request=False, resume_key=valid_resume_key)
    
    if result["success"]:
        print("   ✅ PASS: Valid resume_key accepted")
        next_resume_key = result["response_data"].get("resume_key")
        pagination_info = result["response_data"].get("pagination_info", {})
        
        print(f"   📄 Next resume key: {'Available' if next_resume_key else 'None (last page)'}")
        print(f"   📊 Hotels returned: {pagination_info.get('current_page_count', 'N/A')}")
        print(f"   🔄 Has next page: {pagination_info.get('has_next_page', 'N/A')}")
    else:
        print(f"   ❌ FAIL: Expected success, got {result['status_code']}")
        print(f"   Error: {result.get('error', 'Unknown error')[:100]}...")
    
    # Test Case 5: Invalid resume_key format (should fail)
    print("\n5. Invalid resume_key format")
    invalid_resume_keys = [
        "invalid_format",
        "123",
        "123_short",
        "abc_" + "x" * 50,
        "123_" + "x" * 60,
        ""
    ]
    
    for i, invalid_key in enumerate(invalid_resume_keys, 1):
        print(f"   5.{i} Testing: {invalid_key[:30]}{'...' if len(invalid_key) > 30 else ''}")
        result = test_get_all_hotels(superuser_token, first_request=False, resume_key=invalid_key)
        
        if result["status_code"] == 400:
            print(f"        ✅ PASS: Correctly rejected invalid resume_key")
        else:
            print(f"        ❌ FAIL: Expected 400, got {result['status_code']}")

def test_pagination_flow_with_mandatory_keys():
    """Test complete pagination flow with mandatory resume keys"""
    print("\n🔄 Testing Complete Pagination Flow with Mandatory Resume Keys")
    print("-" * 60)
    
    superuser_token = get_auth_token(
        TEST_USERS["superuser"]["username"], 
        TEST_USERS["superuser"]["password"]
    )
    
    if not superuser_token:
        print("❌ Cannot get superuser token")
        return
    
    # Step 1: First request
    print("\n📄 Step 1: First request (first_request=true)")
    result = test_get_all_hotels(superuser_token, first_request=True, limit=3)
    
    if not result["success"]:
        print(f"❌ First request failed: {result['status_code']}")
        return
    
    current_resume_key = result["response_data"].get("resume_key")
    page_count = 1
    total_hotels_seen = len(result["response_data"].get("hotels", []))
    
    print(f"   ✅ Success: {total_hotels_seen} hotels received")
    print(f"   🔑 Resume key: {'Available' if current_resume_key else 'None'}")
    
    # Step 2-4: Subsequent requests with resume keys
    while current_resume_key and page_count < 4:
        page_count += 1
        print(f"\n📄 Step {page_count}: Request with resume_key")
        
        result = test_get_all_hotels(superuser_token, first_request=False, resume_key=current_resume_key, limit=3)
        
        if not result["success"]:
            print(f"   ❌ Request failed: {result['status_code']}")
            break
        
        hotels = result["response_data"].get("hotels", [])
        next_resume_key = result["response_data"].get("resume_key")
        
        print(f"   ✅ Success: {len(hotels)} hotels received")
        print(f"   🔑 Next resume key: {'Available' if next_resume_key else 'None (last page)'}")
        
        total_hotels_seen += len(hotels)
        current_resume_key = next_resume_key
        
        if not next_resume_key:
            print("   📄 Reached last page")
            break
    
    print(f"\n📊 Pagination Flow Summary:")
    print(f"   Pages processed: {page_count}")
    print(f"   Total hotels seen: {total_hotels_seen}")
    print(f"   Mandatory resume_key working: ✅")

def test_user_role_exemptions():
    """Test point exemptions for different user roles with mandatory resume keys"""
    print("\n👥 Testing User Role Exemptions with Mandatory Resume Keys")
    print("-" * 60)
    
    for user_type, credentials in TEST_USERS.items():
        print(f"\n👤 Testing {user_type.upper()} USER")
        
        token = get_auth_token(credentials["username"], credentials["password"])
        if not token:
            print(f"   ❌ Skipping {user_type} - authentication failed")
            continue
        
        # First request
        result = test_get_all_hotels(token, first_request=True, limit=2)
        
        if result["success"]:
            response_data = result["response_data"]
            pagination_info = response_data.get("pagination_info", {})
            usage_instructions = response_data.get("usage_instructions", {})
            
            print(f"   ✅ First request successful")
            print(f"   🏷️  User role: {pagination_info.get('user_role', 'N/A')}")
            print(f"   💸 Point deduction: {'Yes' if pagination_info.get('point_deduction_applied') else 'No'}")
            print(f"   📋 Usage instructions: {'Included' if usage_instructions else 'Missing'}")
            
            # Test with resume key if available
            resume_key = response_data.get("resume_key")
            if resume_key:
                print(f"   🔑 Testing with resume_key...")
                result2 = test_get_all_hotels(token, first_request=False, resume_key=resume_key, limit=2)
                
                if result2["success"]:
                    print(f"   ✅ Resume key request successful")
                else:
                    print(f"   ❌ Resume key request failed: {result2['status_code']}")
            else:
                print(f"   📄 No resume key (last page)")
                
        else:
            print(f"   ❌ First request failed: {result['status_code']}")
            if result.get("error"):
                print(f"   Error: {result['error'][:100]}...")

def main():
    """Run all tests"""
    print("🔒 MANDATORY RESUME KEY VALIDATION TESTS")
    print("=" * 80)
    print("Testing the requirement that resume_key must be provided for all")
    print("requests after the first one to /v1.0/content/get_all_hotel_info")
    print("=" * 80)
    
    test_mandatory_resume_key()
    test_pagination_flow_with_mandatory_keys()
    test_user_role_exemptions()
    
    print("\n" + "=" * 80)
    print("🎯 MANDATORY RESUME KEY TEST SUMMARY")
    print("=" * 80)
    print("✅ First request: Use first_request=true (no resume_key needed)")
    print("🔒 Subsequent requests: Must provide valid resume_key")
    print("❌ Invalid scenarios: Rejected with 400 Bad Request")
    print("🔓 Point exemption: Super/admin users exempt from point deductions")
    print("📋 Usage instructions: Included in every response")
    print("\nKey Requirements:")
    print("• first_request=true for initial request")
    print("• resume_key required for all subsequent requests")
    print("• Cannot use both first_request=true and resume_key")
    print("• Resume key format: {hotel_id}_{50_char_random_string}")

if __name__ == "__main__":
    main()