#!/usr/bin/env python3
"""
Simple Country Info Endpoint Test

Quick test to verify the endpoint is working correctly.
"""

import requests
import json

# Configuration
BASE_URL = "http://127.0.0.1:8002"
TEST_USER = {
    "username": "roman",
    "password": "roman123"
}

def simple_test():
    """Simple test of the country info endpoint"""
    
    print("🧪 Simple Country Info Endpoint Test")
    print("=" * 50)
    
    session = requests.Session()
    
    # Login
    print("🔐 Login...")
    login_data = {"username": TEST_USER["username"], "password": TEST_USER["password"]}
    response = session.post(f"{BASE_URL}/v1.0/auth/token", data=login_data)
    
    if response.status_code == 200:
        result = response.json()
        access_token = result.get("access_token")
        session.headers.update({"Authorization": f"Bearer {access_token}"})
        print("✅ Login successful!")
    else:
        print(f"❌ Login failed: {response.status_code}")
        return False
    
    # Test endpoint
    print("\n📋 Testing endpoint...")
    request_data = {
        "supplier": "hotelbeds",
        "country_iso": "US"
    }
    
    response = session.post(
        f"{BASE_URL}/v1.0/content/get-basic-info-follow-countryCode",
        json=request_data
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("✅ SUCCESS!")
        print(f"Supplier: {result.get('supplier')}")
        print(f"Country: {result.get('country_iso')}")
        print(f"Total Hotels: {result.get('total_hotel')}")
        return True
    else:
        try:
            result = response.json()
            print(f"❌ Error: {result}")
        except:
            print(f"❌ Raw error: {response.text}")
        return False

if __name__ == "__main__":
    simple_test()