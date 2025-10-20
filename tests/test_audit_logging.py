"""
Test script to demonstrate audit logging functionality
"""

import requests
import json

base_url = "http://127.0.0.1:8000"

def test_audit_logging():
    """Test audit logging by making requests and checking logs"""
    
    print("🔍 Testing Audit Logging Functions")
    print("=" * 50)
    
    # 1. Test login (will create audit logs)
    print("\n1. Testing Login (creates audit logs)...")
    login_data = 'username=testuser&password=testpass123'
    login_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    login_response = requests.post(
        f"{base_url}/v1.0/auth/token",
        data=login_data,
        headers=login_headers
    )
    
    if login_response.status_code == 200:
        token_data = json.loads(login_response.text)
        token = token_data.get('access_token')
        print(f"✅ Login successful - audit log created")
        
        # 2. Test getting my activity
        print("\n2. Getting my activity history...")
        auth_headers = {'Authorization': f'Bearer {token}'}
        
        activity_response = requests.get(
            f"{base_url}/v1.0/audit/my-activity?days=7&limit=10",
            headers=auth_headers
        )
        
        if activity_response.status_code == 200:
            activity_data = json.loads(activity_response.text)
            print(f"✅ Found {activity_data['total_activities']} activities")
            
            # Show recent activities
            for activity in activity_data['activities'][:3]:
                print(f"   - {activity['action']} at {activity['created_at']}")
        
        # 3. Test activity summary
        print("\n3. Getting activity summary...")
        summary_response = requests.get(
            f"{base_url}/v1.0/audit/activity-summary?days=30",
            headers=auth_headers
        )
        
        if summary_response.status_code == 200:
            summary_data = json.loads(summary_response.text)
            print(f"✅ Activity Summary:")
            print(f"   - Total activities: {summary_data['total_activities']}")
            print(f"   - Security events: {summary_data['security_events']}")
            print(f"   - Period: {summary_data['period_days']} days")
        
        # 4. Test available activity types
        print("\n4. Getting available activity types...")
        types_response = requests.get(
            f"{base_url}/v1.0/audit/activity-types",
            headers=auth_headers
        )
        
        if types_response.status_code == 200:
            types_data = json.loads(types_response.text)
            print(f"✅ Available activity types: {len(types_data['activity_types'])}")
            print(f"   Examples: {types_data['activity_types'][:5]}")
        
        # 5. Test logout (will create audit log)
        print("\n5. Testing Logout (creates audit log)...")
        logout_response = requests.post(
            f"{base_url}/v1.0/auth/logout",
            headers=auth_headers
        )
        
        if logout_response.status_code == 200:
            print("✅ Logout successful - audit log created")
    
    else:
        print(f"❌ Login failed: {login_response.text}")

if __name__ == "__main__":
    test_audit_logging()