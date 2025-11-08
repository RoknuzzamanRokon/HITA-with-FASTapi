#!/usr/bin/env python3
"""
Analyze Supplier Query Performance

This script analyzes the actual query execution plan for the supplier endpoint
to verify that indexes are being used correctly.
"""

from sqlalchemy import text
from database import SessionLocal
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_query_performance():
    """Analyze the performance of supplier queries"""
    
    db = SessionLocal()
    
    try:
        print("🔍 Analyzing Supplier Query Performance")
        print("="*80)
        
        # Test Query 1: Get all supplier stats (used by admin/super users)
        print("\n📊 Query 1: Get All Supplier Stats with Hotel Counts")
        print("-"*80)
        
        query1 = """
        SELECT 
            provider_name,
            COUNT(DISTINCT ittid) as hotel_count,
            MAX(updated_at) as last_updated
        FROM provider_mappings
        GROUP BY provider_name
        """
        
        # Explain the query
        explain_result = db.execute(text(f"EXPLAIN {query1}"))
        print("\n🔍 Query Execution Plan:")
        for row in explain_result:
            print(f"   {row}")
        
        # Time the query
        start_time = time.time()
        result = db.execute(text(query1))
        rows = result.fetchall()
        end_time = time.time()
        
        print(f"\n⏱️  Execution Time: {(end_time - start_time)*1000:.2f}ms")
        print(f"📊 Results: {len(rows)} suppliers found")
        
        # Show sample results
        print("\n📋 Sample Results (first 5):")
        for i, row in enumerate(rows[:5]):
            print(f"   {i+1}. {row[0]}: {row[1]} hotels")
        
        # Test Query 2: Get user permissions (used by general users)
        print("\n\n📊 Query 2: Get User Provider Permissions")
        print("-"*80)
        
        query2 = """
        SELECT provider_name
        FROM user_provider_permissions
        WHERE user_id = '5779356081'
        """
        
        # Explain the query
        explain_result = db.execute(text(f"EXPLAIN {query2}"))
        print("\n🔍 Query Execution Plan:")
        for row in explain_result:
            print(f"   {row}")
        
        # Time the query
        start_time = time.time()
        result = db.execute(text(query2))
        rows = result.fetchall()
        end_time = time.time()
        
        print(f"\n⏱️  Execution Time: {(end_time - start_time)*1000:.2f}ms")
        print(f"📊 Results: {len(rows)} permitted suppliers")
        
        # Test Query 3: Get supplier stats for specific suppliers (general user filtered)
        print("\n\n📊 Query 3: Get Filtered Supplier Stats (General User)")
        print("-"*80)
        
        if rows:
            permitted_suppliers = [row[0] for row in rows]
            placeholders = ','.join([f"'{s}'" for s in permitted_suppliers[:5]])  # Test with first 5
            
            query3 = f"""
            SELECT 
                provider_name,
                COUNT(DISTINCT ittid) as hotel_count,
                MAX(updated_at) as last_updated
            FROM provider_mappings
            WHERE provider_name IN ({placeholders})
            GROUP BY provider_name
            """
            
            # Explain the query
            explain_result = db.execute(text(f"EXPLAIN {query3}"))
            print("\n🔍 Query Execution Plan:")
            for row in explain_result:
                print(f"   {row}")
            
            # Time the query
            start_time = time.time()
            result = db.execute(text(query3))
            rows = result.fetchall()
            end_time = time.time()
            
            print(f"\n⏱️  Execution Time: {(end_time - start_time)*1000:.2f}ms")
            print(f"📊 Results: {len(rows)} suppliers")
        
        # Test Query 4: Count distinct suppliers
        print("\n\n📊 Query 4: Count Total Distinct Suppliers")
        print("-"*80)
        
        query4 = """
        SELECT COUNT(DISTINCT provider_name) as total_suppliers
        FROM provider_mappings
        """
        
        # Explain the query
        explain_result = db.execute(text(f"EXPLAIN {query4}"))
        print("\n🔍 Query Execution Plan:")
        for row in explain_result:
            print(f"   {row}")
        
        # Time the query
        start_time = time.time()
        result = db.execute(text(query4))
        total_suppliers = result.fetchone()[0]
        end_time = time.time()
        
        print(f"\n⏱️  Execution Time: {(end_time - start_time)*1000:.2f}ms")
        print(f"📊 Total Suppliers: {total_suppliers}")
        
        # Summary
        print("\n\n" + "="*80)
        print("✅ PERFORMANCE ANALYSIS COMPLETE")
        print("="*80)
        print("\n💡 Key Findings:")
        print("   • All queries should use indexes (check 'key' column in EXPLAIN)")
        print("   • Execution times should be <100ms for optimal performance")
        print("   • Look for 'Using index' in Extra column (covering index)")
        print("   • Avoid 'Using filesort' or 'Using temporary' if possible")
        
    except Exception as e:
        logger.error(f"❌ Error analyzing query performance: {e}")
        raise
    finally:
        db.close()

def check_table_statistics():
    """Check table statistics and row counts"""
    
    db = SessionLocal()
    
    try:
        print("\n\n📊 Table Statistics")
        print("="*80)
        
        # Provider mappings stats
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT provider_name) as unique_providers,
                COUNT(DISTINCT ittid) as unique_hotels
            FROM provider_mappings
        """))
        
        row = result.fetchone()
        print(f"\n📋 provider_mappings:")
        print(f"   Total Rows: {row[0]:,}")
        print(f"   Unique Providers: {row[1]:,}")
        print(f"   Unique Hotels: {row[2]:,}")
        
        # User provider permissions stats
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT user_id) as unique_users,
                COUNT(DISTINCT provider_name) as unique_providers
            FROM user_provider_permissions
        """))
        
        row = result.fetchone()
        print(f"\n📋 user_provider_permissions:")
        print(f"   Total Rows: {row[0]:,}")
        print(f"   Unique Users: {row[1]:,}")
        print(f"   Unique Providers: {row[2]:,}")
        
    except Exception as e:
        logger.error(f"❌ Error checking table statistics: {e}")
    finally:
        db.close()

def main():
    """Main function"""
    try:
        analyze_query_performance()
        check_table_statistics()
        
        print("\n\n🎯 Recommendations:")
        print("="*80)
        print("1. ✅ Indexes are in place - verify they're being used in EXPLAIN output")
        print("2. ✅ Query execution should be <100ms with proper indexes")
        print("3. ✅ Caching is enabled (5 minutes) for additional performance")
        print("4. 💡 Monitor slow query log for any queries >100ms")
        print("5. 💡 Consider increasing cache time if data doesn't change frequently")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()
