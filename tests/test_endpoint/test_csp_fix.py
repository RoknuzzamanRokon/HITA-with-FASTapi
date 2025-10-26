import requests

def test_csp_fix():
    """Test if the CSP fix allows documentation to load properly"""
    
    print("Testing CSP fix for documentation endpoints...")
    
    endpoints = [
        {"url": "http://127.0.0.1:8002/docs", "name": "Swagger UI"},
        {"url": "http://127.0.0.1:8002/redoc", "name": "ReDoc"}
    ]
    
    for endpoint in endpoints:
        try:
            print(f"\nTesting {endpoint['name']}...")
            response = requests.get(endpoint['url'], timeout=10)
            
            print(f"Status Code: {response.status_code}")
            print(f"Content Length: {len(response.content)} bytes")
            
            # Check CSP header
            csp = response.headers.get('content-security-policy', 'Not found')
            print(f"CSP Header: {csp}")
            
            # Check if CDN domains are allowed
            required_domains = [
                'https://cdn.jsdelivr.net',
                'https://fonts.googleapis.com',
                'https://fonts.gstatic.com'
            ]
            
            for domain in required_domains:
                if domain in csp:
                    print(f"✓ {domain} is allowed in CSP")
                else:
                    print(f"✗ {domain} is NOT allowed in CSP")
            
            if response.status_code == 200 and len(response.content) > 800:
                print(f"✓ {endpoint['name']} should now work properly")
            else:
                print(f"⚠ {endpoint['name']} may still have issues")
                
        except Exception as e:
            print(f"✗ Error testing {endpoint['name']}: {e}")

if __name__ == "__main__":
    test_csp_fix()