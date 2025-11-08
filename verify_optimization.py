#!/usr/bin/env python3
"""
Verify Optimization Setup

This script verifies that all optimization components are in place and working.
"""

from sqlalchemy import text
from database import SessionLocal
import models
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_summary_table():
    """Check if summary table exists and has data"""
    db = SessionLocal()
    
    try:
        print("📊 Checking supplier_summary table...")
        
        # Check if table exists
        result = db.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'supplier_summary'
        """))
        
        if result.fetchone()[0] == 0:
            print("   ❌ Table does not exist")
            return False
        
        print("   ✅ Table exists")
        
        # Check if table has data
        result = db.execute(text("SELECT COUNT(*) FROM supplier_summary"))
        count = result.fetchone()[0]
        
        if count == 0:
            print("   ❌ Table is empty")
            return False
        
        print(f"   ✅ Table has {count} suppliers")
        
        # Show sample data
        result = db.execute(text("""
            SELECT provider_name, total_hotels 
            FROM supplier_summary 
            ORDER BY total_hotels DESC 
            LIMIT 3
        """))
        
        print("   📋 Top 3 suppliers:")
        for row in result:
            print(f"      • {row[0]}: {row[1]:,} hotels")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        db.close()

def check_indexes():
    """Check if required indexes exist"""
    db = SessionLocal()
    
    try:
        print("\n🔍 Checking indexes...")
        
        required_indexes = {
            'provider_mappings': [
                'idx_provider_mapping_provider_name',
                'idx_provider_mapping_name_ittid'
            ],
            'user_provider_permissions': [
                'idx_user_provider_permission_user_id',
                'idx_user_provider_permission_user_provider'
            ]
        }
        
        all_good = True
        
        for table, indexes in required_indexes.items():
            print(f"\n   📋 {table}:")
            for index_name in indexes:
                result = db.execute(text(f"""
                    SELECT COUNT(*) 
                    FROM information_schema.statistics 
                    WHERE table_schema = DATABASE() 
                    AND table_name = '{table}' 
                    AND index_name = '{index_name}'
                """))
                
                if result.fetchone()[0] > 0:
                    print(f"      ✅ {index_name}")
                else:
                    print(f"      ❌ {index_name} - MISSING!")
                    all_good = False
        
        return all_good
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        db.close()

def check_stored_procedure():
    """Check if stored procedure exists"""
    db = SessionLocal()
    
    try:
        print("\n🔧 Checking stored procedure...")
        
        result = db.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.routines 
            WHERE routine_schema = DATABASE() 
            AND routine_name = 'refresh_supplier_summary'
        """))
        
        if result.fetchone()[0] > 0:
            print("   ✅ refresh_supplier_summary procedure exists")
            return True
        else:
            print("   ❌ Procedure does not exist")
            return False
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        db.close()

def check_model():
    """Check if SupplierSummary model is available"""
    print("\n📦 Checking model...")
    
    try:
        if hasattr(models, 'SupplierSummary'):
            print("   ✅ SupplierSummary model exists")
            return True
        else:
            print("   ❌ SupplierSummary model not found")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def check_data_freshness():
    """Check how fresh the summary data is"""
    db = SessionLocal()
    
    try:
        print("\n🕐 Checking data freshness...")
        
        result = db.execute(text("""
            SELECT 
                MAX(summary_generated_at) as last_refresh,
                TIMESTAMPDIFF(MINUTE, MAX(summary_generated_at), NOW()) as minutes_ago
            FROM supplier_summary
        """))
        
        row = result.fetchone()
        
        if row and row[0]:
            print(f"   📅 Last refresh: {row[0]}")
            print(f"   ⏱️  {row[1]} minutes ago")
            
            if row[1] > 60:
                print("   ⚠️  Data is more than 1 hour old - consider refreshing")
                return False
            else:
                print("   ✅ Data is fresh")
                return True
        else:
            print("   ❌ No refresh timestamp found")
            return False
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        db.close()

def test_query_performance():
    """Test actual query performance"""
    db = SessionLocal()
    
    try:
        print("\n⚡ Testing query performance...")
        
        import time
        
        # Test the optimized query
        start_time = time.time()
        result = db.execute(text("""
            SELECT provider_name, total_hotels, last_updated
            FROM supplier_summary
            ORDER BY provider_name
        """))
        rows = result.fetchall()
        end_time = time.time()
        
        query_time = (end_time - start_time) * 1000
        
        print(f"   ⏱️  Query time: {query_time:.2f}ms")
        print(f"   📊 Results: {len(rows)} suppliers")
        
        if query_time < 10:
            print("   ✅ EXCELLENT! Query is blazing fast!")
            return True
        elif query_time < 100:
            print("   ✅ GOOD! Query is fast enough.")
            return True
        else:
            print("   ⚠️  Query is slower than expected")
            return False
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        db.close()

def main():
    print("🔍 Optimization Verification")
    print("="*80)
    
    results = {
        "Summary Table": check_summary_table(),
        "Indexes": check_indexes(),
        "Stored Procedure": check_stored_procedure(),
        "Model": check_model(),
        "Data Freshness": check_data_freshness(),
        "Query Performance": test_query_performance()
    }
    
    print("\n" + "="*80)
    print("📊 Verification Summary")
    print("="*80)
    
    all_passed = True
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {check}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*80)
    
    if all_passed:
        print("✅ ALL CHECKS PASSED!")
        print("\n🎉 Optimization is fully set up and working!")
        print("\n💡 Next steps:")
        print("   1. Restart your application if not already done")
        print("   2. Test the endpoint: pipenv run python test_endpoint_performance.py")
        print("   3. Set up automatic refresh schedule")
    else:
        print("❌ SOME CHECKS FAILED!")
        print("\n🔧 Troubleshooting:")
        
        if not results["Summary Table"]:
            print("   • Run: pipenv run python create_supplier_summary_table.py")
        
        if not results["Indexes"]:
            print("   • Run: pipenv run python add_supplier_indexes_mysql.py")
        
        if not results["Stored Procedure"]:
            print("   • Run: pipenv run python create_supplier_summary_table.py")
        
        if not results["Model"]:
            print("   • Check models.py for SupplierSummary class")
            print("   • Restart application to load new model")
        
        if not results["Data Freshness"]:
            print("   • Run: pipenv run python refresh_supplier_summary.py")
    
    return all_passed

if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
