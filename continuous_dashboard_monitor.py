#!/usr/bin/env python3
"""
Continuous dashboard monitoring script
Runs every minute to check dashboard access patterns
"""

import requests
import time
import schedule
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dashboard_monitor.log'),
        logging.StreamHandler()
    ]
)

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust to your server URL
USERNAME = "roman"
PASSWORD = "roman123"  # You'll need the actual password

def check_dashboard_access():
    """Check dashboard access and log results"""
    
    try:
        print(f"🔍 Checking dashboard access at {datetime.now()}")
        
        # Try to login
        login_response = requests.post(
            f"{BASE_URL}/v1.0/auth/token",
            data={
                "username": USERNAME,
                "password": PASSWORD
            },
            timeout=10
        )
        
        if login_response.status_code == 200:
            token_data = login_response.json()
            token = token_data["access_token"]
            
            # Try dashboard access
            dashboard_response = requests.get(
                f"{BASE_URL}/v1.0/dashboard/stats",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            logging.info(f"Dashboard check - Status: {dashboard_response.status_code}")
            
            if dashboard_response.status_code == 403:
                logging.warning("User still doesn't have dashboard permissions")
            elif dashboard_response.status_code == 200:
                logging.info("✅ Dashboard access successful")
            else:
                logging.error(f"Unexpected dashboard response: {dashboard_response.status_code}")
                
        else:
            logging.error(f"Login failed: {login_response.status_code}")
            
    except requests.exceptions.Timeout:
        logging.error("❌ Request timeout - server might be down")
    except requests.exceptions.ConnectionError:
        logging.error("❌ Connection error - server might be down")
    except Exception as e:
        logging.error(f"❌ Unexpected error: {e}")

def run_continuous_monitoring():
    """Run continuous monitoring"""
    
    print("🚀 Starting continuous dashboard monitoring...")
    print("📊 Will check every minute. Press Ctrl+C to stop.")
    
    # Schedule the job every minute
    schedule.every(1).minutes.do(check_dashboard_access)
    
    # Run initial check
    check_dashboard_access()
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user")
        logging.info("Dashboard monitoring stopped")

if __name__ == "__main__":
    run_continuous_monitoring()