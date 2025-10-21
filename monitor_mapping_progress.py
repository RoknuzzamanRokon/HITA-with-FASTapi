#!/usr/bin/env python3
"""
Monitor the progress of the mapping data insertion process
"""

import json
import time
import os
from datetime import datetime

def monitor_progress():
    """Monitor the mapping progress in real-time"""
    print("📊 Mapping Progress Monitor")
    print("=" * 50)
    
    last_offset = 0
    last_time = time.time()
    
    try:
        while True:
            try:
                # Check if progress file exists
                if not os.path.exists("mapping_progress.json"):
                    print("⏳ Waiting for progress file to be created...")
                    time.sleep(5)
                    continue
                
                # Read progress
                with open("mapping_progress.json", "r") as f:
                    progress = json.load(f)
                
                current_time = time.time()
                current_offset = progress.get("offset", 0)
                
                # Calculate rate
                time_diff = current_time - last_time
                offset_diff = current_offset - last_offset
                rate = offset_diff / time_diff if time_diff > 0 else 0
                
                # Display progress
                timestamp = datetime.fromtimestamp(progress.get("timestamp", current_time))
                print(f"\n🕒 Last Update: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"📍 Current Offset: {current_offset:,}")
                print(f"✅ Successful: {progress.get('success_count', 0):,}")
                print(f"⚠️ Not Found: {progress.get('not_found_count', 0):,}")
                print(f"❌ Errors: {progress.get('error_count', 0):,}")
                print(f"📊 Total Processed: {progress.get('success_count', 0) + progress.get('not_found_count', 0) + progress.get('error_count', 0):,}")
                print(f"⚡ Processing Rate: {rate:.1f} records/second")
                
                # Update for next iteration
                last_offset = current_offset
                last_time = current_time
                
                time.sleep(10)  # Update every 10 seconds
                
            except json.JSONDecodeError:
                print("⚠️ Progress file is being written, retrying...")
                time.sleep(2)
            except Exception as e:
                print(f"❌ Error reading progress: {e}")
                time.sleep(5)
                
    except KeyboardInterrupt:
        print("\n👋 Monitor stopped by user")

if __name__ == "__main__":
    monitor_progress()