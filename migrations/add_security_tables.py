"""
Database Migration: Add Security and Audit Logging Tables

This migration adds the necessary tables for enhanced security features:
- user_activity_logs: For comprehensive audit logging
- user_sessions: For session management and tracking
- blacklisted_tokens: For token revocation

Run this migration after implementing the security enhancements.
"""

from sqlalchemy import create_engine, text
from database import DATABASE_URL, engine
import logging

logger = logging.getLogger(__name__)


def create_security_tables():
    """Create security-related tables"""
    
    # SQL statements to create the tables
    create_tables_sql = [
        """
        CREATE TABLE IF NOT EXISTS user_activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(10) NOT NULL,
            action VARCHAR(50) NOT NULL,
            details JSON,
            ip_address VARCHAR(45),
            user_agent VARCHAR(500),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_user_activity_logs_user_id 
        ON user_activity_logs(user_id);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_user_activity_logs_action 
        ON user_activity_logs(action);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_user_activity_logs_created_at 
        ON user_activity_logs(created_at);
        """,
        
        """
        CREATE TABLE IF NOT EXISTS user_sessions (
            id VARCHAR(50) PRIMARY KEY,
            user_id VARCHAR(10) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_activity DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            ip_address VARCHAR(45),
            user_agent VARCHAR(500),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id 
        ON user_sessions(user_id);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at 
        ON user_sessions(expires_at);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_user_sessions_is_active 
        ON user_sessions(is_active);
        """,
        
        """
        CREATE TABLE IF NOT EXISTS blacklisted_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token VARCHAR(255) UNIQUE NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_blacklisted_tokens_token 
        ON blacklisted_tokens(token);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_blacklisted_tokens_created_at 
        ON blacklisted_tokens(created_at);
        """
    ]
    
    try:
        with engine.connect() as connection:
            for sql in create_tables_sql:
                logger.info(f"Executing: {sql.strip()[:50]}...")
                connection.execute(text(sql))
                connection.commit()
        
        logger.info("Security tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating security tables: {e}")
        return False


def add_security_columns_to_existing_tables():
    """Add security-related columns to existing tables if they don't exist"""
    
    alter_statements = [
        # Add columns to users table for enhanced security tracking
        """
        ALTER TABLE users ADD COLUMN last_login DATETIME;
        """,
        
        """
        ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0;
        """,
        
        """
        ALTER TABLE users ADD COLUMN account_locked_until DATETIME;
        """,
        
        """
        ALTER TABLE users ADD COLUMN password_changed_at DATETIME;
        """,
        
        """
        ALTER TABLE users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT 0;
        """,
        
        # Add security tracking to point transactions
        """
        ALTER TABLE point_transactions ADD COLUMN ip_address VARCHAR(45);
        """,
        
        """
        ALTER TABLE point_transactions ADD COLUMN user_agent VARCHAR(500);
        """,
        
        """
        ALTER TABLE point_transactions ADD COLUMN security_flags JSON;
        """
    ]
    
    try:
        with engine.connect() as connection:
            for sql in alter_statements:
                try:
                    logger.info(f"Executing: {sql.strip()[:50]}...")
                    connection.execute(text(sql))
                    connection.commit()
                except Exception as e:
                    # Column might already exist, log but continue
                    logger.warning(f"Could not add column (might already exist): {e}")
        
        logger.info("Security columns added successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error adding security columns: {e}")
        return False


def create_security_indexes():
    """Create additional indexes for security and performance"""
    
    index_statements = [
        # Indexes for users table security columns
        """
        CREATE INDEX IF NOT EXISTS idx_users_last_login 
        ON users(last_login);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_users_failed_login_attempts 
        ON users(failed_login_attempts);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_users_account_locked_until 
        ON users(account_locked_until);
        """,
        
        # Enhanced indexes for point transactions
        """
        CREATE INDEX IF NOT EXISTS idx_point_transactions_ip_address 
        ON point_transactions(ip_address);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_point_transactions_created_at_giver 
        ON point_transactions(created_at, giver_id);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_point_transactions_created_at_receiver 
        ON point_transactions(created_at, receiver_id);
        """,
        
        # Composite indexes for common queries
        """
        CREATE INDEX IF NOT EXISTS idx_users_role_is_active 
        ON users(role, is_active);
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_users_created_by_role 
        ON users(created_by, role);
        """
    ]
    
    try:
        with engine.connect() as connection:
            for sql in index_statements:
                logger.info(f"Executing: {sql.strip()[:50]}...")
                connection.execute(text(sql))
                connection.commit()
        
        logger.info("Security indexes created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating security indexes: {e}")
        return False


def run_migration():
    """Run the complete security migration"""
    logger.info("Starting security tables migration...")
    
    success = True
    
    # Create new security tables
    if not create_security_tables():
        success = False
    
    # Add security columns to existing tables
    if not add_security_columns_to_existing_tables():
        success = False
    
    # Create security indexes
    if not create_security_indexes():
        success = False
    
    if success:
        logger.info("Security migration completed successfully!")
    else:
        logger.error("Security migration completed with errors. Please check the logs.")
    
    return success


def rollback_migration():
    """Rollback the security migration (for development/testing)"""
    logger.warning("Rolling back security migration...")
    
    rollback_statements = [
        "DROP TABLE IF EXISTS user_activity_logs;",
        "DROP TABLE IF EXISTS user_sessions;",
        "DROP TABLE IF EXISTS blacklisted_tokens;",
        
        # Note: Rolling back column additions is more complex in SQLite
        # You would need to recreate the tables without the new columns
        # For now, we'll just log a warning
    ]
    
    try:
        with engine.connect() as connection:
            for sql in rollback_statements:
                logger.info(f"Executing: {sql}")
                connection.execute(text(sql))
                connection.commit()
        
        logger.warning("Security tables dropped. Note: Added columns to existing tables were not removed.")
        logger.warning("To fully rollback, you may need to restore from a backup.")
        return True
        
    except Exception as e:
        logger.error(f"Error during rollback: {e}")
        return False


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Run the migration
    run_migration()