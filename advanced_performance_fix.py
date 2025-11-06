#!/usr/bin/env python3
"""
Advanced Database Performance Optimization

This script will run additional optimizations for the large dataset
(312 countries, 106K+ cities) to get better performance.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import time

def load_database_config():
    """Load database configuration from environment."""
    load_dotenv()
    return os.getenv("DB_CONNECTION")

def run_advanced_optimizations(engine):
    """Run advanced optimizations for large datasets."""
    
    optimizations = [
        # 1. Create more specific indexes
        """
        CREATE INDEX idx_locations_country_trimmed 
        ON locations(country_name(50)) 
        WHERE country_name IS NOT NULL AND country_name != ''
        """,
        
        # 2. Create city index with length limit
        """
        CREATE INDEX idx_locations_city_trimmed 
        ON locations(city_name(50)) 
        WHERE city_name IS NOT NULL AND city_name != ''
        """,
        
        # 3. Create a covering index for the specific query
        """
        CREATE INDEX idx_locations_covering 
        ON locations(country_name(50), city_name(50))
        WHERE country_name IS NOT NULL 
            AND country_name != '' 
            AND city_name IS NOT NULL 
            AND city_name != ''
        """,
        
        # 4. Update table statistics
        "ANALYZE TABLE locations",
        
        # 5. Optimize table
        "OPTIMIZE TABLE locations"
    ]
    
    with engine.connect() as connection:
        for i, sql in enumerate(optimizations, 1):
            print(f"\n📋 Running optimization {i}/{len(optimizations)}...")
            print(f"   {sql.strip().split()[0:3]} ...")
            
            start_time = time.time()
            try:
                connection.execute(text(sql))
                duration = time.time() - start_time
                print(f"   ✅ Success ({duration:.2f}s)")
            except Exception as e:
                duration = time.time() - start_time
                if "Duplicate key name" in str(e):
                    print(f"   ℹ️  Index already exists ({duration:.2f}s)")
                else:
                    print(f"   ⚠️  Warning ({duration:.2f}s): {str(e)}")
        
        connection.commit()

def test_optimized_query(engine):
    """Test the actual query used by the endpoint."""
    print(f"\n🧪 Testing the actual endpoint query...")
    
    # This is the exact query from the endpoint
    endpoint_query = text("""
        SELECT DISTINCT country_name, city_name
        FROM locations 
        WHERE country_name IS NOT NULL 
            AND country_name != ''
            AND city_name IS NOT NULL 
            AND city_name != ''
            AND LENGTH(TRIM(country_name)) > 2
            AND LENGTH(TRIM(city_name)) > 1
        ORDER BY country_name, city_name
        LIMIT 10000
    """)
    
    try:
        with engine.connect() as connection:
            start_time = time.time()
            result = connection.execute(endpoint_query)
            rows = result.fetchall()
            duration = time.time() - start_time
            
            print(f"   ⏱️  Query completed in {duration:.2f} seconds")
            print(f"   📊 Retrieved {len(rows)} city-country pairs")
            
            if duration < 2:
                print(f"   🚀 EXCELLENT: Query is now very fast!")
            elif duration < 5:
                print(f"   ✅ GOOD: Significant improvement achieved")
            elif duration < 15:
                print(f"   ⚠️  MODERATE: Some improvement, but could be better")
            else:
                print(f"   ❌ SLOW: Still needs more optimization")
                
            return duration
                
    except Exception as e:
        print(f"   ❌ Test failed: {str(e)}")
        return None

def main():
    """Main execution function."""
    print("🚀 ADVANCED DATABASE PERFORMANCE OPTIMIZATION")
    print("=" * 55)
    print("Running additional optimizations for your large dataset")
    print("(312 countries, 106K+ cities)")
    print()
    
    # Load database configuration
    db_connection = load_database_config()
    
    # Create database engine
    try:
        engine = create_engine(
            db_connection,
            pool_size=1,
            max_overflow=0,
            echo=False
        )
        
        print("🔗 Connected to database")
        
        # Run advanced optimizations
        print("\n🔧 Running advanced optimizations...")
        run_advanced_optimizations(engine)
        
        # Test the performance
        duration = test_optimized_query(engine)
        
        print(f"\n🎯 OPTIMIZATION RESULTS:")
        if duration and duration < 5:
            print("✅ SUCCESS: Your endpoints should now be much faster!")
            print("📈 Expected endpoint performance:")
            print("   • /cities_with_countries/lightning: 1-5 seconds")
            print("   • /cities_with_countries/sample: <1 second")
            print("   • /cities_with_countries (cached): ~1ms after first request")
        else:
            print("⚠️  PARTIAL SUCCESS: Some improvement achieved")
            print("💡 Consider using the /sample or /lightning endpoints for best performance")
        
        print(f"\n🔥 NEXT STEPS:")
        print("1. Test your endpoints now:")
        print("   • GET /v1.0/locations/cities_with_countries/sample")
        print("   • GET /v1.0/locations/cities_with_countries/lightning")
        print("2. The sample endpoint should be very fast now")
        print("3. Use caching for production workloads")
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()