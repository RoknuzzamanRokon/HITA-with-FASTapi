import requests
import json

def test_redoc_logo():
    """Test if ReDoc will display the logo"""
    
    print("Testing ReDoc logo configuration...")
    
    try:
        # Get the OpenAPI schema
        openapi_url = "http://127.0.0.1:8002/openapi.json"
        response = requests.get(openapi_url, timeout=10)
        
        if response.status_code == 200:
            openapi_data = response.json()
            
            # Check logo configuration
            info = openapi_data.get('info', {})
            logo = info.get('x-logo')
            
            print(f"API Title: {info.get('title', 'N/A')}")
            print(f"API Version: {info.get('version', 'N/A')}")
            
            if logo:
                print("\n✓ Logo configuration found:")
                print(f"  Logo URL: {logo.get('url')}")
                print(f"  Alt Text: {logo.get('altText')}")
                print(f"  Background Color: {logo.get('backgroundColor')}")
                print(f"  Link URL: {logo.get('href')}")
                
                # Test if the logo URL is accessible
                logo_url = f"http://127.0.0.1:8002{logo.get('url')}"
                logo_response = requests.get(logo_url, timeout=5)
                
                if logo_response.status_code == 200:
                    print(f"  ✓ Logo file is accessible ({len(logo_response.content)} bytes)")
                else:
                    print(f"  ✗ Logo file is not accessible (status: {logo_response.status_code})")
                
                print("\n🎉 ReDoc should display the logo!")
                print("Visit: http://127.0.0.1:8002/redoc")
                
            else:
                print("✗ No logo configuration found in OpenAPI schema")
                
        else:
            print(f"✗ Could not fetch OpenAPI schema: {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    test_redoc_logo()