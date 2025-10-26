import requests

def test_logo_accessibility():
    """Test if the logo is accessible via the static files endpoint"""
    
    print("Testing logo accessibility...")
    
    # Test the logo URL
    logo_url = "http://127.0.0.1:8002/static/images/ittapilogo_1.png"
    
    try:
        response = requests.get(logo_url, timeout=10)
        print(f"Logo URL: {logo_url}")
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")
        print(f"Content Length: {len(response.content)} bytes")
        
        if response.status_code == 200:
            print("✓ Logo is accessible!")
        else:
            print("✗ Logo is not accessible")
            
    except Exception as e:
        print(f"✗ Error accessing logo: {e}")
    
    # Test OpenAPI schema to see if logo is included
    print("\nTesting OpenAPI schema for logo configuration...")
    
    try:
        openapi_url = "http://127.0.0.1:8002/openapi.json"
        response = requests.get(openapi_url, timeout=10)
        
        if response.status_code == 200:
            openapi_data = response.json()
            logo_config = openapi_data.get('info', {}).get('x-logo')
            
            if logo_config:
                print("✓ Logo configuration found in OpenAPI schema:")
                print(f"  URL: {logo_config.get('url')}")
                print(f"  Alt Text: {logo_config.get('altText')}")
                print(f"  Background: {logo_config.get('backgroundColor')}")
            else:
                print("✗ Logo configuration not found in OpenAPI schema")
        else:
            print(f"✗ Could not fetch OpenAPI schema: {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error checking OpenAPI schema: {e}")

if __name__ == "__main__":
    test_logo_accessibility()