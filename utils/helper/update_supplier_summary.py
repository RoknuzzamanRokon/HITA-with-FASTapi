#!/usr/bin/env python3
"""
Count and Save Supplier Summary - OPTIMIZED VERSION

This script counts all data from provider_mappings and saves it to supplier_summary table.
Optimized with indexing, batch processing, and performance improvements.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text, create_engine
from database import SessionLocal, engine
import logging
import time
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Performance configuration
BATCH_SIZE = 10000  # Adjust based on your database capacity
CHUNK_SIZE = 5000   # For processing large datasets in chunks

@contextmanager
def database_session():
    """Context manager for database sessions with error handling"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()


def check_index_exists(db, index_name, table_name):
    """Check if an index already exists"""
    try:
        check_query = text("""
            SELECT COUNT(1) 
            FROM information_schema.statistics 
            WHERE table_schema = DATABASE() 
            AND table_name = :table_name 
            AND index_name = :index_name
        """)
        result = db.execute(check_query, {'table_name': table_name, 'index_name': index_name})
        return result.scalar() > 0
    except Exception as e:
        logger.warning(f"Could not check index {index_name}: {e}")
        return False


def create_indexes_if_not_exists():
    """
    Create necessary indexes for optimal performance
    MySQL-compatible version (without IF NOT EXISTS and DESC in index)
    """
    with database_session() as db:
        try:
            print("\n🔧 CREATING/CHECKING INDEXES FOR OPTIMAL PERFORMANCE...")
            
            # Index definitions for provider_mappings table
            provider_indexes = [
                ("idx_provider_mappings_provider", "provider_mappings", "provider_name"),
                ("idx_provider_mappings_ittid", "provider_mappings", "ittid"),
                ("idx_provider_mappings_provider_ittid", "provider_mappings", "provider_name, ittid"),
                ("idx_provider_mappings_updated", "provider_mappings", "updated_at"),
            ]
            
            # Index definitions for supplier_summary table
            summary_indexes = [
                ("idx_supplier_summary_provider", "supplier_summary", "provider_name"),
                ("idx_supplier_summary_hotels", "supplier_summary", "total_hotels"),  # Removed DESC
                ("idx_supplier_summary_updated", "supplier_summary", "last_updated"),  # Removed DESC
            ]
            
            # Create indexes for provider_mappings
            for index_name, table_name, columns in provider_indexes:
                if not check_index_exists(db, index_name, table_name):
                    try:
                        create_sql = f"CREATE INDEX {index_name} ON {table_name} ({columns})"
                        db.execute(text(create_sql))
                        db.commit()
                        print(f"   ✅ Created index '{index_name}' on {table_name}({columns})")
                    except Exception as e:
                        print(f"   ⚠️  Could not create index {index_name}: {e}")
                        db.rollback()
                else:
                    print(f"   ✅ Index '{index_name}' already exists")
            
            # Create indexes for supplier_summary
            for index_name, table_name, columns in summary_indexes:
                if not check_index_exists(db, index_name, table_name):
                    try:
                        create_sql = f"CREATE INDEX {index_name} ON {table_name} ({columns})"
                        db.execute(text(create_sql))
                        db.commit()
                        print(f"   ✅ Created index '{index_name}' on {table_name}({columns})")
                    except Exception as e:
                        print(f"   ⚠️  Could not create index {index_name}: {e}")
                        db.rollback()
                else:
                    print(f"   ✅ Index '{index_name}' already exists")
            
            print("   ✅ All indexes are optimized for performance")
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            raise


def get_table_statistics():
    """
    Get table statistics and size information
    """
    with database_session() as db:
        try:
            stats_query = text("""
                SELECT 
                    TABLE_NAME,
                    TABLE_ROWS as approximate_rows,
                    DATA_LENGTH as data_size_bytes,
                    INDEX_LENGTH as index_size_bytes,
                    ROUND((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) as total_size_mb
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME IN ('provider_mappings', 'supplier_summary')
            """)
            
            result = db.execute(stats_query)
            print("\n📊 TABLE STATISTICS:")
            print("-" * 80)
            print(f"{'Table':<20} {'Rows':<15} {'Data Size':<15} {'Index Size':<15} {'Total Size':<15}")
            print("-" * 80)
            
            for row in result:
                table = row[0]
                rows = f"{row[1]:,}" if row[1] else "N/A"
                data_size = f"{row[2]:,} bytes" if row[2] else "N/A"
                index_size = f"{row[3]:,} bytes" if row[3] else "N/A"
                total_size = f"{row[4]} MB" if row[4] else "N/A"
                
                print(f"{table:<20} {rows:<15} {data_size:<15} {index_size:<15} {total_size:<15}")
                
        except Exception as e:
            print(f"   ⚠️  Could not retrieve table statistics: {e}")


