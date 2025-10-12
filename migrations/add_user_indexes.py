"""
Database migration script to add indexes for user management optimization
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import engine


def create_user_indexes():
    """Create indexes for improved query performance"""
    
    indexes = [
        # User table indexes
        ("idx_users_email", "CREATE INDEX idx_users_email ON users(email);"),
        ("idx_users_role", "CREATE INDEX idx_users_role ON users(role);"),
        ("idx_users_is_active", "CREATE INDEX idx_users_is_active ON users(is_active);"),
        ("idx_users_created_at", "CREATE INDEX idx_users_created_at ON users(created_at);"),
        ("idx_users_created_by", "CREATE INDEX idx_users_created_by ON users(created_by);"),
        
        # Composite indexes for common query patterns
        ("idx_users_role_active", "CREATE INDEX idx_users_role_active ON users(role, is_active);"),
        ("idx_users_active_created", "CREATE INDEX idx_users_active_created ON users(is_active, created_at);"),
        
        # UserPoint table indexes
        ("idx_user_points_user_id", "CREATE INDEX idx_user_points_user_id ON user_points(user_id);"),
        ("idx_user_points_current_points", "CREATE INDEX idx_user_points_current_points ON user_points(current_points);"),
        ("idx_user_points_total_points", "CREATE INDEX idx_user_points_total_points ON user_points(total_points);"),
        
        # PointTransaction table indexes
        ("idx_point_transactions_giver_id", "CREATE INDEX idx_point_transactions_giver_id ON point_transactions(giver_id);"),
        ("idx_point_transactions_receiver_id", "CREATE INDEX idx_point_transactions_receiver_id ON point_transactions(receiver_id);"),
        ("idx_point_transactions_created_at", "CREATE INDEX idx_point_transactions_created_at ON point_transactions(created_at);"),
        ("idx_point_transactions_giver_receiver", "CREATE INDEX idx_point_transactions_giver_receiver ON point_transactions(giver_id, receiver_id);"),
        ("idx_point_transactions_created_giver", "CREATE INDEX idx_point_transactions_created_giver ON point_transactions(created_at, giver_id);"),
        ("idx_point_transactions_created_receiver", "CREATE INDEX idx_point_transactions_created_receiver ON point_transactions(created_at, receiver_id);"),
        
        # UserProviderPermission table indexes
        ("idx_user_provider_permissions_user_id", "CREATE INDEX idx_user_provider_permissions_user_id ON user_provider_permissions(user_id);"),
        ("idx_user_provider_permissions_provider_name", "CREATE INDEX idx_user_provider_permissions_provider_name ON user_provider_permissions(provider_name);"),
        
        # UserActivityLog table indexes
        ("idx_user_activity_logs_user_id", "CREATE INDEX idx_user_activity_logs_user_id ON user_activity_logs(user_id);"),
        ("idx_user_activity_logs_created_at", "CREATE INDEX idx_user_activity_logs_created_at ON user_activity_logs(created_at);"),
        ("idx_user_activity_logs_action", "CREATE INDEX idx_user_activity_logs_action ON user_activity_logs(action);"),
        
        # UserSession table indexes
        ("idx_user_sessions_user_id", "CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);"),
        ("idx_user_sessions_is_active", "CREATE INDEX idx_user_sessions_is_active ON user_sessions(is_active);"),
        ("idx_user_sessions_expires_at", "CREATE INDEX idx_user_sessions_expires_at ON user_sessions(expires_at);"),
        ("idx_user_sessions_last_activity", "CREATE INDEX idx_user_sessions_last_activity ON user_sessions(last_activity);"),
    ]
    
    with engine.connect() as connection:
        for index_name, index_sql in indexes:
            try:
                # Check if index already exists
                table_name = index_sql.split(' ON ')[1].split('(')[0].strip()
                check_sql = f"SHOW INDEX FROM {table_name} WHERE Key_name = '{index_name}'"
                result = connection.execute(text(check_sql)).fetchall()
                
                if not result:
                    connection.execute(text(index_sql))
                    print(f"✓ Created index: {index_name}")
                else:
                    print(f"⚠ Index already exists: {index_name}")
            except Exception as e:
                print(f"✗ Failed to create index {index_name}: {e}")
                import traceback
                traceback.print_exc()
        
        connection.commit()


def drop_user_indexes():
    """Drop the created indexes (for rollback)"""
    
    indexes_to_drop = [
        ("users", "idx_users_email"),
        ("users", "idx_users_role"),
        ("users", "idx_users_is_active"),
        ("users", "idx_users_created_at"),
        ("users", "idx_users_created_by"),
        ("users", "idx_users_role_active"),
        ("users", "idx_users_active_created"),
        ("user_points", "idx_user_points_user_id"),
        ("user_points", "idx_user_points_current_points"),
        ("user_points", "idx_user_points_total_points"),
        ("point_transactions", "idx_point_transactions_giver_id"),
        ("point_transactions", "idx_point_transactions_receiver_id"),
        ("point_transactions", "idx_point_transactions_created_at"),
        ("point_transactions", "idx_point_transactions_giver_receiver"),
        ("point_transactions", "idx_point_transactions_created_giver"),
        ("point_transactions", "idx_point_transactions_created_receiver"),
        ("user_provider_permissions", "idx_user_provider_permissions_user_id"),
        ("user_provider_permissions", "idx_user_provider_permissions_provider_name"),
        ("user_activity_logs", "idx_user_activity_logs_user_id"),
        ("user_activity_logs", "idx_user_activity_logs_created_at"),
        ("user_activity_logs", "idx_user_activity_logs_action"),
        ("user_sessions", "idx_user_sessions_user_id"),
        ("user_sessions", "idx_user_sessions_is_active"),
        ("user_sessions", "idx_user_sessions_expires_at"),
        ("user_sessions", "idx_user_sessions_last_activity"),
    ]
    
    with engine.connect() as connection:
        for table_name, index_name in indexes_to_drop:
            try:
                drop_sql = f"DROP INDEX {index_name} ON {table_name}"
                connection.execute(text(drop_sql))
                print(f"✓ Dropped index: {index_name}")
            except Exception as e:
                print(f"✗ Failed to drop index {index_name}: {e}")
        
        connection.commit()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        print("Rolling back user indexes...")
        drop_user_indexes()
        print("Rollback completed.")
    else:
        print("Creating user indexes for optimization...")
        create_user_indexes()
        print("Index creation completed.")