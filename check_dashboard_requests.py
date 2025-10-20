#!/usr/bin/env python3
"""
Script to help identify what's making dashboard requests
Can be run manually or scheduled to run every minute
"""

import requests
import time
from datetime import datetime
import sys

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust to your server URL
USERNAME = "roman"
PASSWORD = "roman123"  # You'll need the actual password

def check_dashboard_access():
    """Check if there are any active sessions or processes making dashboard requests"""
    
    print("🔍 Checking dashboard access patterns...")
    print(f"Time: {datetime.now()}")
    
    try:
        # Try to login as roman to see what happens
        login_response = requests.post(
            f"{BASE_URL}/v1.0/auth/token",
            data={
                "username": USERNAME,
                "password": PASSWORD
            },
            timeout=5
        )
        
        if login_response.status_code == 200:
            token_data = login_response.json()
            token = token_data["access_token"]
            
            print(f"✅ Successfully logged in as {USERNAME}")
            
            # Try dashboard access
            dashboard_response = requests.get(
                f"{BASE_URL}/v1.0/dashboard/stats",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            )
            
            print(f"📊 Dashboard response: {dashboard_response.status_code}")
            if dashboard_response.status_code == 403:
                print("❌ Confirmed: User doesn't have dashboard permissions")
            elif dashboard_response.status_code == 200:
                print("✅ Dashboard access successful!")
            else:
                print(f"⚠️ Unexpected response: {dashboard_response.status_code}")
            
        else:
            print(f"❌ Login failed: {login_response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def run_every_minute():
    """Run the check every minute continuously"""
    
    print("🚀 Starting continuous monitoring (every minute)")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            check_dashboard_access()
            print("-" * 50)
            time.sleep(60)  # Wait 60 seconds (1 minute)
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
        run_every_minute()
    else:
        check_dashboard_access()