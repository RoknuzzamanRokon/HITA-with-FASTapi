import requests
import time

def test_docs_after_fix():
    """Test documentation endpoints after disabling custom OpenAPI"""
    
    print("Testing documentation endpoints...")
    
    endpoints = [
        {"url": "http://127.0.0.1:8002/docs", "name": "Swagger UI"},
        {"url": "http://127.0.0.1:8002/redoc", "name": "ReDoc"},
        {"url": "http://127.0.0.1:8002/openapi.json", "name": "OpenAPI JSON"}
    ]
    
    for endpoint in endpoints:
        try:
            print(f"\nTesting {endpoint['name']}...")
            response = requests.get(endpoint['url'], timeout=10)
            
            print(f"Status Code: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")
            print(f"Content Length: {len(response.content)} bytes")
            
            if response.status_code == 200:
                if 'json' in endpoint['name'].lower():
                    # For JSON endpoint, check if it's valid JSON
                    try:
                        json_data = response.json()
                        print(f"✓ Valid JSON with {len(json_data)} keys")
                        print(f"OpenAPI version: {json_data.get('openapi', 'N/A')}")
                        print(f"Title: {json_data.get('info', {}).get('title', 'N/A')}")
                    except:
                        print("✗ Invalid JSON response")
                else:
                    # For HTML endpoints, check if content exists
                    if len(response.content) > 1000:  # Reasonable size for docs page
                        print(f"✓ {endpoint['name']} loaded successfully")
                    else:
                        print(f"⚠ {endpoint['name']} content seems too small")
            else:
                print(f"✗ {endpoint['name']} failed with status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"✗ Cannot connect to {endpoint['name']} - is the server running?")
        except Exception as e:
            print(f"✗ Error testing {endpoint['name']}: {e}")

if __name__ == "__main__":
    test_docs_after_fix()