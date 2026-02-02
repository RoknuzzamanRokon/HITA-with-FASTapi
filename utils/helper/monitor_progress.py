#!/usr/bin/env python3
"""
Real-time monitoring script for hotel data insertion progress.
Run this in a separate terminal to monitor progress.
"""
import os
import time
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()


def get_database_engine():
    db_uri = (
        f"mysql+pymysql://{os.getenv('DB_USER')}:"
        f"{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}/"
        f"{os.getenv('DB_NAME')}"
    )
    return create_engine(db_uri, echo=False)


def get_current_stats():
    """Get current processing statistics"""
    try:
        engine = get_database_engine()

        with engine.connect() as conn:
            # Get status counts
            status_result = conn.execute(
                text(
                    "SELECT mapStatus, COUNT(*) as count FROM global_hotel_mapping_copy_2 GROUP BY mapStatus"
                )
            )

            stats = {}
            total = 0

            for row in status_result:
                status = row.mapStatus or "NULL"
                count = row.count
                stats[status] = count
                total += count

            return stats, total

    except Exception as e:
        print(f"Error getting stats: {e}")
        return {}, 0


def monitor_progress():
    """Monitor progress in real-time"""
    print("🔍 Starting real-time monitoring...")
    print("Press Ctrl+C to stop monitoring\n")

    previous_stats = {}
    start_time = datetime.now()

    try:
        while True:
            current_time = datetime.now()
            stats, total = get_current_stats()

            if not stats:
                time.sleep(5)
                continue

            # Clear screen (works on most terminals)
            os.system("cls" if os.name == "nt" else "clear")

            print("=" * 60)
            print(f"🏨 HOTEL DATA INSERTION MONITOR")
            print(f"📅 Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"🕐 Current: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"⏱️  Runtime: {str(current_time - start_time).split('.')[0]}")
            print("=" * 60)

            # Show current status
            new_id = stats.get("new id", 0)
            processed = stats.get("processed", 0)
            upd1 = stats.get("upd1", 0)
            failed = stats.get("failed", 0)

            print(f"📊 CURRENT STATUS:")
            print(f"   🔄 Remaining (new id):     {new_id:,}")
            print(f"   ✅ Processed:             {processed:,}")
            print(f"   📝 Previously updated:    {upd1:,}")
            print(f"   ❌ Failed:                {failed:,}")
            print(f"   📈 Total records:         {total:,}")

            # Calculate progress
            if new_id + processed > 0:
                progress_pct = (processed / (new_id + processed)) * 100
                print(f"   📊 Progress:              {progress_pct:.1f}%")

            # Show changes since last check
            if previous_stats:
                print(f"\n📈 CHANGES (last 10 seconds):")

                prev_new_id = previous_stats.get("new id", 0)
                prev_processed = previous_stats.get("processed", 0)

                new_id_change = new_id - prev_new_id
                processed_change = processed - prev_processed

                if processed_change > 0:
                    print(f"   ✅ +{processed_change} processed")
                if new_id_change < 0:
                    print(f"   🔄 {abs(new_id_change)} moved from 'new id'")
                if processed_change == 0 and new_id_change == 0:
                    print(f"   ⏸️  No changes detected")

            # Estimate completion time
            if previous_stats and processed > previous_stats.get("processed", 0):
                rate = processed - previous_stats.get("processed", 0)  # per 10 seconds
                rate_per_minute = rate * 6  # per minute

                if rate_per_minute > 0 and new_id > 0:
                    eta_minutes = new_id / rate_per_minute
                    eta_time = current_time + pd.Timedelta(minutes=eta_minutes)
                    print(f"   ⏰ Processing rate:       {rate_per_minute:.1f}/min")
                    print(
                        f"   🎯 Estimated completion:  {eta_time.strftime('%H:%M:%S')}"
                    )

            print("=" * 60)
            print("Press Ctrl+C to stop monitoring")

            previous_stats = stats.copy()
            time.sleep(10)  # Update every 10 seconds

    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped by user")
    except Exception as e:
        print(f"\n❌ Monitoring error: {e}")


if __name__ == "__main__":
    monitor_progress()
