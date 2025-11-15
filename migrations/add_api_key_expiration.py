"""
Migration: Add API Key Expiration Field
Description: Adds api_key_expires_at column to users table for time-limited API keys
"""

import sqlite3
from datetime import datetime


def migrate():
    """Add api_key_expires_at column to users table"""
    
    # Connect to the database
    conn = sqlite3.connect('alembic/hotel.db')
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'api_key_expires_at' not in columns:
            print("Adding api_key_expires_at column to users table...")
            
            # Add the new column
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN api_key_expires_at DATETIME NULL
            """)
            
            conn.commit()
            print("✓ Successfully added api_key_expires_at column")
        else:
            print("✓ Column api_key_expires_at already exists")
        
        # Show current table structure
        cursor.execute("PRAGMA table_info(users)")
        print("\nCurrent users table structure:")
        for column in cursor.fetchall():
            print(f"  - {column[1]} ({column[2]})")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Error during migration: {str(e)}")
        raise
    finally:
        conn.close()


def rollback():
    """Remove api_key_expires_at column from users table"""
    
    # Note: SQLite doesn't support DROP COLUMN directly
    # This would require recreating the table
    print("Warning: SQLite doesn't support DROP COLUMN.")
    print("To rollback, you would need to recreate the users table without this column.")


if __name__ == "__main__":
    print("=" * 60)
    print("API Key Expiration Migration")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    migrate()
    
    print()
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
