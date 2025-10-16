#!/usr/bin/env python3
"""
Test script to verify the dashboard endpoint works after fixing JSON serialization
"""

import requests
import json

def test_dashboard_fix():
    """Test the fixed dashboard endpoint"""
    
    print("🔧 Testing Fixed Dashboard Endpoint")
    print("=" * 50)
    
    BASE_URL = "http://localhost:8000"
    
    # Test with sample admin credentials
    credentials = {
        "username": "admin",  # Update with your admin username
        "password": "admin123"  # Update with your admin password
    }
    
    try:
        # Step 1: Login
        print("1. Logging in...")
        login_response = requests.post(
            f"{BASE_URL}/v1.0/auth/token",
            data=credentials,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.status_code}")
            print(f"Response: {login_response.text}")
            print("\n💡 Please update the credentials in this script with valid admin user")
            return False
        
        token_data = login_response.json()
        access_token = token_data["access_token"]
        print("✅ Login successful!")
        
        # Step 2: Test main dashboard stats
        print("2. Testing main dashboard stats...")
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = requests.get(f"{BASE_URL}/v1.0/dashboard/stats", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Dashboard stats failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        data = response.json()
        print("✅ Dashboard stats working!")
        print(f"   Total Users: {data.get('total_users')}")
        print(f"   Active Users: {data.get('active_users')}")
        print(f"   Admin Users: {data.get('admin_users')}")
        
        # Step 3: Test user activity endpoint
        print("3. Testing user activity endpoint...")
        response = requests.get(f"{BASE_URL}/v1.0/dashboard/user-activity", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ User activity failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        print("✅ User activity endpoint working!")
        
        # Step 4: Test points summary endpoint
        print("4. Testing points summary endpoint...")
        response = requests.get(f"{BASE_URL}/v1.0/dashboard/points-summary", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Points summary failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        print("✅ Points summary endpoint working!")
        
        print("\n🎉 All dashboard endpoints are working correctly!")
        print("✅ JSON serialization issue has been fixed")
        print("🌐 Frontend should now work at: http://localhost:3000/dashboard")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection error!")
        print("💡 Make sure your FastAPI server is running:")
        print("   uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_dashboard_fix()
    if success:
        print("\n🚀 Dashboard is ready!")
        print("   1. Start frontend: npm run dev")
        print("   2. Go to: http://localhost:3000/dashboard")
        print("   3. Login with admin credentials")
    else:
        print("\n🔧 Please fix the issues above")