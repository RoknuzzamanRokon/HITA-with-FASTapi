"""add_user_activity_logs_and_sessions_tables_focused

Revision ID: add_user_activity_and_sessions_focused
Revises: 
Create Date: 2025-10-12 17:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'add_user_activity_and_sessions_focused'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add user activity logs and sessions tables."""
    
    # Create user_activity_logs table
    op.create_table('user_activity_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=10), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for user_activity_logs
    op.create_index('ix_user_activity_logs_id', 'user_activity_logs', ['id'], unique=False)
    op.create_index('ix_user_activity_logs_user_id', 'user_activity_logs', ['user_id'], unique=False)
    op.create_index('ix_user_activity_logs_action', 'user_activity_logs', ['action'], unique=False)
    op.create_index('ix_user_activity_logs_created_at', 'user_activity_logs', ['created_at'], unique=False)
    
    # Create user_sessions table
    op.create_table('user_sessions',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_activity', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for user_sessions
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'], unique=False)
    op.create_index('ix_user_sessions_is_active', 'user_sessions', ['is_active'], unique=False)
    op.create_index('ix_user_sessions_expires_at', 'user_sessions', ['expires_at'], unique=False)
    op.create_index('ix_user_sessions_last_activity', 'user_sessions', ['last_activity'], unique=False)
    
    # Add performance indexes for existing tables to support new queries
    # Index for users table to support enhanced queries
    op.create_index('ix_users_email', 'users', ['email'], unique=False)
    op.create_index('ix_users_role', 'users', ['role'], unique=False)
    op.create_index('ix_users_is_active', 'users', ['is_active'], unique=False)
    op.create_index('ix_users_created_at', 'users', ['created_at'], unique=False)
    
    # Index for point_transactions to support activity status queries
    op.create_index('ix_point_transactions_giver_receiver', 'point_transactions', ['giver_id', 'receiver_id'], unique=False)
    op.create_index('ix_point_transactions_created_at', 'point_transactions', ['created_at'], unique=False)
    
    # Index for user_points to support balance queries
    op.create_index('ix_user_points_user_id', 'user_points', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema - Remove user activity logs and sessions tables."""
    
    # Drop indexes for existing tables
    op.drop_index('ix_user_points_user_id', table_name='user_points')
    op.drop_index('ix_point_transactions_created_at', table_name='point_transactions')
    op.drop_index('ix_point_transactions_giver_receiver', table_name='point_transactions')
    op.drop_index('ix_users_created_at', table_name='users')
    op.drop_index('ix_users_is_active', table_name='users')
    op.drop_index('ix_users_role', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    
    # Drop user_sessions table and its indexes
    op.drop_index('ix_user_sessions_last_activity', table_name='user_sessions')
    op.drop_index('ix_user_sessions_expires_at', table_name='user_sessions')
    op.drop_index('ix_user_sessions_is_active', table_name='user_sessions')
    op.drop_index('ix_user_sessions_user_id', table_name='user_sessions')
    op.drop_table('user_sessions')
    
    # Drop user_activity_logs table and its indexes
    op.drop_index('ix_user_activity_logs_created_at', table_name='user_activity_logs')
    op.drop_index('ix_user_activity_logs_action', table_name='user_activity_logs')
    op.drop_index('ix_user_activity_logs_user_id', table_name='user_activity_logs')
    op.drop_index('ix_user_activity_logs_id', table_name='user_activity_logs')
    op.drop_table('user_activity_logs')