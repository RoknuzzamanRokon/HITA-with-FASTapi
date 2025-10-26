import requests

def debug_swagger_issue():
    """Debug Swagger UI specific issues"""
    
    print("=== Debugging Swagger UI Issue ===")
    
    # Test both ports
    ports = [8002, 8003]
    
    for port in ports:
        print(f"\n--- Testing port {port} ---")
        
        try:
            # Test Swagger UI
            swagger_url = f"http://127.0.0.1:{port}/docs"
            response = requests.get(swagger_url, timeout=10)
            
            print(f"Swagger UI Status: {response.status_code}")
            print(f"Content Length: {len(response.content)} bytes")
            
            # Check CSP header
            csp = response.headers.get('content-security-policy', 'Not found')
            print(f"CSP: {csp}")
            
            # Test ReDoc for comparison
            redoc_url = f"http://127.0.0.1:{port}/redoc"
            redoc_response = requests.get(redoc_url, timeout=10)
            
            print(f"ReDoc Status: {redoc_response.status_code}")
            print(f"ReDoc Content Length: {len(redoc_response.content)} bytes")
            
            # Test OpenAPI JSON
            openapi_url = f"http://127.0.0.1:{port}/openapi.json"
            openapi_response = requests.get(openapi_url, timeout=10)
            
            print(f"OpenAPI JSON Status: {openapi_response.status_code}")
            print(f"OpenAPI JSON Length: {len(openapi_response.content)} bytes")
            
            # Check if OpenAPI JSON is valid
            if openapi_response.status_code == 200:
                try:
                    openapi_data = openapi_response.json()
                    print(f"OpenAPI Title: {openapi_data.get('info', {}).get('title', 'N/A')}")
                    print(f"OpenAPI Paths Count: {len(openapi_data.get('paths', {}))}")
                except:
                    print("OpenAPI JSON is invalid")
            
        except requests.exceptions.ConnectionError:
            print(f"Cannot connect to port {port}")
        except Exception as e:
            print(f"Error testing port {port}: {e}")

def test_swagger_resources():
    """Test if Swagger UI resources are accessible"""
    
    print("\n=== Testing Swagger UI Resources ===")
    
    # Test the external resources that Swagger UI needs
    resources = [
        "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"
    ]
    
    for resource in resources:
        try:
            response = requests.get(resource, timeout=10)
            print(f"{resource}: {response.status_code} ({len(response.content)} bytes)")
        except Exception as e:
            print(f"{resource}: Error - {e}")

if __name__ == "__main__":
    debug_swagger_issue()
    test_swagger_resources()