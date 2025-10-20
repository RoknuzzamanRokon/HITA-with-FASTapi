#!/usr/bin/env python3
"""
Test script for superadmin user list caching functionality
Tests the enhanced caching behavior for /v1.0/users/list endpoint
"""

import requests
import time
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
SUPERADMIN_CREDENTIALS = {
    "username": "superadmin",  # Replace with actual superadmin username
    "password": "your_password"  # Replace with actual password
}

def get_auth_token(username: str, password: str) -> str:
    """Get authentication token"""
    try:
        response = requests.post(
            f"{BASE_URL}/v1.0/auth/login",
            data={"username": username, "password": password}
        )
        
        if response.status_code == 200:
            token_data = response.json()
            return token_data.get("access_token")
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None

def test_superadmin_cache():
    """Test superadmin caching functionality"""
    
    print("🔐 Testing Superadmin User List Caching")
    print("=" * 50)
    
    # Get authentication token
    print("1. Getting authentication token...")
    token = get_auth_token(
        SUPERADMIN_CREDENTIALS["username"], 
        SUPERADMIN_CREDENTIALS["password"]
    )
    
    if not token:
        print("❌ Failed to get authentication token")
        return
    
    print("✅ Authentication successful")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: Check cache status
    print("\n2. Checking cache status...")
    try:
        cache_status_response = requests.get(
            f"{BASE_URL}/v1.0/users/cache/status",
            headers=headers
        )
        
        if cache_status_response.status_code == 200:
            cache_data = cache_status_response.json()
            print("✅ Cache status retrieved:")
            print(f"   Cache Available: {cache_data['data']['cache_available']}")
            print(f"   Superadmin Cache Ready: {cache_data['data'].get('superadmin_cache_ready', False)}")
        else:
            print(f"⚠️  Cache status check failed: {cache_status_response.status_code}")
            
    except Exception as e:
        print(f"❌ Cache status error: {e}")
    
    # Test 2: Warm cache
    print("\n3. Warming cache...")
    try:
        warm_response = requests.post(
            f"{BASE_URL}/v1.0/users/cache/warm",
            headers=headers
        )
        
        if warm_response.status_code == 200:
            print("✅ Cache warming successful")
        else:
            print(f"⚠️  Cache warming failed: {warm_response.status_code}")
            
    except Exception as e:
        print(f"❌ Cache warming error: {e}")
    
    # Test 3: First request (should cache data)
    print("\n4. First request to /v1.0/users/list (should cache data)...")
    start_time = time.time()
    
    try:
        first_response = requests.get(
            f"{BASE_URL}/v1.0/users/list?page=1&limit=10",
            headers=headers
        )
        
        first_duration = time.time() - start_time
        
        if first_response.status_code == 200:
            first_data = first_response.json()
            cache_info = first_data.get('data', {}).get('cache_info', {})
            
            print(f"✅ First request successful ({first_duration:.3f}s)")
            print(f"   Cached: {cache_info.get('cached', 'Unknown')}")
            print(f"   Cache Key: {cache_info.get('cache_key', 'N/A')}")
            print(f"   Users Count: {len(first_data.get('data', {}).get('users', []))}")
            
        else:
            print(f"❌ First request failed: {first_response.status_code}")
            return
            
    except Exception as e:
        print(f"❌ First request error: {e}")
        return
    
    # Test 4: Second request (should use cache)
    print("\n5. Second request to /v1.0/users/list (should use cache)...")
    time.sleep(1)  # Small delay
    start_time = time.time()
    
    try:
        second_response = requests.get(
            f"{BASE_URL}/v1.0/users/list?page=1&limit=10",
            headers=headers
        )
        
        second_duration = time.time() - start_time
        
        if second_response.status_code == 200:
            second_data = second_response.json()
            cache_info = second_data.get('data', {}).get('cache_info', {})
            
            print(f"✅ Second request successful ({second_duration:.3f}s)")
            print(f"   Cached: {cache_info.get('cached', 'Unknown')}")
            print(f"   Cache Key: {cache_info.get('cache_key', 'N/A')}")
            print(f"   Users Count: {len(second_data.get('data', {}).get('users', []))}")
            
            # Performance comparison
            if first_duration > second_duration:
                improvement = ((first_duration - second_duration) / first_duration) * 100
                print(f"🚀 Performance improvement: {improvement:.1f}% faster")
            
        else:
            print(f"❌ Second request failed: {second_response.status_code}")
            
    except Exception as e:
        print(f"❌ Second request error: {e}")
    
    # Test 5: Different page (should cache separately)
    print("\n6. Request different page (should cache separately)...")
    start_time = time.time()
    
    try:
        page2_response = requests.get(
            f"{BASE_URL}/v1.0/users/list?page=2&limit=10",
            headers=headers
        )
        
        page2_duration = time.time() - start_time
        
        if page2_response.status_code == 200:
            page2_data = page2_response.json()
            cache_info = page2_data.get('data', {}).get('cache_info', {})
            
            print(f"✅ Page 2 request successful ({page2_duration:.3f}s)")
            print(f"   Cached: {cache_info.get('cached', 'Unknown')}")
            print(f"   Users Count: {len(page2_data.get('data', {}).get('users', []))}")
            
        else:
            print(f"❌ Page 2 request failed: {page2_response.status_code}")
            
    except Exception as e:
        print(f"❌ Page 2 request error: {e}")
    
    # Final cache status check
    print("\n7. Final cache status check...")
    try:
        final_cache_response = requests.get(
            f"{BASE_URL}/v1.0/users/cache/status",
            headers=headers
        )
        
        if final_cache_response.status_code == 200:
            final_cache_data = final_cache_response.json()
            print("✅ Final cache status:")
            print(f"   Superadmin Cache Ready: {final_cache_data['data'].get('superadmin_cache_ready', False)}")
            
            cache_keys = final_cache_data['data'].get('cache_keys_status', {})
            for key, status in cache_keys.items():
                if 'superadmin' in key:
                    print(f"   {key}: {'✅ Exists' if status.get('exists') else '❌ Missing'}")
        
    except Exception as e:
        print(f"❌ Final cache status error: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Superadmin cache testing completed!")
    print("\nKey Benefits:")
    print("• First superadmin request caches data for 15 minutes")
    print("• Subsequent superadmin requests use cached data (faster)")
    print("• Cache is shared among all superadmin users")
    print("• Separate cache keys for different pages/filters")

if __name__ == "__main__":
    test_superadmin_cache()