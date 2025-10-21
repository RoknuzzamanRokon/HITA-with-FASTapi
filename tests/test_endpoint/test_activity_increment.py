import requests
import json
import time

base_url = "http://127.0.0.1:8000"

def check_activity_count(token, step_name):
    """Check current activity count"""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(f"{base_url}/v1.0/audit/activity-summary?days=30", headers=headers)
    
    if response.status_code == 200:
        data = json.loads(response.text)
        count = data['total_activities']
        print(f"{step_name}: total_activities = {count}")
        return count
    else:
        print(f"Error checking count: {response.text}")
        return 0

def test_activity_increment():
    """Test how activities increment step by step"""
    
    print("🔢 Testing Activity Count Increment")
    print("=" * 50)
    
    # Step 1: Login (this should create +1 activity)
    print("\n1. Performing Login...")
    login_data = 'username=roman&password=roman123'
    login_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    login_response = requests.post(f"{base_url}/v1.0/auth/token", data=login_data, headers=login_headers)
    
    if login_response.status_code == 200:
        token_data = json.loads(login_response.text)
        token = token_data.get('access_token')
        print("✅ Login successful")
        
        # Check count after login
        time.sleep(1)  # Give database time to update
        count1 = check_activity_count(token, "After Login")
        
        # Step 2: Get profile (this might create +1 activity)
        print("\n2. Getting Profile...")
        requests.get(f"{base_url}/v1.0/auth/me", headers={'Authorization': f'Bearer {token}'})
        time.sleep(1)
        count2 = check_activity_count(token, "After Get Profile")
        
        # Step 3: Get activity summary (this might create +1 activity)
        print("\n3. Getting Activity Summary...")
        requests.get(f"{base_url}/v1.0/audit/activity-summary", headers={'Authorization': f'Bearer {token}'})
        time.sleep(1)
        count3 = check_activity_count(token, "After Activity Summary")
        
        # Step 4: Logout (this should create +1 activity)
        print("\n4. Performing Logout...")
        requests.post(f"{base_url}/v1.0/auth/logout", headers={'Authorization': f'Bearer {token}'})
        time.sleep(1)
        
        # Use a new login to check final count
        login_response2 = requests.post(f"{base_url}/v1.0/auth/token", data=login_data, headers=login_headers)
        if login_response2.status_code == 200:
            token_data2 = json.loads(login_response2.text)
            token2 = token_data2.get('access_token')
            count4 = check_activity_count(token2, "After Logout + New Login")
        
        print(f"\n📊 Activity Progression:")
        print(f"   Start → Login: 0 → {count1} (+{count1})")
        print(f"   Login → Profile: {count1} → {count2} (+{count2-count1})")
        print(f"   Profile → Summary: {count2} → {count3} (+{count3-count2})")
        print(f"   Summary → Logout+Login: {count3} → {count4} (+{count4-count3})")
        
    else:
        print(f"❌ Login failed: {login_response.text}")

if __name__ == "__main__":
    test_activity_increment()