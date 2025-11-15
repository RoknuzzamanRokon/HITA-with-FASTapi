"""
Migration script to add api_key_expires_at column to users table

This script adds the missing api_key_expires_at column to the users table.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

def run_migration():
    """Add api_key_expires_at column to users table"""
    
    # Get database connection string from environment
    db_connection = os.getenv("DB_CONNECTION")
    
    if not db_connection:
        print("ERROR: DB_CONNECTION environment variable not set")
        return False
    
    try:
        # Create engine
        engine = create_engine(db_connection)
        
        # Check if column already exists
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) as count
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'users'
                AND COLUMN_NAME = 'api_key_expires_at'
            """))
            
            row = result.fetchone()
            if row[0] > 0:
                print("Column 'api_key_expires_at' already exists in users table")
                return True
            
            # Add the column
            print("Adding 'api_key_expires_at' column to users table...")
            conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN api_key_expires_at DATETIME NULL
                AFTER api_key
            """))
            conn.commit()
            
            print("✓ Successfully added 'api_key_expires_at' column to users table")
            return True
            
    except Exception as e:
        print(f"ERROR: Failed to add column: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
