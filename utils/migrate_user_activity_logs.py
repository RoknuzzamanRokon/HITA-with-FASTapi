#!/usr/bin/env python3
"""
Migration script to update user_activity_logs table to allow NULL user_id
This fixes the audit logging issue for unauthenticated requests
"""

import sys
import os
from sqlalchemy import create_engine, text
from database import DATABASE_URL

def migrate_user_activity_logs():
    """Update user_activity_logs table to allow NULL user_id"""
    
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as connection:
            # Start transaction
            trans = connection.begin()
            
            try:
                print("Updating user_activity_logs table to allow NULL user_id...")
                
                # Modify the user_id column to allow NULL values
                connection.execute(text("""
                    ALTER TABLE user_activity_logs 
                    MODIFY COLUMN user_id VARCHAR(10) NULL
                """))
                
                print("✅ Successfully updated user_activity_logs table")
                
                # Commit the transaction
                trans.commit()
                
            except Exception as e:
                # Rollback on error
                trans.rollback()
                print(f"❌ Error during migration: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🔄 Starting user_activity_logs migration...")
    
    success = migrate_user_activity_logs()
    
    if success:
        print("✅ Migration completed successfully!")
        print("The SecurityMiddleware can now log activities from unauthenticated users.")
    else:
        print("❌ Migration failed!")
        sys.exit(1)