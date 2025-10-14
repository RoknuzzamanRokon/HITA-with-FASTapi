"""merge_heads

Revision ID: 102d4bb3da30
Revises: 0acce6a01a31, add_user_activity_and_sessions_focused
Create Date: 2025-10-12 19:23:39.333118

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '102d4bb3da30'
down_revision: Union[str, None] = ('0acce6a01a31', 'add_user_activity_and_sessions_focused')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
