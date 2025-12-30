"""add_export_jobs_table

Revision ID: a917d5cf0216
Revises: deeb66a55c0f
Create Date: 2025-11-16 12:40:37.442463

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a917d5cf0216'
down_revision: Union[str, None] = 'deeb66a55c0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create export_jobs table
    op.create_table(
        'export_jobs',
        sa.Column('id', sa.String(50), primary_key=True, index=True),
        sa.Column('user_id', sa.String(10), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('export_type', sa.String(50), nullable=False),
        sa.Column('format', sa.String(10), nullable=False),
        sa.Column('filters', sa.JSON, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending', index=True),
        sa.Column('progress_percentage', sa.Integer, default=0),
        sa.Column('processed_records', sa.Integer, default=0),
        sa.Column('total_records', sa.Integer, nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_size_bytes', sa.Integer, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now(), index=True),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=True, index=True)
    )
    
    # Create additional indexes for performance
    op.create_index('idx_export_jobs_user_status', 'export_jobs', ['user_id', 'status'])
    op.create_index('idx_export_jobs_created_status', 'export_jobs', ['created_at', 'status'])
    op.create_index('idx_export_jobs_expires_status', 'export_jobs', ['expires_at', 'status'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_export_jobs_expires_status', 'export_jobs')
    op.drop_index('idx_export_jobs_created_status', 'export_jobs')
    op.drop_index('idx_export_jobs_user_status', 'export_jobs')
    
    # Drop table
    op.drop_table('export_jobs')
