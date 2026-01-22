"""add_notifications_table

Revision ID: 22fd2f447aad
Revises: 01b3fcaee1e5
Create Date: 2025-11-26 10:52:10.770886

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "22fd2f447aad"
down_revision: Union[str, None] = "01b3fcaee1e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True, index=True),
        sa.Column(
            "user_id",
            sa.String(10),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("type", sa.String(20), nullable=False, index=True),
        sa.Column("priority", sa.String(10), nullable=False, default="medium"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column(
            "status", sa.String(10), nullable=False, default="unread", index=True
        ),
        sa.Column("meta_data", sa.JSON, nullable=True),
        sa.Column(
            "created_at", sa.DateTime, default=sa.func.now(), nullable=False, index=True
        ),
        sa.Column("read_at", sa.DateTime, nullable=True),
    )

    # Create composite index for optimized unread count queries
    op.create_index(
        "idx_notifications_user_status", "notifications", ["user_id", "status"]
    )

    # Create index for chronological ordering and cleanup operations
    op.create_index(
        "idx_notifications_created_status", "notifications", ["created_at", "status"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index("idx_notifications_created_status", "notifications")
    op.drop_index("idx_notifications_user_status", "notifications")

    # Drop table
    op.drop_table("notifications")
