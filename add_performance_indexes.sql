-- Performance indexes for user management system
-- This script adds indexes to improve query performance for user management operations
-- Users table composite indexes for complex queries
CREATE INDEX IF NOT EXISTS idx_users_role_active ON users(role, is_active);
CREATE INDEX IF NOT EXISTS idx_users_active_created ON users(is_active, created_at);
CREATE INDEX IF NOT EXISTS idx_users_role_created ON users(role, created_at);
CREATE INDEX IF NOT EXISTS idx_users_updated_at ON users(updated_at);
-- User points table indexes for point-related queries
CREATE INDEX IF NOT EXISTS idx_user_points_current_points ON user_points(current_points);
CREATE INDEX IF NOT EXISTS idx_user_points_total_points ON user_points(total_points);
CREATE INDEX IF NOT EXISTS idx_user_points_updated_at ON user_points(updated_at);
-- Point transactions table indexes for activity tracking
CREATE INDEX IF NOT EXISTS idx_point_transactions_giver_id ON point_transactions(giver_id);
CREATE INDEX IF NOT EXISTS idx_point_transactions_receiver_id ON point_transactions(receiver_id);
CREATE INDEX IF NOT EXISTS idx_point_transactions_transaction_type ON point_transactions(transaction_type);
-- Composite indexes for recent activity queries
CREATE INDEX IF NOT EXISTS idx_point_transactions_created_giver ON point_transactions(created_at, giver_id);
CREATE INDEX IF NOT EXISTS idx_point_transactions_created_receiver ON point_transactions(created_at, receiver_id);
-- User provider permissions table indexes
CREATE INDEX IF NOT EXISTS idx_user_provider_permissions_user_id ON user_provider_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_provider_permissions_provider ON user_provider_permissions(provider_name);
-- User activity logs table indexes (if table exists)
CREATE INDEX IF NOT EXISTS idx_user_activity_logs_user_created ON user_activity_logs(user_id, created_at);
-- User sessions table indexes (if table exists)
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_active ON user_sessions(user_id, is_active);