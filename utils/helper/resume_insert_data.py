#!/usr/bin/env python3
"""
Recovery script to resume hotel data insertion from where it stopped.
This script checks the current status and can resume processing.
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

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


def check_status():
    """Check current processing status"""
    try:
        engine = get_database_engine()

        with engine.connect() as conn:
            print("=== Current Processing Status ===")

            # Show current status distribution
            status_result = conn.execute(
                text(
                    "SELECT mapStatus, COUNT(*) as count FROM global_hotel_mapping_copy_2 GROUP BY mapStatus ORDER BY count DESC"
                )
            )

            total_all = 0
            status_counts = {}

            for row in status_result:
                count = row.count
                status = row.mapStatus or "NULL"
                status_counts[status] = count
                total_all += count
                print(f"mapStatus '{status}': {count:,} rows")

            print(f"\nTotal rows in table: {total_all:,}")

            # Check for stuck processing
            new_id_count = status_counts.get("new id", 0)
            processed_count = status_counts.get("processed", 0)

            print(f"\n=== Processing Progress ===")
            print(f"Remaining to process (new id): {new_id_count:,}")
            print(f"Successfully processed: {processed_count:,}")

            if new_id_count > 0:
                print(f"\n✅ Can resume processing {new_id_count:,} remaining rows")

                # Show sample of remaining data
                print("\n=== Sample of remaining data ===")
                sample_result = conn.execute(
                    text(
                        "SELECT Id, ittid, Name FROM global_hotel_mapping_copy_2 WHERE mapStatus = 'new id' LIMIT 5"
                    )
                )

                for i, row in enumerate(sample_result, 1):
                    print(f"{i}. ID: {row.Id}, ITTID: {row.ittid}, Name: {row.Name}")

                return True
            else:
                print("\n🎉 All rows have been processed!")
                return False

    except Exception as e:
        print(f"❌ Error checking status: {e}")
        return False


def reset_stuck_rows():
    """Reset any rows that might be stuck in processing"""
    try:
        engine = get_database_engine()

        with engine.begin() as conn:
            # If you had any rows marked as 'processing', reset them back to 'new id'
            result = conn.execute(
                text(
                    "UPDATE global_hotel_mapping_copy_2 SET mapStatus = 'new id' WHERE mapStatus = 'processing'"
                )
            )

            if result.rowcount > 0:
                print(
                    f"✅ Reset {result.rowcount} stuck rows from 'processing' back to 'new id'"
                )
            else:
                print("ℹ️  No stuck rows found")

    except Exception as e:
        print(f"❌ Error resetting stuck rows: {e}")


def main():
    print("🔍 Checking hotel insertion status...\n")

    can_resume = check_status()

    if can_resume:
        print("\n" + "=" * 50)
        print("NEXT STEPS:")
        print("1. Run: python utils/helper/insert_new_data_into_HITA.py")
        print("2. The script will automatically resume from remaining 'new id' rows")
        print("3. Monitor the progress and check for any errors")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("✅ Processing appears to be complete!")
        print("=" * 50)


if __name__ == "__main__":
    main()
