import requests

# Test different ports and check available routes
ports = [8000, 8002]

for port in ports:
    print(f"\n=== Testing port {port} ===")
    
    try:
        # Test health endpoint first
        health_url = f"http://127.0.0.1:{port}/v1.0/ml_mapping/health"
        response = requests.get(health_url)
        print(f"Health endpoint status: {response.status_code}")
        if response.status_code == 200:
            print("ML Mapping router is working on this port!")
            
            # Test our endpoint
            url = f"http://127.0.0.1:{port}/v1.0/ml_mapping/get_not_mapped_hotel_id_list"
            payload = {"supplier_name": "agoda"}
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(url, headers=headers, json=payload)
            print(f"Our endpoint status: {response.status_code}")
            print(f"Response: {response.text}")
            
        else:
            print(f"Health endpoint failed: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"Cannot connect to port {port}")
    except Exception as e:
        print(f"Error testing port {port}: {e}")

# Also test the docs endpoint to see all available routes
print("\n=== Testing docs endpoints ===")
for port in ports:
    try:
        docs_url = f"http://127.0.0.1:{port}/docs"
        response = requests.get(docs_url)
        print(f"Port {port} docs status: {response.status_code}")
        if response.status_code == 200:
            print(f"Docs available at: {docs_url}")
    except:
        print(f"Port {port} docs not available")