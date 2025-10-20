#!/usr/bin/env python3
"""
Connection test script to verify dashboard API is working
"""

import requests
import json
import sys

def test_connection():
    """Test the connection to dashboard API"""
    
    print("🔍 Testing Dashboard API Connection")
    print("=" * 50)
    
    BASE_URL = "http://localhost:8000"
    
    # Test 1: Health check
    print("1. Testing backend health...")
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ Backend server is running and accessible")
        else:
            print(f"⚠️ Backend responded with status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend server")
        print("💡 Make sure to start the server with:")
        print("   cd backend")
        print("   uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        return False
    except Exception as e:
        print(f"❌ Error connecting to backend: {e}")
        return False
    
    # Test 2: API health endpoint
    print("2. Testing API health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/v1.0/health/", timeout=5)
        if response.status_code == 200:
            print("✅ API health endpoint working")
        else:
            print(f"⚠️ API health endpoint returned {response.status_code}")
    except Exception as e:
        print(f"❌ API health endpoint failed: {e}")
    
    # Test 3: Login endpoint
    print("3. Testing login endpoint...")
    credentials = {
        "username": "admin",  # Update with your admin username
        "password": "admin123"  # Update with your admin password
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/v1.0/auth/token",
            data=credentials,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            print("✅ Login endpoint working")
            
            # Test 4: Dashboard endpoint
            print("4. Testing dashboard stats endpoint...")
            headers = {"Authorization": f"Bearer {access_token}"}
            
            dashboard_response = requests.get(
                f"{BASE_URL}/v1.0/dashboard/stats",
                headers=headers,
                timeout=10
            )
            
            if dashboard_response.status_code == 200:
                data = dashboard_response.json()
                print("✅ Dashboard API working perfectly!")
                print(f"   Sample data: Total Users = {data.get('total_users', 'N/A')}")
                return True
            else:
                print(f"❌ Dashboard API failed with status {dashboard_response.status_code}")
                print(f"   Response: {dashboard_response.text}")
                return False
                
        else:
            print(f"❌ Login failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            print("💡 Please update the credentials in this script")
            return False
            
    except Exception as e:
        print(f"❌ Login test failed: {e}")
        return False

def check_cors():
    """Check CORS configuration"""
    print("\n🌐 CORS Configuration Check")
    print("-" * 30)
    
    try:
        # Make a preflight request
        response = requests.options(
            "http://localhost:8000/v1.0/dashboard/stats",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type"
            },
            timeout=5
        )
        
        cors_headers = {
            "Access-Control-Allow-Origin": response.headers.get("Access-Control-Allow-Origin"),
            "Access-Control-Allow-Methods": response.headers.get("Access-Control-Allow-Methods"),
            "Access-Control-Allow-Headers": response.headers.get("Access-Control-Allow-Headers"),
        }
        
        print("CORS Headers:")
        for header, value in cors_headers.items():
            if value:
                print(f"  ✅ {header}: {value}")
            else:
                print(f"  ❌ {header}: Not set")
                
        if cors_headers["Access-Control-Allow-Origin"] in ["*", "http://localhost:3000"]:
            print("✅ CORS is properly configured")
        else:
            print("⚠️ CORS might not allow frontend requests")
            
    except Exception as e:
        print(f"❌ CORS check failed: {e}")

if __name__ == "__main__":
    print("🧪 Dashboard Connection Test")
    print("=" * 50)
    
    success = test_connection()
    check_cors()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed!")
        print("✅ Your dashboard API is working correctly")
        print("🌐 Frontend should be able to connect")
        print("\n💡 If frontend still shows errors:")
        print("   1. Check browser console for specific error messages")
        print("   2. Verify frontend is running on http://localhost:3000")
        print("   3. Clear browser cache and cookies")
    else:
        print("🔧 Some tests failed")
        print("💡 Please fix the issues above before testing frontend")
        sys.exit(1)