#!/usr/bin/env python3
"""
Simple test to verify dashboard endpoint works
Run this after starting your FastAPI server
"""

import requests
import json

def test_dashboard_endpoint():
    """Test the dashboard endpoint"""
    
    print("🧪 Testing Dashboard Endpoint")
    print("=" * 50)
    
    # Configuration
    BASE_URL = "http://localhost:8000"
    
    # Test credentials - you'll need to update these
    credentials = {
        "username": "admin",  # Replace with your admin username
        "password": "admin123"  # Replace with your admin password
    }
    
    try:
        # Step 1: Login
        print("1. Attempting login...")
        login_response = requests.post(
            f"{BASE_URL}/v1.0/auth/token",
            data=credentials,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if login_response.status_code != 200:
            print(f"❌ Login failed with status {login_response.status_code}")
            print(f"Response: {login_response.text}")
            print("\n💡 Make sure you have:")
            print("   - A user with admin or super_user role")
            print("   - Correct username and password")
            print("   - Backend server running on localhost:8000")
            return False
        
        token_data = login_response.json()
        access_token = token_data["access_token"]
        print("✅ Login successful!")
        
        # Step 2: Test dashboard endpoint
        print("2. Testing dashboard stats endpoint...")
        headers = {"Authorization": f"Bearer {access_token}"}
        
        dashboard_response = requests.get(
            f"{BASE_URL}/v1.0/dashboard/stats",
            headers=headers
        )
        
        if dashboard_response.status_code != 200:
            print(f"❌ Dashboard request failed with status {dashboard_response.status_code}")
            print(f"Response: {dashboard_response.text}")
            return False
        
        # Step 3: Display results
        data = dashboard_response.json()
        print("✅ Dashboard endpoint working!")
        print("\n📊 Dashboard Statistics:")
        print(f"   Total Users: {data.get('total_users', 'N/A')}")
        print(f"   Active Users: {data.get('active_users', 'N/A')}")
        print(f"   Admin Users: {data.get('admin_users', 'N/A')}")
        print(f"   General Users: {data.get('general_users', 'N/A')}")
        print(f"   Points Distributed: {data.get('points_distributed', 'N/A')}")
        print(f"   Current Balance: {data.get('current_balance', 'N/A')}")
        print(f"   Recent Signups: {data.get('recent_signups', 'N/A')}")
        print(f"   Inactive Users: {data.get('inactive_users', 'N/A')}")
        
        print("\n🎉 Test completed successfully!")
        print(f"🌐 Frontend can now access: http://localhost:3000/dashboard")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection error!")
        print("💡 Make sure your FastAPI server is running:")
        print("   cd backend")
        print("   uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_dashboard_endpoint()
    if success:
        print("\n🚀 Ready to test frontend integration!")
        print("   1. Start your Next.js frontend: npm run dev")
        print("   2. Navigate to: http://localhost:3000/dashboard")
        print("   3. Login with admin credentials")
        print("   4. View the dashboard statistics")
    else:
        print("\n🔧 Fix the issues above and try again")