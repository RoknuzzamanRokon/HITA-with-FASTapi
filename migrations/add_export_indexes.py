"""
Migration script to add performance indexes for export operations.

This script adds database indexes to optimize export query performance:
- Hotels table: updated_at, rating, property_type
- Locations table: country_code, city_name
- Provider mappings table: provider_name, updated_at
- Export jobs table: user_id, status, expires_at
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import engine, SessionLocal
from sqlalchemy import text
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def apply_export_indexes():
    """
    Apply performance indexes for export operations.
    
    Reads SQL commands from add_export_performance_indexes.sql and executes them.
    """
    logger.info("Starting export performance indexes migration")
    
    # Read SQL file
    sql_file_path = Path(__file__).parent.parent / "database" / "add_export_performance_indexes.sql"
    
    if not sql_file_path.exists():
        logger.error(f"SQL file not found: {sql_file_path}")
        return False
    
    logger.info(f"Reading SQL commands from: {sql_file_path}")
    
    with open(sql_file_path, 'r') as f:
        sql_content = f.read()
    
    # Split into individual commands (by semicolon)
    commands = [cmd.strip() for cmd in sql_content.split(';') if cmd.strip() and not cmd.strip().startswith('--')]
    
    logger.info(f"Found {len(commands)} SQL commands to execute")
    
    # Create database session
    db = SessionLocal()
    
    try:
        success_count = 0
        error_count = 0
        
        for i, command in enumerate(commands, 1):
            try:
                # Skip comments
                if command.startswith('--'):
                    continue
                
                logger.info(f"Executing command {i}/{len(commands)}: {command[:60]}...")
                
                # Execute command
                db.execute(text(command))
                db.commit()
                
                success_count += 1
                logger.info(f"✓ Command {i} executed successfully")
                
            except Exception as e:
                # Check if error is due to duplicate index (which is OK)
                error_str = str(e).lower()
                if 'duplicate' in error_str or 'already exists' in error_str or '1061' in error_str:
                    logger.info(f"⊙ Index already exists (skipping): {command[:60]}...")
                    success_count += 1
                else:
                    error_count += 1
                    logger.error(f"✗ Error executing command {i}: {str(e)}")
                    logger.error(f"Command: {command}")
                
                db.rollback()
                
                # Continue with next command even if one fails
                continue
        
        logger.info(f"\nMigration completed:")
        logger.info(f"  Successful: {success_count}")
        logger.info(f"  Failed: {error_count}")
        
        return error_count == 0
        
    except Exception as e:
        logger.error(f"Fatal error during migration: {str(e)}")
        db.rollback()
        return False
        
    finally:
        db.close()


def verify_indexes():
    """
    Verify that indexes were created successfully.
    
    Queries the database to check for the existence of key indexes.
    """
    logger.info("\nVerifying indexes...")
    
    db = SessionLocal()
    
    try:
        # Check for key indexes
        key_indexes = [
            'idx_hotels_updated_at',
            'idx_locations_country_code',
            'idx_provider_mappings_provider_name',
            'idx_export_jobs_user_status'
        ]
        
        for index_name in key_indexes:
            try:
                # SQLite-specific query to check index existence
                result = db.execute(text(
                    f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index_name}'"
                )).fetchone()
                
                if result:
                    logger.info(f"✓ Index verified: {index_name}")
                else:
                    logger.warning(f"✗ Index not found: {index_name}")
                    
            except Exception as e:
                logger.error(f"Error verifying index {index_name}: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error during verification: {str(e)}")
        
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Export Performance Indexes Migration")
    logger.info("=" * 60)
    
    # Apply indexes
    success = apply_export_indexes()
    
    if success:
        logger.info("\n✓ Migration completed successfully")
        
        # Verify indexes
        verify_indexes()
    else:
        logger.error("\n✗ Migration completed with errors")
        sys.exit(1)
    
    logger.info("\n" + "=" * 60)
