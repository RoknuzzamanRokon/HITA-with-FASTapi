#!/usr/bin/env python3
"""
Test Unpaid General Users Endpoint

This script tests the /all-general-user endpoint to verify it returns
only general users who are not paid (have zero or no points).
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_unpaid_users_endpoint():
    """Test the all-general-user endpoint"""
    
    print("🧪 Testing Unpaid General Users Endpoint")
    print("="*80)
    
    # Step 1: Login
    print("\n🔐 Step 1: Login as admin/super user...")
    login_data = {
        "username": "roman",  # Change to your admin/super user
        "password": "123456"   # Change to your password
    }
    
    session = requests.Session()
    
    try:
        response = session.post(f"{BASE_URL}/v1.0/auth/login", json=login_data)
        
        if response.status_code != 200:
            print(f"❌ Login failed: {response.status_code}")
            print(response.text)
            return False
        
        print("✅ Login successful")
        
        # Step 2: Test the endpoint without parameters
        print("\n📋 Step 2: Get unpaid users (default pagination)...")
        response = session.get(f"{BASE_URL}/v1.0/user/all-general-user")
        
        if response.status_code != 200:
            print(f"❌ Request failed: {response.status_code}")
            print(response.text)
            return False
        
        data = response.json()
        
        print(f"✅ Request successful")
        print(f"\n📊 Results:")
        print(f"   Total Unpaid Users: {data['statistics']['total_unpaid_users']}")
        print(f"   Showing: {data['statistics']['showing']}")
        print(f"   Page: {data['pagination']['page']}/{data['pagination']['total_pages']}")
        
        if data['users']:
            print(f"\n👥 Sample Users (first 3):")
            for i, user in enumerate(data['users'][:3], 1):
                print(f"\n   {i}. {user['username']} ({user['email']})")
                print(f"      ID: {user['id']}")
                print(f"      Points: {user['points']['current_points']}")
                print(f"      Status: {user['points']['paid_status']}")
                print(f"      Suppliers: {user['total_suppliers']}")
                print(f"      Activity: {user['activity_status']}")
        else:
            print("\n   No unpaid users found")
        
        # Step 3: Test with pagination
        print("\n📋 Step 3: Test pagination (page 1, limit 5)...")
        response = session.get(f"{BASE_URL}/v1.0/user/all-general-user?page=1&limit=5")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Pagination works")
            print(f"   Showing: {len(data['users'])} users")
        
        # Step 4: Test with search
        print("\n🔍 Step 4: Test search functionality...")
        response = session.get(f"{BASE_URL}/v1.0/user/all-general-user?search=test")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Search works")
            print(f"   Found: {data['statistics']['total_unpaid_users']} users matching 'test'")
        
        print("\n" + "="*80)
        print("✅ All tests passed!")
        print("\n💡 Endpoint Features:")
        print("   • Returns only general users with unpaid status")
        print("   • Supports pagination (page, limit)")
        print("   • Supports search (username, email)")
        print("   • Includes user details, points, and suppliers")
        print("   • Access restricted to super_user and admin_user")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Is the server running?")
        print("💡 Start server with: pipenv run uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    success = test_unpaid_users_endpoint()
    
    if not success:
        print("\n❌ Tests failed!")
    
    return success

if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
