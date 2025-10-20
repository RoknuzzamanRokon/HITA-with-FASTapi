#!/usr/bin/env python3
"""
Test the robust dashboard implementation
"""

import requests
import json

def test_robust_dashboard():
    """Test the dashboard with better error handling"""
    
    print("🧪 Testing Robust Dashboard Implementation")
    print("=" * 50)
    
    BASE_URL = "http://localhost:8000"
    
    # Test credentials - update these with your actual admin credentials
    credentials = {
        "username": "admin",  # Update with your admin username
        "password": "admin123"  # Update with your admin password
    }
    
    try:
        # Step 1: Login
        print("1. Testing login...")
        login_response = requests.post(
            f"{BASE_URL}/v1.0/auth/token",
            data=credentials,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.status_code}")
            print(f"Response: {login_response.text}")
            print("\n💡 Please update credentials in this script or create an admin user")
            return False
        
        token_data = login_response.json()
        access_token = token_data["access_token"]
        print("✅ Login successful!")
        
        # Step 2: Test main dashboard stats
        print("2. Testing main dashboard stats...")
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = requests.get(f"{BASE_URL}/v1.0/dashboard/stats", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Dashboard stats working!")
            print(f"   Total Users: {data.get('total_users')}")
            print(f"   Active Users: {data.get('active_users')}")
            print(f"   Admin Users: {data.get('admin_users')}")
            print(f"   General Users: {data.get('general_users')}")
            print(f"   Points Distributed: {data.get('points_distributed')}")
            print(f"   Current Balance: {data.get('current_balance')}")
            print(f"   Recent Signups: {data.get('recent_signups')}")
            print(f"   Inactive Users: {data.get('inactive_users')}")
        else:
            print(f"❌ Dashboard stats failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        # Step 3: Test user activity endpoint
        print("3. Testing user activity endpoint...")
        response = requests.get(f"{BASE_URL}/v1.0/dashboard/user-activity", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ User activity endpoint working!")
            print(f"   Daily activities: {len(data.get('daily_activity', []))}")
            print(f"   Most active users: {len(data.get('most_active_users', []))}")
        else:
            print(f"❌ User activity failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        # Step 4: Test points summary endpoint
        print("4. Testing points summary endpoint...")
        response = requests.get(f"{BASE_URL}/v1.0/dashboard/points-summary", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Points summary endpoint working!")
            print(f"   Points by role: {len(data.get('points_by_role', []))}")
            print(f"   Recent transactions: {data.get('recent_transactions_30d')}")
            print(f"   Transaction types: {len(data.get('transaction_types', []))}")
            print(f"   Top point holders: {len(data.get('top_point_holders', []))}")
        else:
            print(f"❌ Points summary failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        print("\n🎉 All dashboard endpoints are working!")
        print("✅ The 500 errors have been fixed")
        print("🌐 Frontend should now work at: http://localhost:3000/dashboard")
        
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
    success = test_robust_dashboard()
    if success:
        print("\n🚀 Dashboard is ready!")
        print("   1. Start frontend: npm run dev")
        print("   2. Go to: http://localhost:3000/dashboard")
        print("   3. Login with admin credentials")
        print("   4. View your dashboard statistics")
    else:
        print("\n🔧 Please fix the issues above")