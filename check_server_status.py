"""
Check Server Status and Configuration

This script checks if the server is running and if it loaded the new code.
"""

import requests
import sys

BASE_URL = "http://127.0.0.1:8001"

print("="*70)
print("SERVER STATUS CHECK")
print("="*70)

# Test 1: Is server running?
print("\n1. Checking if server is running...")
try:
    response = requests.get(f"{BASE_URL}/v1.0/health", timeout=2)
    print(f"   ✅ Server is running (Status: {response.status_code})")
except requests.exceptions.ConnectionError:
    print("   ❌ Server is NOT running!")
    print("\n   Please start the server:")
    print("   uvicorn main:app --host 0.0.0.0 --port 8001 --reload")
    sys.exit(1)
except requests.exceptions.Timeout:
    print("   ⚠️  Server is responding but VERY SLOW")
    print("   This suggests the OLD code is still running")
except Exception as e:
    print(f"   ❌ Error: {str(e)}")
    sys.exit(1)

# Test 2: Check server logs for export worker
print("\n2. Checking server configuration...")
print("   Please check your server terminal for these lines:")
print("   - 'INFO: Export worker initialized'")
print("   - 'INFO: ExportWorker initialized: max_workers=3'")
print()
print("   Do you see these lines? (This confirms new code is loaded)")

# Test 3: Quick export test
print("\n3. Testing export endpoint (quick test)...")
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyb24xMjMiLCJ1c2VyX2lkIjoiMmYwMTBmZTRjNSIsInJvbGUiOiJhZG1pbl91c2VyIiwiZXhwIjoxNzY1MDc0MDUxLCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxNzYzMjc0MDUxfQ.Nwg4K9gPqzFBfI8Zobuuqr66szghg6AVGkOk6iefUkk"

import time
start = time.time()

try:
    response = requests.post(
        f"{BASE_URL}/v1.0/export/supplier-summary",
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {TOKEN}'
        },
        json={
            "filters": {
                "suppliers": ["kiwihotel"],
                "include_country_breakdown": True
            },
            "format": "json"
        },
        timeout=10
    )
    
    elapsed_ms = (time.time() - start) * 1000
    
    print(f"   Response time: {elapsed_ms:.0f}ms")
    print(f"   Status code: {response.status_code}")
    
    if response.status_code == 200:
        try:
            data = response.json()
            if 'job_id' in data:
                print(f"   ✅ NEW CODE: Returns job_id = {data['job_id']}")
                print(f"   ✅ Export is async (background processing)")
                
                if elapsed_ms < 1000:
                    print(f"\n   ✅ ✅ ✅ SUCCESS! New code is working!")
                else:
                    print(f"\n   ⚠️  Response is slow but async")
            else:
                print(f"   ❌ OLD CODE: Returns data directly (not job_id)")
                print(f"   ❌ Server is running OLD code")
        except:
            print(f"   ❌ Unexpected response format")
    else:
        print(f"   ❌ Error response: {response.text[:200]}")
        
except requests.exceptions.Timeout:
    elapsed_ms = (time.time() - start) * 1000
    print(f"   ❌ TIMEOUT after {elapsed_ms:.0f}ms")
    print(f"   ❌ Server is running OLD CODE (blocking)")
except Exception as e:
    print(f"   ❌ Error: {str(e)}")

print("\n" + "="*70)
print("DIAGNOSIS")
print("="*70)

print("\nIf you see:")
print("  ✅ 'NEW CODE: Returns job_id' = Server restarted successfully!")
print("  ❌ 'OLD CODE' or 'TIMEOUT' = Server needs to be restarted")
print()
print("To restart:")
print("  1. Stop server (Ctrl+C in server terminal)")
print("  2. Start: uvicorn main:app --host 0.0.0.0 --port 8001 --reload")
print("  3. Look for 'Export worker initialized' in logs")
print("  4. Run this script again")
print("="*70)
