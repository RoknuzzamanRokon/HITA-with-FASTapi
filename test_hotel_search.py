"""
Test script for the search-hotel-with-location endpoint
"""
import requests
import json

# Test data
test_request = {
    "lat": "18.17",
    "lon": "-63.14",
    "radious": "10",
    "supplier": ["agoda"],
    "country_code": "AI"
}

# Make request to the endpoint
# Note: Update the URL to match your server
url = "http://localhost:8000/v1.0/locations/search-hotel-with-location"

try:
    response = requests.post(url, json=test_request)
    print(f"Status Code: {response.status_code}")
    print(f"\nResponse:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {str(e)}")
