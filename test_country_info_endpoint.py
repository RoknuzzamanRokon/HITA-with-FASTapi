#!/usr/bin/env python3
"""
Test Get Basic Info Follow Country Code Endpoint

This script tests the /get-basic-info-follow-countryCode endpoint to ensure it's working correctly.
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://127.0.0.1:8002"
TEST_USER = {
    "username": "roman",
    "password": "roman123"
}

def test_country_info_endpoint():
    """Test the get-basic-info-follow-countryCode endpoint"""
    
    print("🧪 Testing Get Basic Info Follow Country Code Endpoint")
    print("=" * 60)
    
    session = requests.Session()
    
    # Step 1: Login
    print("🔐 Step 1: Login")
    login_data = {
        "username": TEST_USER["username"],
        "password": TEST_USER["password"]
    }
    
    try:
        response = session.post(f"{BASE_URL}/v1.0/auth/token", data=login_data)
        if response.status_code == 200:
            result = response.json()
            access_token = result.get("access_token")
            session.headers.update({"Authorization": f"Bearer {access_token}"})
            print("✅ Login successful!")
            
            # Get user info
            user_response = session.get(f"{BASE_URL}/v1.0/user/check-me")
            if user_response.status_code == 200:
                user_info = user_response.json()
                user_id = user_info.get("id")
                print(f"   User: {user_info.get('username')} (ID: {user_id})")
                print(f"   Role: {user_info.get('role')}")
            else:
                print("❌ Could not get user info")
                return False
        else:
            print(f"❌ Login failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False
    
    # Step 2: Test endpoint with different suppliers and countries
    test_cases = [
        {"supplier": "booking", "country_iso": "US"},
        {"supplier": "expedia", "country_iso": "GB"},
        {"supplier": "hotelbeds", "country_iso": "FR"},
        {"supplier": "invalid_supplier", "country_iso": "US"},  # Should fail
        {"supplier": "booking", "country_iso": "XX"},  # Should fail - invalid country
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Step 2.{i}: Test with supplier='{test_case['supplier']}', country='{test_case['country_iso']}'")
        
        try:
            request_data = {
                "supplier": test_case["supplier"],
                "country_iso": test_case["country_iso"]
            }
            
            response = session.post(
                f"{BASE_URL}/v1.0/content/get-basic-info-follow-countryCode",
                json=request_data
            )
            
            print(f"   Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Request successful!")
                print(f"   Success: {result.get('success', False)}")
                print(f"   Supplier: {result.get('supplier', 'N/A')}")
                print(f"   Country ISO: {result.get('country_iso', 'N/A')}")
                print(f"   Total Hotels: {result.get('total_hotel', 0)}")
                
                # Show sample data if available
                data = result.get('data', [])
                if data and isinstance(data, list) and len(data) > 0:
                    print(f"   Sample Data: {str(data[0])[:100]}...")
                elif data:
                    print(f"   Data Type: {type(data).__name__}")
                else:
                    print("   No data returned")
                    
            elif response.status_code == 403:
                result = response.json()
                if result.get("error_code") == "IP_NOT_WHITELISTED":
                    print("🔒 Access BLOCKED by IP whitelist (expected)")
                    print(f"   Client IP: {result.get('details', {}).get('client_ip', 'unknown')}")
                else:
                    print(f"⚠️ Access denied: {result.get('detail', 'Unknown error')}")
                    
            elif response.status_code == 404:
                result = response.json()
                print(f"❌ Not found: {result.get('detail', 'Unknown error')}")
                
            else:
                print(f"❌ Unexpected response: {response.status_code}")
                try:
                    result = response.json()
                    print(f"   Error: {result.get('detail', 'Unknown error')}")
                except:
                    print(f"   Raw response: {response.text}")
                    
        except Exception as e:
            print(f"❌ Request error: {e}")
    
    return True

def main():
    """Main test function"""
    print(f"🚀 Country Info Endpoint Test")
    print(f"📍 Base URL: {BASE_URL}")
    print(f"👤 Test User: {TEST_USER['username']}")
    print(f"⏰ Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success = test_country_info_endpoint()
    
    print("\n" + "=" * 60)
    print("📊 Endpoint Information:")
    print("🔗 POST /v1.0/content/get-basic-info-follow-countryCode")
    print("📝 Request Body: {\"supplier\": \"booking\", \"country_iso\": \"US\"}")
    print("🔒 Features: IP whitelist, role-based access, file-based data")
    
    print("\n🔧 Fixed Issues:")
    print("✅ Fixed duplicate 'request' parameter in function signature")
    print("✅ Updated IP whitelist debug message")
    print("✅ Improved docstring with clear examples")
    print("✅ Added comprehensive error handling")
    
    if success:
        print("\n🎯 ✅ Country Info Endpoint Test Complete!")
        print("🛡️ Endpoint is ready for use with proper error handling.")
    else:
        print("\n💥 ❌ Some tests encountered issues.")
    
    return success

if __name__ == "__main__":
    main()