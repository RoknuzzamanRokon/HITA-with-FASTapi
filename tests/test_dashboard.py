#!/usr/bin/env python3
"""
Simple test script for the dashboard endpoint
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
LOGIN_URL = f"{BASE_URL}/v1.0/auth/token"
DASHBOARD_URL = f"{BASE_URL}/v1.0/dashboard/stats"

def test_dashboard():
    """Test the dashboard endpoint with admin credentials"""
    
    print("🧪 Testing Dashboard Endpoint")
    print("=" * 50)
    
    # You'll need to replace these with actual admin credentials
    admin_credentials = {
        "username": "admin",  # Replace with actual admin username
        "password": "password"  # Replace with actual admin password
    }
    
    try:
        # Step 1: Login to get access token
        print("1. Logging in...")
        login_response = requests.post(
            LOGIN_URL,
            data=admin_credentials,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.status_code}")
            print(f"Response: {login_response.text}")
            return
        
        token_data = login_response.json()
        access_token = token_data["access_token"]
        print("✅ Login successful")
        
        # Step 2: Call dashboard endpoint
        print("2. Fetching dashboard stats...")
        headers = {"Authorization": f"Bearer {access_token}"}
        
        dashboard_response = requests.get(DASHBOARD_URL, headers=headers)
        
        if dashboard_response.status_code != 200:
            print(f"❌ Dashboard request failed: {dashboard_response.status_code}")
            print(f"Response: {dashboard_response.text}")
            return
        
        # Step 3: Display results
        dashboard_data = dashboard_response.json()
        print("✅ Dashboard data retrieved successfully")
        print("\n📊 DASHBOARD STATISTICS")
        print("=" * 50)
        
        # Main stats
        print(f"Total Users: {dashboard_data['total_users']}")
        print(f"Active Users: {dashboard_data['active_users']}")
        print(f"Admin Users: {dashboard_data['admin_users']}")
        print(f"General Users: {dashboard_data['general_users']}")
        print(f"Points Distributed: {dashboard_data['points_distributed']}")
        print(f"Current Balance: {dashboard_data['current_balance']}")
        print(f"Recent Signups: {dashboard_data['recent_signups']}")
        print(f"Inactive Users: {dashboard_data['inactive_users']}")
        
        # Additional stats
        if 'additional_stats' in dashboard_data:
            print("\n📈 ADDITIONAL STATISTICS")
            print("-" * 30)
            additional = dashboard_data['additional_stats']
            print(f"Super Users: {additional.get('super_users', 0)}")
            print(f"Admin Users Only: {additional.get('admin_users_only', 0)}")
            print(f"Total Transactions: {additional.get('total_transactions', 0)}")
            print(f"Recent Activity Count: {additional.get('recent_activity_count', 0)}")
            print(f"Users with API Keys: {additional.get('users_with_api_keys', 0)}")
            print(f"Points Used: {additional.get('points_used', 0)}")
        
        print(f"\n⏰ Generated at: {dashboard_data['timestamp']}")
        print(f"👤 Requested by: {dashboard_data['requested_by']['username']} ({dashboard_data['requested_by']['role']})")
        
        # Test other endpoints
        print("\n🔍 Testing additional endpoints...")
        
        # User activity stats
        activity_response = requests.get(f"{BASE_URL}/v1.0/dashboard/user-activity", headers=headers)
        if activity_response.status_code == 200:
            print("✅ User activity endpoint working")
        else:
            print(f"❌ User activity endpoint failed: {activity_response.status_code}")
        
        # Points summary
        points_response = requests.get(f"{BASE_URL}/v1.0/dashboard/points-summary", headers=headers)
        if points_response.status_code == 200:
            print("✅ Points summary endpoint working")
        else:
            print(f"❌ Points summary endpoint failed: {points_response.status_code}")
        
        print("\n🎉 Dashboard test completed successfully!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection error: Make sure the backend server is running on localhost:8000")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    test_dashboard()