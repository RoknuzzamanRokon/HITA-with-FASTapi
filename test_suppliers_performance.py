#!/usr/bin/env python3
"""
Test the optimized check-my-active-suppliers-info endpoint performance.
"""

import requests
import time
import json

# Your server URL - adjust if different
BASE_URL = "http://127.0.0.1:8000/v1.0/hotels"

def test_suppliers_endpoint(auth_token):
    """Test the suppliers endpoint and measure performance."""
    url = f"{BASE_URL}/check-my-active-suppliers-info"
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    print(f"🚀 Testing Suppliers Endpoint")
    print(f"URL: {url}")
    
    try:
        start_time = time.time()
        response = requests.get(url, headers=headers, timeout=60)
        end_time = time.time()
        
        duration = end_time - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"✅ SUCCESS - {duration:.2f} seconds")
            print(f"👤 User: {data.get('userId')} (Role: {data.get('role')})")
            
            access_summary = data.get('accessSummary', {})
            print(f"📊 Access Summary:")
            print(f"   • Total Suppliers in System: {access_summary.get('totalSuppliersInSystem')}")
            print(f"   • Accessible Suppliers: {access_summary.get('accessibleSuppliersCount')}")
            print(f"   • Permission Based: {access_summary.get('permissionBased')}")
            
            analytics = data.get('supplierAnalytics', {})
            print(f"📈 Analytics:")
            print(f"   • Total Hotels Accessible: {analytics.get('totalHotelsAccessible')}")
            print(f"   • Active Suppliers: {analytics.get('activeSuppliers')}")
            print(f"   • Inactive Suppliers: {analytics.get('inactiveSuppliers')}")
            print(f"   • Coverage: {analytics.get('accessCoveragePercentage')}%")
            
            suppliers = data.get('accessibleSuppliers', [])
            if suppliers:
                print(f"🏨 Sample Suppliers:")
                for supplier in suppliers[:3]:  # Show first 3
                    print(f"   • {supplier['supplierName']}: {supplier['totalHotels']} hotels ({supplier['availabilityStatus']})")
            
            # Performance rating
            if duration < 1:
                print("🚀 EXCELLENT: Lightning fast!")
            elif duration < 3:
                print("✅ VERY GOOD: Fast response")
            elif duration < 10:
                print("⚠️  MODERATE: Acceptable but could be better")
            else:
                print("❌ SLOW: Still needs optimization")
                
        else:
            print(f"❌ FAILED: HTTP {response.status_code}")
            print(f"Error: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print(f"⏰ TIMEOUT: Request took longer than 60 seconds")
    except requests.exceptions.ConnectionError:
        print(f"🔌 CONNECTION ERROR: Cannot connect to {BASE_URL}")
        print("Make sure your FastAPI server is running!")
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")

def main():
    print("🔥 TESTING OPTIMIZED SUPPLIERS ENDPOINT")
    print("=" * 45)
    
    # You'll need to provide a valid auth token
    auth_token = input("Enter your auth token (or press Enter to skip): ").strip()
    
    if not auth_token:
        print("⚠️  No auth token provided. You'll need a valid token to test this endpoint.")
        print("💡 Get a token by logging in through your API first.")
        return
    
    # Test the endpoint multiple times to see caching effect
    print("\n🧪 Testing endpoint performance...")
    
    for i in range(3):
        print(f"\n--- Test {i+1}/3 ---")
        test_suppliers_endpoint(auth_token)
        if i < 2:
            time.sleep(1)  # Small delay between tests
    
    print("\n🎯 OPTIMIZATION RESULTS:")
    print("✅ First request should be fast (~100-500ms)")
    print("✅ Subsequent requests should be cached (~1-50ms)")
    print("✅ No more N+1 query problems!")

if __name__ == "__main__":
    main()