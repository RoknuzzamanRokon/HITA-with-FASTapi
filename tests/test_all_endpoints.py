import requests
import json

base_url = "http://127.0.0.1:8000"

def test_endpoint(method, endpoint, data=None, headers=None, token=None):
    """Test endpoint and show security middleware in action"""
    url = f"{base_url}{endpoint}"
    
    if token:
        headers = headers or {}
        headers['Authorization'] = f'Bearer {token}'
    
    print(f"\n🔒 Testing: {method} {endpoint}")
    print("SecurityMiddleware will process this request...")
    
    if method == "POST":
        if headers and headers.get('Content-Type') == 'application/json':
            response = requests.post(url, data=data, headers=headers)
        else:
            response = requests.post(url, data=data, headers=headers)
    elif method == "GET":
        response = requests.get(url, headers=headers)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:200]}...")
    return response

# Test all your auth endpoints
print("🛡️  Testing All Endpoints with SecurityMiddleware")
print("=" * 50)

# 1. Register (will go through SecurityMiddleware)
register_data = {
    "username": "testuser2", 
    "email": "test2@example.com", 
    "password": "testpass123"
}
register_headers = {'Content-Type': 'application/json'}
test_endpoint("POST", "/v1.0/auth/register", json.dumps(register_data), register_headers)

# 2. Login (will go through SecurityMiddleware)
login_data = 'username=testuser&password=testpass123'
login_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
login_response = test_endpoint("POST", "/v1.0/auth/token", login_data, login_headers)

# Extract token if login successful
token = None
if login_response.status_code == 200:
    token_data = json.loads(login_response.text)
    token = token_data.get('access_token')
    print(f"✅ Got token: {token[:30]}...")

# 3. Get Profile (will go through SecurityMiddleware + JWT auth)
if token:
    test_endpoint("GET", "/v1.0/auth/me", token=token)

# 4. Logout (will go through SecurityMiddleware + JWT auth)
if token:
    test_endpoint("POST", "/v1.0/auth/logout", token=token)

print("\n🎯 All requests went through SecurityMiddleware!")
print("Check your server logs to see audit logging in action.")