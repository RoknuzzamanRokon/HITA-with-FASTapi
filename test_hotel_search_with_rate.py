"""
Test script for the search-hotel-with-location-with-rate endpoint

SECURITY REQUIREMENTS:
- Valid authentication token (Bearer token)
- IP address must be whitelisted for the user
- User must have permission for the requested supplier(s)
"""
import requests
import json

# Test data - Request multiple suppliers
# Note: If user doesn't have permission for some suppliers, 
# they will be filtered out and only authorized suppliers will be searched
test_request = {
    "lat": "42.5777",
    "lon": "1.47909",
    "radius": "10",
    "supplier": ["agoda", "hotelbeds", "tbohotel"],  # Multiple suppliers
    "country_code": "AD"
}

# Authentication token - REPLACE WITH YOUR ACTUAL TOKEN
# To get a token, login via /v1.0/auth/login endpoint
AUTH_TOKEN = "your_bearer_token_here"

# Make request to the endpoint
# Note: Update the URL to match your server
url = "http://localhost:8000/v1.0/locations/search-hotel-with-location-with-rate"

# Headers with authentication
headers = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, json=test_request, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"\nResponse:")
    print(json.dumps(response.json(), indent=2))
    
    # Verify the response structure
    if response.status_code == 200:
        data = response.json()
        print(f"\n✓ Total hotels found: {data.get('total_hotels', 0)}")
        
        if data.get('total_hotels', 0) == 0:
            print("\n⚠️ No hotels found - Possible reasons:")
            print("  1. No hotels in the specified radius")
            print("  2. User has no permission for any of the requested suppliers")
            print("  3. Country code or supplier data not available")
        elif data.get('hotels'):
            first_hotel = data['hotels'][0]
            print(f"\n✓ First hotel details:")
            print(f"  - Name: {first_hotel.get('name')}")
            print(f"  - Room: {first_hotel.get('rName')}")
            print(f"  - Total: ${first_hotel.get('total')}")
            print(f"  - Fare: ${first_hotel.get('fare')}")
            print(f"  - Tax: ${first_hotel.get('tax')}")
            print(f"  - Fees: ${first_hotel.get('fees')}")
            
            # Show which suppliers returned data
            suppliers_found = set()
            for hotel in data['hotels']:
                for supplier in test_request['supplier']:
                    if supplier in hotel:
                        suppliers_found.add(supplier)
            
            if suppliers_found:
                print(f"\n✓ Data returned from suppliers: {', '.join(suppliers_found)}")
                requested_suppliers = set(test_request['supplier'])
                missing_suppliers = requested_suppliers - suppliers_found
                if missing_suppliers:
                    print(f"⚠️ No data from suppliers (no permission or no data): {', '.join(missing_suppliers)}")
    elif response.status_code == 403:
        print("\n❌ Access Denied - Possible reasons:")
        print("  1. IP address not whitelisted")
        print("  2. Invalid authentication token")
    elif response.status_code == 401:
        print("\n❌ Authentication Failed - Please provide a valid token")
            
except Exception as e:
    print(f"Error: {str(e)}")
