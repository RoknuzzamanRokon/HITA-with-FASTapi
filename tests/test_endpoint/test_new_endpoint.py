import requests
import json

def test_both_endpoints():
    """Test both endpoints"""
    
    base_url = "http://127.0.0.1:8002/v1.0/ml_mapping"
    payload = {"supplier_name": "agoda"}
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1cnNhbXJva28iLCJ1c2VyX2lkIjoiMWEyMDNjY2RhNCIsInJvbGUiOiJzdXBlcl91c2VyIiwiZXhwIjoxNzYyOTk0ODE2LCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxNzYxMTk0ODE2fQ.XAE6ma_JFe7JDGPVahpbo80OLxHhe5lN2vjsvhgQA1s'
    }
    
    endpoints = [
        {
            "name": "get_not_mapped_hotel_id_list",
            "description": "Hotels in folder but NOT in database (need mapping)",
            "expected_count": 25457
        },
        {
            "name": "get_not_update_content_hotel_id_list", 
            "description": "Hotels in database but NOT in folder (need content update)",
            "expected_count": 344755
        }
    ]
    
    for endpoint in endpoints:
        print(f"\n=== Testing {endpoint['name']} ===")
        print(f"Description: {endpoint['description']}")
        
        url = f"{base_url}/{endpoint['name']}"
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Success!")
                print(f"Supplier: {result['supplier_name']}")
                print(f"Total hotel IDs: {result['total_hotel_id']}")
                print(f"Expected: {endpoint['expected_count']}")
                print(f"First 10 hotel IDs: {result['hotel_id'][:10]}")
                
                if result['total_hotel_id'] == endpoint['expected_count']:
                    print("✓ Count matches expected value!")
                else:
                    print("⚠ Count doesn't match expected value")
                    
            else:
                print(f"✗ Error: {response.text}")
                
        except Exception as e:
            print(f"✗ Exception: {e}")

if __name__ == "__main__":
    test_both_endpoints()