def count_and_save_summary_optimized():
    """
    Count all data from provider_mappings and save to supplier_summary table
    Optimized version with indexing and batch processing
    """
    print("\n" + "="*80)
    print("📊 COUNTING AND SAVING SUPPLIER SUMMARY - OPTIMIZED VERSION")
    print("="*80)
    
    total_start_time = time.time()
    
    try:
        # Step 0: Create indexes for optimal performance
        create_indexes_if_not_exists()
        
        # Step 0.5: Show table statistics
        get_table_statistics()
        
        with database_session() as db:
            # Step 1: Count current data in provider_mappings (optimized with EXISTS)
            print(f"\n1️⃣  COUNTING DATA IN PROVIDER_MAPPINGS (Batch size: {BATCH_SIZE})...")
            count_start_time = time.time()
            
            # Use more efficient counting method
            count_query = text("""
                SELECT 
                    COUNT(DISTINCT provider_name) as total_providers,
                    COUNT(DISTINCT ittid) as total_hotels,
                    COUNT(*) as total_mappings,
                    MAX(updated_at) as latest_update
                FROM provider_mappings
            """)
            
            result = db.execute(count_query)
            row = result.fetchone()
            total_providers = row[0] or 0
            total_hotels = row[1] or 0
            total_mappings = row[2] or 0
            latest_update = row[3]
            
            count_end_time = time.time()
            
            print(f"   ✅ Found {total_providers:,} providers")
            print(f"   ✅ Found {total_hotels:,} unique hotels")
            print(f"   ✅ Found {total_mappings:,} total mappings")
            if latest_update:
                print(f"   ✅ Latest update: {latest_update}")
            else:
                print(f"   ✅ Latest update: N/A")
            print(f"   ⚡ Counting completed in {(count_end_time - count_start_time):.2f}s")
            
            if total_providers == 0:
                print("\n⚠️  No data found in provider_mappings table!")
                return False
            
            # Step 2: Update/Insert data using optimized batch approach
            print(f"\n2️⃣  UPDATING SUPPLIER_SUMMARY DATA (Chunk size: {CHUNK_SIZE})...")
            update_start_time = time.time()
            
            # For very large datasets, process in chunks
            if total_mappings > 50000:
                print("   🔄 Large dataset detected, using chunked processing...")
                success = process_large_dataset(db, total_providers)
                if not success:
                    return False
            else:
                # Standard optimized approach for smaller datasets
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
            
            update_end_time = time.time()
            print(f"   ✅ Updated/Inserted {total_providers:,} providers")
            print(f"   ⚡ Update completed in {(update_end_time - update_start_time):.2f}s")
            
            # Step 3: Verify and analyze results
            verify_and_analyze(db, total_start_time)
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Error in optimized summary: {e}")
        return False


def process_large_dataset(db, total_providers):
    """
    Process very large datasets in chunks to avoid memory issues
    """
    try:
        # Get all provider names first
        providers_query = text("SELECT DISTINCT provider_name FROM provider_mappings ORDER BY provider_name")
        providers_result = db.execute(providers_query)
        provider_names = [row[0] for row in providers_result]
        
        print(f"   🔄 Processing {len(provider_names):,} providers in chunks...")
        
        processed = 0
        for i in range(0, len(provider_names), CHUNK_SIZE):
            chunk = provider_names[i:i + CHUNK_SIZE]
            
            # Use parameter binding instead of string formatting for security
            placeholders = ", ".join([f":name_{j}" for j in range(len(chunk))])
            params = {f"name_{j}": name for j, name in enumerate(chunk)}
            
            chunk_query = text(f"""
                INSERT INTO supplier_summary 
                    (provider_name, total_hotels, total_mappings, last_updated, summary_generated_at)
                SELECT 
                    provider_name,
                    COUNT(DISTINCT ittid) as total_hotels,
                    COUNT(*) as total_mappings,
                    MAX(updated_at) as last_updated,
                    CURRENT_TIMESTAMP as summary_generated_at
                FROM provider_mappings
                WHERE provider_name IN ({placeholders})
                GROUP BY provider_name
                ON DUPLICATE KEY UPDATE
                    total_hotels = VALUES(total_hotels),
                    total_mappings = VALUES(total_mappings),
                    last_updated = VALUES(last_updated),
                    summary_generated_at = VALUES(summary_generated_at)
            """)
            
            db.execute(chunk_query, params)
            db.commit()
            
            processed += len(chunk)
            print(f"   ✅ Processed {processed:,}/{len(provider_names):,} providers")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in chunked processing: {e}")
        db.rollback()
        return False


