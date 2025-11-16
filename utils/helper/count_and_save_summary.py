#!/usr/bin/env python3
"""
Count and Save Supplier Summary

This script counts all data from provider_mappings and saves it to supplier_summary table.
Run this to populate or refresh the supplier_summary table.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from database import SessionLocal
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def count_and_save_summary():
    """
    Count all data from provider_mappings and save to supplier_summary table
    """
    db = SessionLocal()
    
    try:
        print("\n" + "="*70)
        print("📊 COUNTING AND SAVING SUPPLIER SUMMARY")
        print("="*70)
        
        # Step 1: Count current data in provider_mappings
        print("\n1️⃣  Counting data in provider_mappings...")
        count_query = text("""
            SELECT 
                COUNT(DISTINCT provider_name) as total_providers,
                COUNT(DISTINCT ittid) as total_hotels,
                COUNT(*) as total_mappings
            FROM provider_mappings
        """)
        
        result = db.execute(count_query)
        row = result.fetchone()
        total_providers = row[0]
        total_hotels = row[1]
        total_mappings = row[2]
        
        print(f"   ✅ Found {total_providers} providers")
        print(f"   ✅ Found {total_hotels} unique hotels")
        print(f"   ✅ Found {total_mappings} total mappings")
        
        if total_providers == 0:
            print("\n⚠️  No data found in provider_mappings table!")
            return False
        
        # Step 2: Update/Insert data (no clearing)
        print("\n2️⃣  Updating supplier_summary data...")
        start_time = time.time()
        
        # Use INSERT ... ON DUPLICATE KEY UPDATE to update existing or insert new
        insert_query = text("""
            INSERT INTO supplier_summary 
                (provider_name, total_hotels, total_mappings, last_updated, summary_generated_at)
            SELECT 
                provider_name,
                COUNT(DISTINCT ittid) as total_hotels,
                COUNT(*) as total_mappings,
                MAX(updated_at) as last_updated,
                CURRENT_TIMESTAMP as summary_generated_at
            FROM provider_mappings
            GROUP BY provider_name
            ON DUPLICATE KEY UPDATE
                total_hotels = VALUES(total_hotels),
                total_mappings = VALUES(total_mappings),
                last_updated = VALUES(last_updated),
                summary_generated_at = VALUES(summary_generated_at)
        """)
        
        result = db.execute(insert_query)
        db.commit()
        
        end_time = time.time()
        
        print(f"   ✅ Updated/Inserted {total_providers} providers in {(end_time - start_time):.2f}s")
        
        # Step 3: Verify saved data
        print("\n3️⃣  Verifying saved data...")
        verify_query = text("""
            SELECT 
                COUNT(*) as providers_saved,
                SUM(total_hotels) as hotels_saved,
                SUM(total_mappings) as mappings_saved
            FROM supplier_summary
        """)
        
        result = db.execute(verify_query)
        row = result.fetchone()
        
        print(f"   ✅ Providers saved: {row[0]}")
        print(f"   ✅ Total hotels: {row[1]}")
        print(f"   ✅ Total mappings: {row[2]}")
        
        # Step 4: Show top suppliers
        print("\n4️⃣  Top 10 Suppliers by Hotel Count:")
        print("-"*70)
        
        top_query = text("""
            SELECT 
                provider_name,
                total_hotels,
                total_mappings,
                last_updated
            FROM supplier_summary
            ORDER BY total_hotels DESC
            LIMIT 10
        """)
        
        result = db.execute(top_query)
        
        print(f"   {'Provider':<20} {'Hotels':<12} {'Mappings':<12} {'Last Updated'}")
        print("   " + "-"*66)
        
        for row in result:
            provider = row[0]
            hotels = row[1]
            mappings = row[2]
            last_updated = row[3].strftime("%Y-%m-%d %H:%M") if row[3] else "N/A"
            print(f"   {provider:<20} {hotels:<12,} {mappings:<12,} {last_updated}")
        
        # Step 5: Data consistency check (fixed collation issue)
        print("\n5️⃣  Data Consistency Check:")
        print("-"*70)
        
        # Use subquery to avoid collation issues
        consistency_query = text("""
            SELECT 
                pm.provider_name,
                pm.actual_hotels,
                pm.actual_mappings,
                ss.total_hotels as summary_hotels,
                ss.total_mappings as summary_mappings
            FROM (
                SELECT 
                    provider_name,
                    COUNT(DISTINCT ittid) as actual_hotels,
                    COUNT(*) as actual_mappings
                FROM provider_mappings
                GROUP BY provider_name
            ) pm
            LEFT JOIN supplier_summary ss ON pm.provider_name = ss.provider_name COLLATE utf8mb4_unicode_ci
            LIMIT 5
        """)
        
        result = db.execute(consistency_query)
        all_match = True
        
        for row in result:
            provider = row[0]
            actual_h = row[1]
            actual_m = row[2]
            summary_h = row[3]
            summary_m = row[4]
            
            if actual_h == summary_h and actual_m == summary_m:
                print(f"   ✅ {provider}: {actual_h:,} hotels, {actual_m:,} mappings (MATCH)")
            else:
                print(f"   ❌ {provider}: Actual({actual_h:,}, {actual_m:,}) vs Summary({summary_h:,}, {summary_m:,})")
                all_match = False
        
        if all_match:
            print("\n   ✅ All data is consistent!")
        else:
            print("\n   ⚠️  Some inconsistencies found!")
        
        print("\n" + "="*70)
        print("✅ COUNT AND SAVE COMPLETED SUCCESSFULLY!")
        print("="*70)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def main():
    """Main function"""
    success = count_and_save_summary()
    
    if success:
        print("\n💡 Next Steps:")
        print("   • Query supplier_summary table for fast statistics")
        print("   • Schedule periodic refreshes (hourly/daily)")
        print("   • Integrate into your routes after mapping changes")
        print("\n📖 See README_SUPPLIER_SUMMARY.md for integration guide")
    else:
        print("\n❌ Failed to count and save summary. Check logs for details.")
    
    return success


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
