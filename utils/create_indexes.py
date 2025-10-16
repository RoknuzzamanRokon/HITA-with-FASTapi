#!/usr/bin/env python3
"""
Script to create performance indexes for user management system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine
from sqlalchemy import text

def create_performance_indexes():
    """Create performance indexes for user management"""
    
    indexes = [
        # Users table composite indexes for complex queries
        ("idx_users_role_active", "CREATE INDEX idx_users_role_active ON users(role, is_active)"),
        ("idx_users_active_created", "CREATE INDEX idx_users_active_created ON users(is_active, created_at)"),
        ("idx_users_role_created", "CREATE INDEX idx_users_role_created ON users(role, created_at)"),
        ("idx_users_updated_at", "CREATE INDEX idx_users_updated_at ON users(updated_at)"),
        
        # User points table indexes for point-related queries
        ("idx_user_points_current_points", "CREATE INDEX idx_user_points_current_points ON user_points(current_points)"),
        ("idx_user_points_total_points", "CREATE INDEX idx_user_points_total_points ON user_points(total_points)"),
        ("idx_user_points_updated_at", "CREATE INDEX idx_user_points_updated_at ON user_points(updated_at)"),
        
        # Point transactions table indexes for activity tracking
        ("idx_point_transactions_giver_id", "CREATE INDEX idx_point_transactions_giver_id ON point_transactions(giver_id)"),
        ("idx_point_transactions_receiver_id", "CREATE INDEX idx_point_transactions_receiver_id ON point_transactions(receiver_id)"),
        ("idx_point_transactions_transaction_type", "CREATE INDEX idx_point_transactions_transaction_type ON point_transactions(transaction_type)"),
        
        # Composite indexes for recent activity queries
        ("idx_point_transactions_created_giver", "CREATE INDEX idx_point_transactions_created_giver ON point_transactions(created_at, giver_id)"),
        ("idx_point_transactions_created_receiver", "CREATE INDEX idx_point_transactions_created_receiver ON point_transactions(created_at, receiver_id)"),
        
        # User provider permissions table indexes
        ("idx_user_provider_permissions_user_id", "CREATE INDEX idx_user_provider_permissions_user_id ON user_provider_permissions(user_id)"),
        ("idx_user_provider_permissions_provider", "CREATE INDEX idx_user_provider_permissions_provider ON user_provider_permissions(provider_name)"),
        
        # User activity logs table indexes (if table exists)
        ("idx_user_activity_logs_user_created", "CREATE INDEX idx_user_activity_logs_user_created ON user_activity_logs(user_id, created_at)"),
        
        # User sessions table indexes (if table exists)
        ("idx_user_sessions_user_active", "CREATE INDEX idx_user_sessions_user_active ON user_sessions(user_id, is_active)")
    ]
    
    with engine.connect() as connection:
        for index_name, index_sql in indexes:
            try:
                # Check if index already exists
                check_sql = f"SHOW INDEX FROM {index_sql.split(' ON ')[1].split('(')[0]} WHERE Key_name = '{index_name}'"
                result = connection.execute(text(check_sql))
                if result.fetchone():
                    print(f"Index {index_name} already exists, skipping...")
                    continue
                    
                print(f"Creating index: {index_name}...")
                connection.execute(text(index_sql))
                connection.commit()
                print("✓ Success")
            except Exception as e:
                print(f"✗ Error creating {index_name}: {e}")
                continue
    
    print("\nPerformance indexes creation completed!")

if __name__ == "__main__":
    create_performance_indexes()