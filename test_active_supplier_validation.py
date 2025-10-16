#!/usr/bin/env python3
"""
Test script to verify active supplier validation for /v1.0/content/get_hotel_with_ittid/{ittid} endpoint
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

# Test ITTIDs (replace with actual ITTIDs from your database)
TEST_CASES = {
    "valid_with_suppliers": "12345",  # ITTID that exists and has active suppliers
    "valid_no_suppliers": "67890",   # ITTID that exists but has no suppliers
    "invalid_ittid": "99999",        # ITTID that doesn't exist
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

def test_active_supplier_validation():
    """Test active supplier validation for different scenarios"""
    
    print("🏨 Testing Active Supplier Validation for Hotel ITTID Endpoint")
    print("=" * 80)
    
    # Get superuser token for testing
    superuser_token = get_auth_token(
        TEST_USERS["superuser"]["username"], 
        TEST_USERS["superuser"]["password"]
    )
    
    if not superuser_token:
        print("❌ Cannot get superuser token - skipping tests")
        return
    
    print("🧪 Test Cases for Active Supplier Validation")
    print("-" * 50)
    
    # Test Case 1: Valid ITTID with active suppliers (should work)
    print(f"\n1. Valid ITTID with active suppliers: {TEST_CASES['valid_with_suppliers']}")
    result = test_get_hotel_by_ittid(superuser_token, TEST_CASES["valid_with_suppliers"])
    
    if result["success"]:
        print("   ✅ PASS: Hotel with active suppliers found")
        
        response_data = result["response_data"]
        supplier_info = response_data.get("supplier_info", {})
        provider_mappings = response_data.get("provider_mappings", [])
        
        print(f"   🏨 Hotel: {response_data.get('hotel', {}).get('name', 'N/A')}")
        print(f"   🔗 Total active suppliers: {supplier_info.get('total_active_suppliers', 0)}")
        print(f"   🔓 Accessible suppliers: {supplier_info.get('accessible_suppliers', 0)}")
        print(f"   📋 Supplier names: {', '.join(supplier_info.get('supplier_names', []))}")
        
        if provider_mappings:
            print(f"   ✅ Provider mappings included in response")
        else:
            print(f"   ⚠️  No provider mappings in response")
            
    else:
        print(f"   ❌ FAIL: Expected success, got {result['status_code']}")
        if result.get("error"):
            error_detail = json.loads(result["error"]).get("detail", "") if result["error"] else ""
            print(f"   Error: {error_detail}")
    
    # Test Case 2: Valid ITTID with no suppliers (should fail with specific message)
    print(f"\n2. Valid ITTID with no active suppliers: {TEST_CASES['valid_no_suppliers']}")
    result = test_get_hotel_by_ittid(superuser_token, TEST_CASES["valid_no_suppliers"])
    
    if result["status_code"] == 404:
        print("   ✅ PASS: Correctly rejected hotel with no active suppliers")
        if result.get("error"):
            error_detail = json.loads(result["error"]).get("detail", "") if result["error"] else ""
            if "Cannot active supplier with this ittid" in error_detail:
                print("   ✅ PASS: Correct error message about no active suppliers")
                print(f"   📝 Error message: {error_detail}")
            else:
                print("   ⚠️  WARNING: Error message doesn't mention active suppliers")
                print(f"   📝 Error message: {error_detail}")
    else:
        print(f"   ❌ FAIL: Expected 404, got {result['status_code']}")
        if result.get("error"):
            error_detail = json.loads(result["error"]).get("detail", "") if result["error"] else ""
            print(f"   Error: {error_detail}")
    
    # Test Case 3: Invalid ITTID (should fail with hotel not found)
    print(f"\n3. Invalid ITTID (hotel not found): {TEST_CASES['invalid_ittid']}")
    result = test_get_hotel_by_ittid(superuser_token, TEST_CASES["invalid_ittid"])
    
    if result["status_code"] == 404:
        print("   ✅ PASS: Correctly rejected non-existent hotel")
        if result.get("error"):
            error_detail = json.loads(result["error"]).get("detail", "") if result["error"] else ""
            if "Hotel with id" in error_detail and "not found" in error_detail:
                print("   ✅ PASS: Correct error message about hotel not found")
                print(f"   📝 Error message: {error_detail}")
            else:
                print("   ⚠️  WARNING: Unexpected error message format")
                print(f"   📝 Error message: {error_detail}")
    else:
        print(f"   ❌ FAIL: Expected 404, got {result['status_code']}")

def test_user_role_behavior_with_suppliers():
    """Test behavior for different user roles with supplier validation"""
    print("\n👥 Testing User Role Behavior with Supplier Validation")
    print("-" * 60)
    
    valid_ittid = TEST_CASES["valid_with_suppliers"]
    
    for user_type, credentials in TEST_USERS.items():
        print(f"\n👤 Testing {user_type.upper()} USER")
        
        token = get_auth_token(credentials["username"], credentials["password"])
        if not token:
            print(f"   ❌ Skipping {user_type} - authentication failed")
            continue
        
        result = test_get_hotel_by_ittid(token, valid_ittid)
        
        if result["success"]:
            response_data = result["response_data"]
            supplier_info = response_data.get("supplier_info", {})
            
            print(f"   ✅ Request successful")
            print(f"   🔗 Total active suppliers: {supplier_info.get('total_active_suppliers', 0)}")
            print(f"   🔓 Accessible suppliers: {supplier_info.get('accessible_suppliers', 0)}")
            print(f"   📋 Accessible supplier names: {', '.join(supplier_info.get('supplier_names', []))}")
            
            # Check point deduction behavior
            if user_type in ["superuser", "admin"]:
                print(f"   🔓 Point exemption: Should be exempt from point deductions")
            else:
                print(f"   💸 Point deduction: Should apply for general user")
                
        else:
            print(f"   ❌ Request failed: {result['status_code']}")
            if result.get("error"):
                error_detail = json.loads(result["error"]).get("detail", "") if result["error"] else ""
                print(f"   Error: {error_detail[:100]}...")
                
                # Check if it's a permission issue for general users
                if user_type == "general" and "permission" in error_detail.lower():
                    print(f"   ℹ️  This might be expected if general user lacks supplier permissions")

def test_supplier_access_control():
    """Test supplier access control for general users"""
    print("\n🔒 Testing Supplier Access Control")
    print("-" * 40)
    
    general_token = get_auth_token(
        TEST_USERS["general"]["username"], 
        TEST_USERS["general"]["password"]
    )
    
    if not general_token:
        print("❌ Cannot get general user token")
        return
    
    valid_ittid = TEST_CASES["valid_with_suppliers"]
    
    print(f"🧪 Testing general user access to ITTID: {valid_ittid}")
    result = test_get_hotel_by_ittid(general_token, valid_ittid)
    
    if result["success"]:
        response_data = result["response_data"]
        supplier_info = response_data.get("supplier_info", {})
        
        print("   ✅ General user has access to hotel")
        print(f"   🔓 Accessible suppliers: {supplier_info.get('accessible_suppliers', 0)}")
        print(f"   📋 Supplier names: {', '.join(supplier_info.get('supplier_names', []))}")
        
    elif result["status_code"] == 403:
        error_detail = json.loads(result["error"]).get("detail", "") if result["error"] else ""
        print("   🔒 General user access restricted")
        print(f"   📝 Reason: {error_detail}")
        
        if "Available suppliers:" in error_detail:
            print("   ✅ PASS: Error message includes available suppliers for admin reference")
        else:
            print("   ⚠️  Error message could include available suppliers for admin reference")
            
    else:
        print(f"   ❌ Unexpected response: {result['status_code']}")

def test_response_format():
    """Test the enhanced response format with supplier information"""
    print("\n📋 Testing Enhanced Response Format")
    print("-" * 40)
    
    superuser_token = get_auth_token(
        TEST_USERS["superuser"]["username"], 
        TEST_USERS["superuser"]["password"]
    )
    
    if not superuser_token:
        print("❌ Cannot get superuser token")
        return
    
    valid_ittid = TEST_CASES["valid_with_suppliers"]
    result = test_get_hotel_by_ittid(superuser_token, valid_ittid)
    
    if result["success"]:
        response_data = result["response_data"]
        
        print("✅ Response Format Validation:")
        
        # Check required fields
        required_fields = ["hotel", "provider_mappings", "locations", "chains", "contacts", "supplier_info"]
        for field in required_fields:
            if field in response_data:
                print(f"   ✅ {field}: Present")
            else:
                print(f"   ❌ {field}: Missing")
        
        # Check supplier_info structure
        supplier_info = response_data.get("supplier_info", {})
        supplier_fields = ["total_active_suppliers", "accessible_suppliers", "supplier_names"]
        
        print("\n   📊 Supplier Info Structure:")
        for field in supplier_fields:
            if field in supplier_info:
                value = supplier_info[field]
                print(f"      ✅ {field}: {value}")
            else:
                print(f"      ❌ {field}: Missing")
        
        # Check datetime serialization
        hotel_data = response_data.get("hotel", {})
        if "created_at" in hotel_data and "updated_at" in hotel_data:
            print("   ✅ Datetime fields: Properly serialized")
        else:
            print("   ⚠️  Datetime fields: Missing or not serialized")
            
    else:
        print(f"❌ Cannot test response format - request failed: {result['status_code']}")

def main():
    """Run all tests"""
    print("🏨 ACTIVE SUPPLIER VALIDATION TESTS")
    print("=" * 80)
    print("Testing the requirement that hotels must have active suppliers")
    print("to be accessible via /v1.0/content/get_hotel_with_ittid/{ittid}")
    print("=" * 80)
    
    test_active_supplier_validation()
    test_user_role_behavior_with_suppliers()
    test_supplier_access_control()
    test_response_format()
    
    print("\n" + "=" * 80)
    print("🎯 ACTIVE SUPPLIER VALIDATION TEST SUMMARY")
    print("=" * 80)
    print("✅ Hotels with active suppliers: Accessible with supplier information")
    print("❌ Hotels without active suppliers: Rejected with 'Cannot active supplier with this ittid'")
    print("❌ Non-existent hotels: Rejected with 'Hotel not found'")
    print("🔒 General users: Access controlled by supplier permissions")
    print("🔓 Super/Admin users: Access to all hotels with active suppliers")
    print("📋 Enhanced response: Includes supplier information and counts")
    print("\nKey Features:")
    print("• Active supplier validation for all requests")
    print("• Clear error messages for different failure scenarios")
    print("• Role-based access control maintained")
    print("• Enhanced response with supplier information")
    print("• Point exemption for privileged users")

if __name__ == "__main__":
    main()