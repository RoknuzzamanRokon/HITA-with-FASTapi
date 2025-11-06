#!/usr/bin/env python3
"""
Test the optimized endpoints to verify performance improvements.
"""

import requests
import time
import json

# Your server URL - adjust if different
BASE_URL = "http://127.0.0.1:8000/v1.0/locations"

def test_endpoint(name, url, timeout=60):
    """Test an endpoint and measure performance."""
    print(f"\n🚀 Testing {name}")
    print(f"URL: {url}")
    
    try:
        start_time = time.time()
        response = requests.get(url, timeout=timeout)
        end_time = time.time()
        
        duration = end_time - start_time
        
        if response.status_code == 200:
            data = response.json()
            total_countries = data.get('total_country', 0)
            
            print(f"✅ SUCCESS - {duration:.2f} seconds")
            print(f"📊 Countries: {total_countries}")
            
            if 'countries' in data and len(data['countries']) > 0:
                total_cities = sum(country.get('total', 0) for country in data['countries'])
                print(f"🏙️  Total Cities: {total_cities}")
                
                # Show sample
                sample = data['countries'][0]
                print(f"📋 Sample: {sample['country_name']} ({sample['total']} cities)")
                print(f"   Cities: {', '.join(sample['city_name'][:3])}{'...' if len(sample['city_name']) > 3 else ''}")
            
            # Performance rating
            if duration < 1:
                print("🚀 EXCELLENT: Lightning fast!")
            elif duration < 5:
                print("✅ VERY GOOD: Fast response")
            elif duration < 15:
                print("⚠️  MODERATE: Acceptable but could be better")
            else:
                print("❌ SLOW: Needs more optimization")
                
        else:
            print(f"❌ FAILED: HTTP {response.status_code}")
            print(f"Error: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print(f"⏰ TIMEOUT: Request took longer than {timeout} seconds")
    except requests.exceptions.ConnectionError:
        print(f"🔌 CONNECTION ERROR: Cannot connect to {BASE_URL}")
        print("Make sure your FastAPI server is running!")
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")

def main():
    print("🔥 TESTING OPTIMIZED ENDPOINTS")
    print("=" * 40)
    
    # Test endpoints in order of expected performance
    endpoints = [
        ("Sample Endpoint (Ultra-Fast)", f"{BASE_URL}/cities_with_countries/sample", 5),
        ("Turbo Endpoint (New!)", f"{BASE_URL}/cities_with_countries/turbo", 10),
        ("Lightning Endpoint", f"{BASE_URL}/cities_with_countries/lightning", 30),
        ("Cached Endpoint", f"{BASE_URL}/cities_with_countries", 60),
    ]
    
    for name, url, timeout in endpoints:
        test_endpoint(name, url, timeout)
        print("-" * 50)
    
    print("\n🎯 RECOMMENDATIONS:")
    print("✅ Use /sample for development and testing")
    print("✅ Use /lightning for production with reasonable limits")
    print("✅ Use /cities_with_countries for full data with caching")
    print("✅ The cached version should be instant on 2nd+ requests")

if __name__ == "__main__":
    main()