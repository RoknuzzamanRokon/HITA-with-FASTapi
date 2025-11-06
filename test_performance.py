#!/usr/bin/env python3
"""
Performance Testing Script for Cities with Countries Endpoints

Run this script to test the performance of different endpoint versions.
"""

import requests
import time
import json

# Configuration
BASE_URL = "http://localhost:8000/v1.0/locations"  # Adjust to your server URL

def test_endpoint(endpoint_name, url):
    """Test a single endpoint and measure performance."""
    print(f"\n🚀 Testing {endpoint_name}...")
    print(f"URL: {url}")
    
    try:
        start_time = time.time()
        response = requests.get(url, timeout=300)  # 5 minute timeout
        end_time = time.time()
        
        duration = end_time - start_time
        
        if response.status_code == 200:
            data = response.json()
            total_countries = data.get('total_country', 0)
            total_cities = sum(country.get('total', 0) for country in data.get('countries', []))
            
            print(f"✅ SUCCESS")
            print(f"⏱️  Duration: {duration:.2f} seconds")
            print(f"🌍 Countries: {total_countries}")
            print(f"🏙️  Total Cities: {total_cities}")
            
            # Show sample data
            if data.get('countries') and len(data['countries']) > 0:
                sample_country = data['countries'][0]
                print(f"📋 Sample: {sample_country['country_name']} ({sample_country['total']} cities)")
                
        else:
            print(f"❌ FAILED: HTTP {response.status_code}")
            print(f"⏱️  Duration: {duration:.2f} seconds")
            print(f"Error: {response.text[:200]}...")
            
    except requests.exceptions.Timeout:
        print(f"⏰ TIMEOUT: Request took longer than 5 minutes")
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")

def main():
    """Test all endpoint versions."""
    print("🔥 PERFORMANCE TESTING FOR CITIES WITH COUNTRIES ENDPOINTS")
    print("=" * 60)
    
    endpoints = [
        ("Sample Version (FASTEST)", f"{BASE_URL}/cities_with_countries/sample"),
        ("Lightning Version", f"{BASE_URL}/cities_with_countries/lightning"),
        ("Cached Version", f"{BASE_URL}/cities_with_countries"),
        ("Fast Version", f"{BASE_URL}/cities_with_countries/fast"),
    ]
    
    results = []
    
    for name, url in endpoints:
        test_endpoint(name, url)
        print("-" * 40)
    
    print("\n🎯 RECOMMENDATIONS:")
    print("1. Use /sample for immediate testing (fastest)")
    print("2. Run CRITICAL_PERFORMANCE_FIX.sql for production speed")
    print("3. Use /cities_with_countries for production (cached)")
    print("4. Use /lightning if cache is not working")

if __name__ == "__main__":
    main()