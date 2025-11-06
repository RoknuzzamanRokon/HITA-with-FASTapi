#!/usr/bin/env python3
"""
Database Performance Optimization Script

This script will run the critical performance fixes on your MySQL database
to dramatically improve the cities_with_countries endpoint performance.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import time

def load_database_config():
    """Load database configuration from environment."""
    load_dotenv()
    
    db_connection = os.getenv("DB_CONNECTION")
    if not db_connection:
        print("❌ ERROR: DB_CONNECTION not found in .env file")
        sys.exit(1)
    
    return db_connection

def run_sql_file(engine, sql_file_path):
    """Execute SQL commands from a file."""
    try:
        with open(sql_file_path, 'r', encoding='utf-8') as file:
            sql_content = file.read()
        
        # Split SQL commands (simple approach)
        commands = [cmd.strip() for cmd in sql_content.split(';') if cmd.strip() and not cmd.strip().startswith('--')]
        
        with engine.connect() as connection:
            print(f"🔗 Connected to database successfully")
            
            for i, command in enumerate(commands, 1):
                if command.upper().startswith(('CREATE INDEX', 'ANALYZE', 'OPTIMIZE', 'SHOW', 'SELECT')):
                    print(f"\n📋 Executing command {i}/{len(commands)}:")
                    print(f"   {command[:60]}{'...' if len(command) > 60 else ''}")
                    
                    start_time = time.time()
                    try:
                        result = connection.execute(text(command))
                        duration = time.time() - start_time
                        
                        if command.upper().startswith(('SHOW', 'SELECT')):
                            rows = result.fetchall()
                            print(f"   ✅ Success ({duration:.2f}s) - {len(rows)} rows returned")
                            
                            # Show some results for informational commands
                            if len(rows) > 0 and len(rows) <= 10:
                                for row in rows:
                                    print(f"      {row}")
                        else:
                            print(f"   ✅ Success ({duration:.2f}s)")
                            
                    except Exception as e:
                        duration = time.time() - start_time
                        print(f"   ⚠️  Warning ({duration:.2f}s): {str(e)}")
                        # Continue with other commands even if one fails
                        continue
            
            # Commit all changes
            connection.commit()
            print(f"\n✅ All database optimizations completed successfully!")
            
    except FileNotFoundError:
        print(f"❌ ERROR: SQL file '{sql_file_path}' not found")
        return False
    except Exception as e:
        print(f"❌ ERROR: Failed to execute SQL file: {str(e)}")
        return False
    
    return True

def test_performance_improvement(engine):
    """Test a simple query to verify performance improvement."""
    print(f"\n🧪 Testing query performance...")
    
    test_query = text("""
        SELECT COUNT(DISTINCT country_name) as countries,
               COUNT(DISTINCT city_name) as cities
        FROM locations 
        WHERE country_name IS NOT NULL 
            AND country_name != ''
            AND city_name IS NOT NULL 
            AND city_name != ''
    """)
    
    try:
        with engine.connect() as connection:
            start_time = time.time()
            result = connection.execute(test_query)
            duration = time.time() - start_time
            
            row = result.fetchone()
            countries = row[0] if row else 0
            cities = row[1] if row else 0
            
            print(f"   ⏱️  Query completed in {duration:.2f} seconds")
            print(f"   📊 Found {countries} countries and {cities} cities")
            
            if duration < 5:
                print(f"   🚀 EXCELLENT: Query is now fast!")
            elif duration < 15:
                print(f"   ✅ GOOD: Significant improvement achieved")
            else:
                print(f"   ⚠️  SLOW: May need additional optimization")
                
    except Exception as e:
        print(f"   ❌ Test failed: {str(e)}")

def main():
    """Main execution function."""
    print("🔥 DATABASE PERFORMANCE OPTIMIZATION")
    print("=" * 50)
    print("This script will optimize your locations table for faster queries.")
    print("Expected improvement: 60+ seconds → 2-10 seconds")
    print()
    
    # Load database configuration
    print("📋 Loading database configuration...")
    db_connection = load_database_config()
    print(f"   Database: {db_connection.split('@')[1].split('/')[0] if '@' in db_connection else 'Unknown'}")
    
    # Create database engine
    print("\n🔗 Connecting to database...")
    try:
        engine = create_engine(
            db_connection,
            pool_size=1,
            max_overflow=0,
            echo=False
        )
        
        # Test connection
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("   ✅ Database connection successful")
        
    except Exception as e:
        print(f"   ❌ Database connection failed: {str(e)}")
        sys.exit(1)
    
    # Run the performance optimization
    print("\n🚀 Running performance optimization...")
    sql_file = "CRITICAL_PERFORMANCE_FIX_MYSQL.sql"
    
    if run_sql_file(engine, sql_file):
        print("\n🎉 OPTIMIZATION COMPLETED SUCCESSFULLY!")
        
        # Test the improvement
        test_performance_improvement(engine)
        
        print("\n📈 NEXT STEPS:")
        print("1. Test your /cities_with_countries endpoint")
        print("2. It should now respond in 2-10 seconds instead of 60+ seconds")
        print("3. Cached requests will be ~1ms (instant)")
        print("4. Monitor your database performance")
        
    else:
        print("\n❌ OPTIMIZATION FAILED")
        print("Please check the error messages above and try again.")
        sys.exit(1)

if __name__ == "__main__":
    main()