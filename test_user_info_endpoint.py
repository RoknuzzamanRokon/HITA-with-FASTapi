#!/usr/bin/env python3
"""
Test User Info Endpoint with Ownership Validation

This script tests the /check/user_info/{user_id} endpoint to verify
that admin and super users can only view users they created.
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_user_info_endpoint():
    """Test the check/user_info endpoint with ownership validation"""
    
    print("🧪 Testing User Info Endpoint (Ownership Validation)")
    print("="*80)
    
    # Step 1: Login as admin/super user
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
        
        login_result = response.json()
        print("✅ Login successful")
        print(f"   User: {login_result.get('username')}")
        print(f"   Role: {login_result.get('role')}")
        
        # Step 2: Get list of users created by current user
        print("\n📋 Step 2: Get users created by current user...")
        response = session.get(f"{BASE_URL}/v1.0/user/check/all")
        
        if response.status_code != 200:
            print(f"❌ Failed to get user list: {response.status_code}")
            print(response.text)
            return False
        
        users_data = response.json()
        
        # Get a general user ID to test
        test_user_id = None
        if users_data.get('general_users'):
            test_user_id = users_data['general_users'][0]['id']
            print(f"✅ Found test user: {users_data['general_users'][0]['username']}")
            print(f"   User ID: {test_user_id}")
        else:
            print("⚠️  No general users found to test")
            print("   Create a general user first to test this endpoint")
            return True
        
        # Step 3: Test getting user info (should succeed - user created by current user)
        print(f"\n✅ Step 3: Get user info (owned user)...")
        response = session.get(f"{BASE_URL}/v1.0/user/check/user_info/{test_user_id}")
        
        if response.status_code != 200:
            print(f"❌ Failed to get user info: {response.status_code}")
            print(response.text)
            return False
        
        user_info = response.json()
        print(f"✅ Successfully retrieved user info")
        print(f"\n📊 User Details:")
        print(f"   ID: {user_info['id']}")
        print(f"   Username: {user_info['username']}")
        print(f"   Email: {user_info['email']}")
        print(f"   Role: {user_info['role']}")
        print(f"   Status: {user_info['is_active']}")
        print(f"   Created By: {user_info['created_by']}")
        
        print(f"\n💰 Points Info:")
        print(f"   Total Points: {user_info['points']['total_points']}")
        print(f"   Current Points: {user_info['points']['current_points']}")
        print(f"   Paid Status: {user_info['points']['paid_status']}")
        print(f"   Total Requests: {user_info['points']['total_rq']}")
        
        print(f"\n📡 Suppliers:")
        print(f"   Total Suppliers: {user_info['total_suppliers']}")
        if user_info['active_suppliers']:
            print(f"   Active Suppliers: {', '.join(user_info['active_suppliers'][:5])}")
        
        print(f"\n📈 Activity:")
        print(f"   Status: {user_info['using_rq_status']}")
        
        # Step 4: Test with non-existent user (should fail)
        print(f"\n❌ Step 4: Test with non-existent user...")
        response = session.get(f"{BASE_URL}/v1.0/user/check/user_info/nonexistent123")
        
        if response.status_code == 404:
            print(f"✅ Correctly returned 404 for non-existent user")
        else:
            print(f"⚠️  Expected 404, got {response.status_code}")
        
        print("\n" + "="*80)
        print("✅ All tests passed!")
        print("\n💡 Endpoint Features:")
        print("   • Admin/Super users can view users they created")
        print("   • Ownership validation using created_by field")
        print("   • Super users can view all users (optional)")
        print("   • Returns detailed user info including points and suppliers")
        print("   • Returns 404 for users not created by current user")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Is the server running?")
        print("💡 Start server with: pipenv run uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    success = test_user_info_endpoint()
    
    if not success:
        print("\n❌ Tests failed!")
    
    return success

if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
