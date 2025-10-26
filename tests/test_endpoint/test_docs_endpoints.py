import requests

def test_documentation_endpoints():
    """Test if documentation endpoints are available"""
    
    ports = [8000, 8002]
    endpoints = [
        {"path": "/docs", "name": "Swagger UI"},
        {"path": "/redoc", "name": "ReDoc"},
        {"path": "/openapi.json", "name": "OpenAPI JSON"}
    ]
    
    for port in ports:
        print(f"\n=== Testing port {port} ===")
        
        for endpoint in endpoints:
            url = f"http://127.0.0.1:{port}{endpoint['path']}"
            
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    print(f"✓ {endpoint['name']}: {url}")
                else:
                    print(f"✗ {endpoint['name']}: {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                print(f"✗ {endpoint['name']}: Connection refused")
            except Exception as e:
                print(f"✗ {endpoint['name']}: {e}")

if __name__ == "__main__":
    test_documentation_endpoints()