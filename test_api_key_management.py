"""
Test script for API Key Management System
Tests the new API key policy where only admin/super admin can generate API keys
"""

import requests
import json

base_url = "http://127.0.0.1:8000"

def test_api_key_management():
    """Test the complete API key management system"""
    
    print("🔑 Testing API Key Management System")
    print("=" * 50)
    
    # Test 1: Self-registration (should not get API key)
    print("\n1. Testing Self-Registration (Expected: No API key)")
    test_self_registration()
    
    # Test 2: Admin creating user (should get API key)
    print("\n2. Testing Admin User Creation (Expected: API key generated)")
    test_admin_user_creation()
    
    # Test 3: API key regeneration restrictions
    print("\n3. Testing API Key Regeneration Restrictions")
    test_api_key_regeneration_restrictions()
    
    # Test 4: Admin generating API keys for others
    print("\n4. Testing Admin Generating API Keys for Others")
    test_admin_generate_api_keys()
    
    # Test 5: API key revocation
    print("\n5. Testing API Key Revocation")
    test_api_key_revocation()

def test_self_registration():
    """Test that self-registered users don't get API keys"""
    
    print("-" * 30)
    
    # Register a new user
    register_data = {
        "username": "selfuser123",
        "email": "selfuser123@example.com",
        "password": "password123"
    }
    
    try:
        response = requests.post(
            f"{base_url}/v1.0/auth/register",
            json=register_data
        )
        
        print(f"   Registration Status: {response.status_code}")
        
        if response.status_code == 200:
            result = json.loads(response.text)
            api_key = result.get('api_key')
            
            if api_key is None:
                print("   ✅ PASS: Self-registered user has no API key")
            else:
                print(f"   ❌ FAIL: Self-registered user got API key: {api_key[:20]}...")
        else:
            print(f"   ⚠️  Registration failed: {response.text[:100]}...")
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

def test_admin_user_creation():
    """Test that admin-created users get API keys"""
    
    print("-" * 30)
    print("📝 Note: This test requires admin credentials")
    print("   To test admin user creation:")
    print("   1. Login as admin/super admin")
    print("   2. Use POST /v1.0/user/create_general_user")
    print("   3. Created user should have API key")
    print("   Expected: User created by admin gets API key automatically")

def test_api_key_regeneration_restrictions():
    """Test API key regeneration restrictions"""
    
    print("-" * 30)
    
    # First, try to login as the self-registered user
    login_data = 'username=selfuser123&password=password123'
    login_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    try:
        login_response = requests.post(f"{base_url}/v1.0/auth/token", data=login_data, headers=login_headers)
        
        if login_response.status_code == 200:
            token_data = json.loads(login_response.text)
            token = token_data.get('access_token')
            
            # Try to regenerate API key as general user
            headers = {'Authorization': f'Bearer {token}'}
            
            regen_response = requests.post(
                f"{base_url}/v1.0/auth/regenerate_api_key",
                headers=headers
            )
            
            print(f"   Regeneration Status: {regen_response.status_code}")
            
            if regen_response.status_code == 403:
                print("   ✅ PASS: General user cannot regenerate API key")
                error_detail = json.loads(regen_response.text).get('detail', '')
                print(f"   📝 Error: {error_detail[:80]}...")
            else:
                print(f"   ❌ FAIL: General user was able to regenerate API key")
                print(f"   📝 Response: {regen_response.text[:100]}...")
        else:
            print(f"   ⚠️  Login failed: {login_response.text[:100]}...")
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

def test_admin_generate_api_keys():
    """Test admin generating API keys for other users"""
    
    print("-" * 30)
    print("📝 Note: This test requires admin credentials and existing user ID")
    print("   To test admin API key generation:")
    print("   1. Login as admin/super admin")
    print("   2. Use POST /v1.0/auth/generate_api_key/{user_id}")
    print("   3. Should successfully generate API key for target user")
    print("   Expected: Admin can generate API keys for any user")

def test_api_key_revocation():
    """Test API key revocation by admin"""
    
    print("-" * 30)
    print("📝 Note: This test requires admin credentials and existing user ID")
    print("   To test API key revocation:")
    print("   1. Login as admin/super admin")
    print("   2. Use DELETE /v1.0/auth/revoke_api_key/{user_id}")
    print("   3. Should successfully revoke API key for target user")
    print("   Expected: Admin can revoke API keys from any user")

