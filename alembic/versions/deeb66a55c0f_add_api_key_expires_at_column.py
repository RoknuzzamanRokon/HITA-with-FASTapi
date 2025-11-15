"""add_api_key_expires_at_column

Revision ID: deeb66a55c0f
Revises: 2e0a8d2a36d1
Create Date: 2025-11-15 13:33:52.671233

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'deeb66a55c0f'
down_revision: Union[str, None] = '2e0a8d2a36d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add api_key_expires_at column to users table
    op.add_column('users', sa.Column('api_key_expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove api_key_expires_at column from users table
    op.drop_column('users', 'api_key_expires_at')
