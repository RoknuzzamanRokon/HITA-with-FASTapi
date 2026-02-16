"""add free trial requests table

Revision ID: add_free_trial_001
Revises:
Create Date: 2026-02-16 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = "add_free_trial_001"
down_revision = None  # Update this to your latest migration revision
branch_labels = None
depends_on = None


def upgrade():
    # Create free_trial_status_enum type
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS free_trial_requests (
            id VARCHAR(50) PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            business_name VARCHAR(200) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            phone_number VARCHAR(20) NOT NULL,
            message TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            notes TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by VARCHAR(100)
        )
    """
    )

    # Create indexes
    op.create_index("ix_free_trial_requests_id", "free_trial_requests", ["id"])
    op.create_index("ix_free_trial_requests_email", "free_trial_requests", ["email"])
    op.create_index("ix_free_trial_requests_status", "free_trial_requests", ["status"])
    op.create_index(
        "ix_free_trial_requests_created_at", "free_trial_requests", ["created_at"]
    )


def downgrade():
    # Drop indexes
    op.drop_index("ix_free_trial_requests_created_at", "free_trial_requests")
    op.drop_index("ix_free_trial_requests_status", "free_trial_requests")
    op.drop_index("ix_free_trial_requests_email", "free_trial_requests")
    op.drop_index("ix_free_trial_requests_id", "free_trial_requests")

    # Drop table
    op.drop_table("free_trial_requests")
