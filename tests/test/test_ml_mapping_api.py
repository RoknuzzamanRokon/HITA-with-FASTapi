#!/usr/bin/env python3
"""
Test script for the ML mapping API endpoint
"""

import requests
import json
import sys
import os

# Test configuration
BASE_URL = "http://localhost:8000"  # Adjust this to your FastAPI server URL
ENDPOINT = "/v1.0/ml_mapping/find_match_data"

def test_single_hotel_mapping():
    """Test the single hotel mapping endpoint"""
    print("Testing single hotel mapping endpoint...")
    
    # Test data
    test_data = {
        "supplier_name": "agoda",
        "hotel_id": "297844"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}{ENDPOINT}",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("SUCCESS! Response:")
            print(json.dumps(result, indent=2))
            
            # Validate response structure
            if isinstance(result, list) and len(result) > 0:
                hotel_data = result[0]
                if "find_hotel" in hotel_data:
                    find_hotel = hotel_data["find_hotel"]
                    required_fields = ["Id", "ittid", "supplier_name", "hotel_id", "api_data", "matched_data", "matching_info"]
                    
                    missing_fields = [field for field in required_fields if field not in find_hotel]
                    if missing_fields:
                        print(f"WARNING: Missing fields in response: {missing_fields}")
                    else:
                        print("✓ Response structure is valid")
                        print(f"✓ Confidence Score: {find_hotel['matching_info']['confidence_score']}")
                        print(f"✓ Matched Hotel: {find_hotel['matched_data']['name']}")
                else:
                    print("ERROR: 'find_hotel' key not found in response")
            else:
                print("ERROR: Response is not a list or is empty")
                
        else:
            print(f"ERROR: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to the server. Make sure FastAPI is running.")
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out")
    except Exception as e:
        print(f"ERROR: {str(e)}")

def test_batch_hotel_mapping():
    """Test the batch hotel mapping endpoint"""
    print("\nTesting batch hotel mapping endpoint...")
    
    # Test data
    test_data = {
        "supplier_name": "agoda",
        "hotel_ids": ["297844", "64845042"]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/v1.0/ml_mapping/batch_find_match_data",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("SUCCESS! Batch Response:")
            print(f"Total Hotels: {result['summary']['total_hotels']}")
            print(f"Successful: {result['summary']['successful']}")
            print(f"Failed: {result['summary']['failed']}")
            
            if result['successful_mappings']:
                print("\nFirst successful mapping:")
                print(json.dumps(result['successful_mappings'][0], indent=2))
                
        else:
            print(f"ERROR: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")

def test_health_endpoint():
    """Test the health check endpoint"""
    print("\nTesting health endpoint...")
    
    try:
        response = requests.get(f"{BASE_URL}/v1.0/ml_mapping/health")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("Health Check Response:")
            print(json.dumps(result, indent=2))
        else:
            print(f"ERROR: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")

def test_supported_suppliers():
    """Test the supported suppliers endpoint"""
    print("\nTesting supported suppliers endpoint...")
    
    try:
        response = requests.get(f"{BASE_URL}/v1.0/ml_mapping/supported_suppliers")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("Supported Suppliers:")
            print(json.dumps(result, indent=2))
        else:
            print(f"ERROR: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    print("="*60)
    print("ML MAPPING API TESTS")
    print("="*60)
    print(f"Testing against: {BASE_URL}")
    print("Make sure your FastAPI server is running!")
    print("="*60)
    
    test_health_endpoint()
    test_supported_suppliers()
    test_single_hotel_mapping()
    test_batch_hotel_mapping()
    
    print("\n" + "="*60)
    print("TESTS COMPLETED")
    print("="*60)