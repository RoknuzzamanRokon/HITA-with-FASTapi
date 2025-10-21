import requests

# Correct login endpoint
url = "http://127.0.0.1:8000/v1.0/auth/token"

payload = 'username=roman&password=roman123'
headers = {'Content-Type': 'application/x-www-form-urlencoded'}

print("Testing login with SecurityMiddleware...")
response = requests.request("POST", url, headers=headers, data=payload)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code == 200:
    print("✅ Login successful!")
    import json
    token_data = json.loads(response.text)
    print(f"Access Token: {token_data.get('access_token', 'N/A')[:50]}...")
else:
    print("❌ Login failed - check username/password or user exists")