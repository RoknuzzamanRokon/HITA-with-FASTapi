"""add_performance_indexes_for_user_management

Revision ID: 2e0a8d2a36d1
Revises: 102d4bb3da30
Create Date: 2025-10-12 19:23:50.785534

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e0a8d2a36d1'
down_revision: Union[str, None] = '102d4bb3da30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create additional performance indexes for user management
    # Note: Some basic indexes already exist from model definition and previous migrations
    
    # Additional composite indexes for complex user search and filtering queries
    # Index for role + active status filtering (common dashboard query)
    op.create_index('idx_users_role_active', 'users', ['role', 'is_active'])
    
    # Index for active status + creation date (for active users by date)
    op.create_index('idx_users_active_created', 'users', ['is_active', 'created_at'])
    
    # Index for role + creation date (for user growth by role)
    op.create_index('idx_users_role_created', 'users', ['role', 'created_at'])
    
    # Index for updated_at for recent changes queries
    op.create_index('idx_users_updated_at', 'users', ['updated_at'])
    
    # Additional indexes for user_points table for point-related queries
    op.create_index('idx_user_points_current_points', 'user_points', ['current_points'])
    op.create_index('idx_user_points_total_points', 'user_points', ['total_points'])
    op.create_index('idx_user_points_updated_at', 'user_points', ['updated_at'])
    
    # Additional indexes for point_transactions table for activity tracking
    op.create_index('idx_point_transactions_giver_id', 'point_transactions', ['giver_id'])
    op.create_index('idx_point_transactions_receiver_id', 'point_transactions', ['receiver_id'])
    op.create_index('idx_point_transactions_transaction_type', 'point_transactions', ['transaction_type'])
    
    # Index for recent activity queries (created_at + giver/receiver)
    op.create_index('idx_point_transactions_created_giver', 'point_transactions', ['created_at', 'giver_id'])
    op.create_index('idx_point_transactions_created_receiver', 'point_transactions', ['created_at', 'receiver_id'])
    
    # Indexes for user_provider_permissions table
    op.create_index('idx_user_provider_permissions_user_id', 'user_provider_permissions', ['user_id'])
    op.create_index('idx_user_provider_permissions_provider', 'user_provider_permissions', ['provider_name'])
    
    # Additional composite index for user activity queries (if tables exist)
    # Note: These tables may be created by other migrations
    try:
        op.create_index('idx_user_activity_logs_user_created', 'user_activity_logs', ['user_id', 'created_at'])
    except Exception:
        # Table may not exist yet, skip this index
        pass
    
    try:
        # Composite index for active session queries
        op.create_index('idx_user_sessions_user_active', 'user_sessions', ['user_id', 'is_active'])
    except Exception:
        # Table may not exist yet, skip this index
        pass


def downgrade() -> None:
    """Downgrade schema."""
    # Drop all the indexes created in upgrade
    
    # Users table composite indexes
    op.drop_index('idx_users_updated_at', 'users')
    op.drop_index('idx_users_role_active', 'users')
    op.drop_index('idx_users_active_created', 'users')
    op.drop_index('idx_users_role_created', 'users')
    
    # User points table indexes
    op.drop_index('idx_user_points_current_points', 'user_points')
    op.drop_index('idx_user_points_total_points', 'user_points')
    op.drop_index('idx_user_points_updated_at', 'user_points')
    
    # Point transactions table indexes
    op.drop_index('idx_point_transactions_giver_id', 'point_transactions')
    op.drop_index('idx_point_transactions_receiver_id', 'point_transactions')
    op.drop_index('idx_point_transactions_transaction_type', 'point_transactions')
    op.drop_index('idx_point_transactions_created_giver', 'point_transactions')
    op.drop_index('idx_point_transactions_created_receiver', 'point_transactions')
    
    # User provider permissions table indexes
    op.drop_index('idx_user_provider_permissions_user_id', 'user_provider_permissions')
    op.drop_index('idx_user_provider_permissions_provider', 'user_provider_permissions')
    
    # User activity logs table indexes (if they exist)
    try:
        op.drop_index('idx_user_activity_logs_user_created', 'user_activity_logs')
    except Exception:
        pass
    
    # User sessions table indexes (if they exist)
    try:
        op.drop_index('idx_user_sessions_user_active', 'user_sessions')
    except Exception:
        pass
