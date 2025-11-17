"""
Test script for Export API Key Validation

This script demonstrates how to:
1. Validate an API key
2. Use the API key to access export endpoints
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "your_api_key_here"  # Replace with your actual API key

def test_api_key_validation():
    """Test the API key validation endpoint"""
    print("=" * 60)
    print("Testing API Key Validation")
    print("=" * 60)
    
    url = f"{BASE_URL}/v1.0/export/my-validation"
    headers = {
        "X-API-Key": API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("\n✓ API Key is valid!")
            return True
        else:
            print("\n✗ API Key validation failed!")
            return False
            
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        return False


def test_export_hotels():
    """Test hotel export endpoint with API key"""
    print("\n" + "=" * 60)
    print("Testing Hotel Export with API Key")
    print("=" * 60)
    
    url = f"{BASE_URL}/v1.0/export/hotels"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "format": "csv",
        "filters": {
            "suppliers": ["agoda"],
            "country_codes": ["US"]
        },
        "include_locations": True,
        "include_contacts": False,
        "include_mappings": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            job_id = response.json().get("job_id")
            print(f"\n✓ Export job created successfully!")
            print(f"Job ID: {job_id}")
            return job_id
        else:
            print("\n✗ Export job creation failed!")
            return None
            
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        return None


def test_export_status(job_id):
    """Test export status endpoint with API key"""
    print("\n" + "=" * 60)
    print("Testing Export Status Check")
    print("=" * 60)
    
    url = f"{BASE_URL}/v1.0/export/status/{job_id}"
    headers = {
        "X-API-Key": API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            status = response.json().get("status")
            print(f"\n✓ Export status: {status}")
            return True
        else:
            print("\n✗ Status check failed!")
            return False
            
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        return False


def test_without_api_key():
    """Test that endpoints reject requests without API key"""
    print("\n" + "=" * 60)
    print("Testing Request WITHOUT API Key (Should Fail)")
    print("=" * 60)
    
    url = f"{BASE_URL}/v1.0/export/my-validation"
    
    try:
        response = requests.get(url)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 401:
            print("\n✓ Correctly rejected request without API key!")
            return True
        else:
            print("\n✗ Should have rejected request without API key!")
            return False
            
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("EXPORT API KEY VALIDATION TEST SUITE")
    print("=" * 60)
    print(f"\nBase URL: {BASE_URL}")
    print(f"API Key: {API_KEY[:10]}..." if len(API_KEY) > 10 else f"API Key: {API_KEY}")
    
    # Test 1: Validate API key
    if not test_api_key_validation():
        print("\n⚠ API key validation failed. Please check your API key.")
        print("Continuing with other tests...\n")
    
    # Test 2: Test without API key (should fail)
    test_without_api_key()
    
    # Test 3: Export hotels
    job_id = test_export_hotels()
    
    # Test 4: Check export status (if job was created)
    if job_id:
        test_export_status(job_id)
    
    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()
