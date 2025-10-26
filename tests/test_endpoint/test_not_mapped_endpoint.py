#!/usr/bin/env python3
"""
Test script for the get_not_mapped_hotel_id_list endpoint
"""

import requests
import json

def test_not_mapped_endpoint():
    """Test the new endpoint"""
    
    # Endpoint URL (adjust if your server runs on different port)
    url = "http://localhost:8000/v1.0/ml_mapping/get_not_mapped_hotel_id_list"
    
    # Test payload
    payload = {
        "supplier_name": "agoda"
    }
    
    try:
        print("Testing get_not_mapped_hotel_id_list endpoint...")
        print(f"URL: {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Make the request
        response = requests.post(url, json=payload)
        
        print(f"\nResponse Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\nSuccess! Response:")
            print(json.dumps(result, indent=2))
            
            # Print summary
            print(f"\nSummary:")
            print(f"Supplier: {result.get('supplier_name')}")
            print(f"Total unmapped hotel IDs: {result.get('total_hotel_id')}")
            print(f"First 10 hotel IDs: {result.get('hotel_id', [])[:10]}")
            
        else:
            print(f"\nError Response:")
            try:
                error_detail = response.json()
                print(json.dumps(error_detail, indent=2))
            except:
                print(response.text)
                
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Make sure the FastAPI server is running on localhost:8000")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_not_mapped_endpoint()