#!/usr/bin/env python3
"""
Test script for the new /find_match_data_without_push endpoint

This script demonstrates how to use the new endpoint that gets hotel data
directly from /hotel/details without requiring the /hotel/pushhotel step.
"""

import requests
import json

def test_without_push_endpoint():
    """Test the new find_match_data_without_push endpoint"""
    
    # API endpoint
    base_url = "http://127.0.0.1:8001"  # Adjust port if needed
    endpoint = f"{base_url}/v1.0/ml_mapping/find_match_data_without_push"
    
    # Test data
    test_data = {
        "supplier_name": "agoda",
        "hotel_id": "297844"
    }
    
    print("="*60)
    print("TESTING: /find_match_data_without_push endpoint")
    print("="*60)
    print(f"URL: {endpoint}")
    print(f"Payload: {json.dumps(test_data, indent=2)}")
    print("="*60)
    
    try:
        # Make the API request
        response = requests.post(
            endpoint,
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print("\nResponse:")
            print(json.dumps(result, indent=2))
            
            # Extract key information
            if result and len(result) > 0:
                hotel_info = result[0]["find_hotel"]
                print(f"\n📋 SUMMARY:")
                print(f"Hotel Name: {hotel_info['api_data']['name']}")
                print(f"Matched Name: {hotel_info['matched_data']['name']}")
                print(f"Confidence Score: {hotel_info['matching_info']['confidence_score']}")
                print(f"ITTID: {hotel_info['ittid']}")
        else:
            print("❌ FAILED!")
            print(f"Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ CONNECTION ERROR!")
        print("Make sure the FastAPI server is running on port 8001")
    except requests.exceptions.Timeout:
        print("❌ TIMEOUT ERROR!")
        print("The request took too long to complete")
    except Exception as e:
        print(f"❌ ERROR: {e}")

def test_health_endpoint():
    """Test the health endpoint to verify the new mapper is available"""
    
    base_url = "http://127.0.0.1:8001"
    endpoint = f"{base_url}/v1.0/ml_mapping/health"
    
    print("\n" + "="*60)
    print("TESTING: Health endpoint")
    print("="*60)
    
    try:
        response = requests.get(endpoint, timeout=10)
        
        if response.status_code == 200:
            health_data = response.json()
            print("✅ Health check successful!")
            print(f"Service: {health_data.get('service')}")
            print(f"Status: {health_data.get('status')}")
            print(f"HotelMapper Available: {health_data.get('hotel_mapper_available')}")
            print(f"HotelMapperWithoutPush Available: {health_data.get('hotel_mapper_without_push_available')}")
            
            if 'endpoints' in health_data:
                print("\nAvailable Endpoints:")
                for endpoint_name, description in health_data['endpoints'].items():
                    print(f"  - {endpoint_name}: {description}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Health check error: {e}")

if __name__ == "__main__":
    # Test health endpoint first
    test_health_endpoint()
    
    # Test the new endpoint
    test_without_push_endpoint()
    
    print("\n" + "="*60)
    print("COMPARISON: With Push vs Without Push")
    print("="*60)
    print("WITH PUSH (/find_match_data):")
    print("  1. POST to /hotel/pushhotel")
    print("  2. POST to /hotel/details")
    print("  3. Match with CSV data")
    print("  ⏱️  Slower (2 API calls)")
    print("")
    print("WITHOUT PUSH (/find_match_data_without_push):")
    print("  1. POST to /hotel/details directly")
    print("  2. Match with CSV data")
    print("  ⚡ Faster (1 API call)")
    print("  🔒 More reliable (no push dependency)")