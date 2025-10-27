import requests
import time
import json

def test_optimized_performance():
    """Test the performance of optimized endpoints"""
    
    print("=== Testing Optimized Endpoint Performance ===")
    
    base_url = "http://127.0.0.1:8002/v1.0/ml_mapping"
    payload = {"supplier_name": "agoda"}
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1cnNhbXJva28iLCJ1c2VyX2lkIjoiMWEyMDNjY2RhNCIsInJvbGUiOiJzdXBlcl91c2VyIiwiZXhwIjoxNzYyOTk0ODE2LCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxNzYxMTk0ODE2fQ.XAE6ma_JFe7JDGPVahpbo80OLxHhe5lN2vjsvhgQA1s'
    }
    
    endpoints = [
        {
            "name": "get_not_mapped_hotel_id_list",
            "description": "Hotels in folder but NOT in database"
        },
        {
            "name": "get_not_update_content_hotel_id_list", 
            "description": "Hotels in database but NOT in folder"
        }
    ]
    
    # Clear cache first
    print("Clearing cache...")
    try:
        cache_response = requests.post(f"{base_url}/clear_cache", headers=headers)
        if cache_response.status_code == 200:
            print("✓ Cache cleared successfully")
        else:
            print(f"⚠ Cache clear failed: {cache_response.status_code}")
    except:
        print("⚠ Could not clear cache")
    
    # Test each endpoint multiple times
    for endpoint in endpoints:
        print(f"\n=== Testing {endpoint['name']} ===")
        print(f"Description: {endpoint['description']}")
        
        url = f"{base_url}/{endpoint['name']}"
        times = []
        
        for run in range(3):  # Test 3 times
            print(f"\nRun {run + 1}:")
            
            try:
                start_time = time.time()
                response = requests.post(url, headers=headers, json=payload, timeout=60)
                end_time = time.time()
                
                duration = end_time - start_time
                times.append(duration)
                
                print(f"  Status: {response.status_code}")
                print(f"  Duration: {duration:.2f} seconds")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"  Total hotel IDs: {result['total_hotel_id']}")
                    print(f"  First 5 IDs: {result['hotel_id'][:5]}")
                else:
                    print(f"  Error: {response.text}")
                    
            except requests.exceptions.Timeout:
                print(f"  ✗ Request timed out after 60 seconds")
                times.append(60)
            except Exception as e:
                print(f"  ✗ Error: {e}")
                times.append(999)
        
        # Calculate statistics
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"\n  Performance Summary:")
            print(f"    Average: {avg_time:.2f}s")
            print(f"    Fastest: {min_time:.2f}s")
            print(f"    Slowest: {max_time:.2f}s")
            
            if avg_time < 5:
                print(f"    ✓ Good performance!")
            elif avg_time < 15:
                print(f"    ⚠ Moderate performance")
            else:
                print(f"    ✗ Slow performance")

def test_cache_effectiveness():
    """Test if caching is working effectively"""
    
    print("\n=== Testing Cache Effectiveness ===")
    
    base_url = "http://127.0.0.1:8002/v1.0/ml_mapping"
    payload = {"supplier_name": "agoda"}
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1cnNhbXJva28iLCJ1c2VyX2lkIjoiMWEyMDNjY2RhNCIsInJvbGUiOiJzdXBlcl91c2VyIiwiZXhwIjoxNzYyOTk0ODE2LCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxNzYxMTk0ODE2fQ.XAE6ma_JFe7JDGPVahpbo80OLxHhe5lN2vjsvhgQA1s'
    }
    
    url = f"{base_url}/get_not_update_content_hotel_id_list"
    
    # Clear cache
    requests.post(f"{base_url}/clear_cache", headers=headers)
    
    # First call (should be slower - no cache)
    print("First call (no cache):")
    start_time = time.time()
    response1 = requests.post(url, headers=headers, json=payload)
    first_call_time = time.time() - start_time
    print(f"  Duration: {first_call_time:.2f}s")
    
    # Second call (should be faster - with cache)
    print("Second call (with cache):")
    start_time = time.time()
    response2 = requests.post(url, headers=headers, json=payload)
    second_call_time = time.time() - start_time
    print(f"  Duration: {second_call_time:.2f}s")
    
    # Calculate improvement
    if first_call_time > 0 and second_call_time > 0:
        improvement = ((first_call_time - second_call_time) / first_call_time) * 100
        print(f"  Cache improvement: {improvement:.1f}%")
        
        if improvement > 50:
            print("  ✓ Excellent cache performance!")
        elif improvement > 20:
            print("  ✓ Good cache performance")
        else:
            print("  ⚠ Limited cache benefit")

if __name__ == "__main__":
    test_optimized_performance()
    test_cache_effectiveness()