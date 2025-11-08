#!/usr/bin/env python3
"""
Refresh Supplier Summary Table

This script refreshes the supplier_summary table with the latest data.
Run this periodically (e.g., hourly or daily) via cron job or scheduler.
"""

from sqlalchemy import text
from database import SessionLocal
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def refresh_summary():
    """Refresh the supplier summary table"""
    
    db = SessionLocal()
    
    try:
        logger.info("🔄 Refreshing supplier_summary table...")
        
        start_time = time.time()
        
        # Call the stored procedure
        db.execute(text("CALL refresh_supplier_summary()"))
        db.commit()
        
        end_time = time.time()
        
        # Get count
        result = db.execute(text("SELECT COUNT(*) FROM supplier_summary"))
        count = result.fetchone()[0]
        
        logger.info(f"✅ Refreshed {count} suppliers in {(end_time - start_time):.2f}s")
        
        # Show top suppliers
        result = db.execute(text("""
            SELECT provider_name, total_hotels, total_mappings
            FROM supplier_summary
            ORDER BY total_hotels DESC
            LIMIT 5
        """))
        
        print("\n📊 Top 5 Suppliers:")
        print("-"*60)
        for row in result:
            print(f"   {row[0]}: {row[1]:,} hotels ({row[2]:,} mappings)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error refreshing summary: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def main():
    print("🔄 Supplier Summary Refresh")
    print("="*60)
    
    success = refresh_summary()
    
    if success:
        print("\n✅ Refresh completed successfully!")
        print("\n💡 Schedule this script to run periodically:")
        print("   • Cron job: 0 * * * * (every hour)")
        print("   • Windows Task Scheduler: hourly")
        print("   • Or trigger after bulk data imports")
    else:
        print("\n❌ Refresh failed. Check logs for details.")
    
    return success

if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