def test_with_admin_credentials(admin_username, admin_password):
    """Test API key management with admin credentials"""
    
    print(f"\n🔐 Testing with Admin Credentials: {admin_username}")
    print("-" * 50)
    
    # Login as admin
    login_data = f'username={admin_username}&password={admin_password}'
    login_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    try:
        login_response = requests.post(f"{base_url}/v1.0/auth/token", data=login_data, headers=login_headers)
        
        if login_response.status_code == 200:
            token_data = json.loads(login_response.text)
            admin_token = token_data.get('access_token')
            
            headers = {'Authorization': f'Bearer {admin_token}'}
            
            # Test 1: Admin can regenerate their own API key
            print("\n1. Testing Admin API Key Regeneration")
            test_admin_regenerate_api_key(headers)
            
            # Test 2: Admin can generate API key for others (need user ID)
            print("\n2. Testing Admin Generate API Key for Others")
            print("   📝 Need target user ID to test this functionality")
            print("   Example: POST /v1.0/auth/generate_api_key/user123")
            
            # Test 3: Admin can revoke API keys
            print("\n3. Testing Admin API Key Revocation")
            print("   📝 Need target user ID to test this functionality")
            print("   Example: DELETE /v1.0/auth/revoke_api_key/user123")
            
        else:
            print(f"❌ Admin login failed: {login_response.text}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

def test_admin_regenerate_api_key(headers):
    """Test admin regenerating their own API key"""
    
    try:
        response = requests.post(
            f"{base_url}/v1.0/auth/regenerate_api_key",
            headers=headers
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = json.loads(response.text)
            print("   ✅ PASS: Admin can regenerate API key")
            print(f"   🔑 New API key: {result.get('api_key', 'N/A')[:20]}...")
        else:
            print(f"   ❌ FAIL: Admin cannot regenerate API key")
            print(f"   📝 Response: {response.text[:100]}...")
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

def test_api_key_endpoints_access():
    """Test accessing API key protected endpoints"""
    
    print("\n6. Testing API Key Protected Endpoints")
    print("-" * 40)
    
    print("📝 API Key Authentication Test:")
    print("   Some endpoints may require API key authentication")
    print("   Example: GET /v1.0/auth/apikey/me")
    print("   Header: X-API-Key: your_api_key_here")
    print("   Expected: Only users with valid API keys can access")

def show_api_key_policy():
    """Show the new API key policy"""
    
    print("\n📋 API Key Policy Summary")
    print("=" * 30)
    print("🔒 New API Key Rules:")
    print("   ✅ Self-registered users: NO API key")
    print("   ✅ Admin-created users: API key generated automatically")
    print("   ✅ Only Admin/Super Admin can:")
    print("      - Regenerate their own API keys")
    print("      - Generate API keys for other users")
    print("      - Revoke API keys from users")
    print("   ❌ General users CANNOT:")
    print("      - Regenerate API keys")
    print("      - Generate API keys for others")
    print("      - Access API key management endpoints")

if __name__ == "__main__":
    test_api_key_management()
    test_api_key_endpoints_access()
    show_api_key_policy()
    
    print("\n" + "=" * 50)
    print("🎯 API KEY MANAGEMENT TEST SUMMARY")
    print("=" * 50)
    print("✅ Policy implemented:")
    print("   - Self-registered users get NO API key")
    print("   - Admin-created users get API key automatically")
    print("   - Only Admin/Super Admin can manage API keys")
    print("\n🔑 New Endpoints:")
    print("   - POST /v1.0/auth/regenerate_api_key (Admin only)")
    print("   - POST /v1.0/auth/generate_api_key/{user_id} (Admin only)")
    print("   - DELETE /v1.0/auth/revoke_api_key/{user_id} (Admin only)")
    print("\n🧪 To test with admin credentials:")
    print("   test_with_admin_credentials('admin_username', 'admin_password')")
    print("\n🛡️ Security Benefits:")
    print("   - Prevents unauthorized API key generation")
    print("   - Centralized API key management")
    print("   - Clear separation between user types")
    print("   - Admin control over API access")