def verify_and_analyze(db, total_start_time):
    """
    Verify results and provide performance analysis
    """
    print(f"\n3️⃣  VERIFYING AND ANALYZING RESULTS...")
    
    # Verify saved data
    verify_query = text("""
        SELECT 
            COUNT(*) as providers_saved,
            SUM(total_hotels) as hotels_saved,
            SUM(total_mappings) as mappings_saved,
            MAX(summary_generated_at) as last_summary_time
        FROM supplier_summary
    """)
    
    result = db.execute(verify_query)
    row = result.fetchone()
    
    providers_saved = row[0] or 0
    hotels_saved = row[1] or 0
    mappings_saved = row[2] or 0
    
    print(f"   ✅ Providers saved: {providers_saved:,}")
    print(f"   ✅ Total hotels: {hotels_saved:,}")
    print(f"   ✅ Total mappings: {mappings_saved:,}")
    if row[3]:
        print(f"   ✅ Last summary: {row[3]}")
    else:
        print(f"   ✅ Last summary: N/A")
    
    # Show top suppliers with improved performance
    print(f"\n4️⃣  TOP 10 SUPPLIERS BY HOTEL COUNT:")
    print("-" * 80)
    
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
    
    print(f"   {'Provider':<25} {'Hotels':<12} {'Mappings':<12} {'Last Updated'}")
    print("   " + "-" * 70)
    
    for row in result:
        provider = (row[0][:22] + '...') if len(row[0]) > 25 else row[0]
        hotels = f"{row[1]:,}"
        mappings = f"{row[2]:,}"
        last_updated = row[3].strftime("%Y-%m-%d %H:%M") if row[3] else "N/A"
        print(f"   {provider:<25} {hotels:<12} {mappings:<12} {last_updated}")
    
    # Performance summary
    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    
    print(f"\n5️⃣  PERFORMANCE SUMMARY:")
    print("-" * 80)
    print(f"   ⚡ Total execution time: {total_duration:.2f} seconds")
    print(f"   📊 Records processed: {mappings_saved:,} mappings")
    print(f"   🏨 Unique hotels: {hotels_saved:,}")
    print(f"   👥 Suppliers: {providers_saved:,}")
    
    if total_duration > 0:
        records_per_second = mappings_saved / total_duration
        print(f"   🚀 Processing speed: {records_per_second:,.0f} records/second")
    
    print("\n" + "=" * 80)
    print("✅ OPTIMIZED COUNT AND SAVE COMPLETED SUCCESSFULLY!")
    print("=" * 80)


def cleanup_old_summaries():
    """
    Optional: Clean up old summary data to keep table size manageable
    """
    with database_session() as db:
        try:
            print(f"\n🧹 CLEANING UP OLD SUMMARY DATA...")
            
            cleanup_query = text("""
                DELETE FROM supplier_summary 
                WHERE summary_generated_at < DATE_SUB(NOW(), INTERVAL 30 DAY)
            """)
            
            result = db.execute(cleanup_query)
            db.commit()
            
            deleted_rows = result.rowcount
            if deleted_rows > 0:
                print(f"   ✅ Cleaned up {deleted_rows} old summary records")
            else:
                print(f"   ✅ No old records to clean up")
                
        except Exception as e:
            print(f"   ⚠️  Cleanup warning: {e}")


def main():
    """Main function"""
    print("🚀 STARTING OPTIMIZED SUPPLIER SUMMARY PROCESS...")
    
    # Optional: Clean up old data first
    cleanup_old_summaries()
    
    success = count_and_save_summary_optimized()
    
    if success:
        print("\n💡 NEXT STEPS & RECOMMENDATIONS:")
        print("   • Query supplier_summary table for fast statistics")
        print("   • Schedule periodic refreshes (hourly/daily)")
        print("   • Monitor database performance with indexes")
        print("   • Consider partitioning for very large datasets")
        print("\n📖 See README_SUPPLIER_SUMMARY.md for integration guide")
        
        # Additional optimization tips
        print("\n🔧 FURTHER OPTIMIZATION TIPS:")
        print("   • For >1M records: Consider table partitioning")
        print("   • For frequent updates: Use materialized views")
        print("   • For real-time needs: Implement caching layer")
    else:
        print("\n❌ Failed to count and save summary. Check logs for details.")
    
    return success


if __name__ == "__main__":
    sys.exit(0 if main() else 1)