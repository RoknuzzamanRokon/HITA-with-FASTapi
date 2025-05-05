"""Update User model to use string ID

Revision ID: 3f43a88d8576
Revises: 
Create Date: 2025-05-05 23:14:15.352779

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3f43a88d8576'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    # Alter the `id` column to String(10)
    op.alter_column(
        'users',
        'id',
        existing_type=sa.Integer(),
        type_=sa.String(length=10),
        existing_nullable=False
    )

    # Add the `role` column with default value
    op.add_column('users', sa.Column('role', sa.String(length=12), nullable=True))

    # Add the `api_key` column
    op.add_column('users', sa.Column('api_key', sa.String(), nullable=True))

    # Add the `is_active` column with default value
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('1')))

    # Add the `created_at` column
    op.add_column('users', sa.Column('created_at', sa.DateTime(), nullable=True))

    # Add the `updated_at` column
    op.add_column('users', sa.Column('updated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Revert the changes made in the upgrade
    op.alter_column(
        'users',
        'id',
        existing_type=sa.String(length=10),
        type_=sa.Integer(),
        existing_nullable=False
    )

    op.drop_column('users', 'role')
    op.drop_column('users', 'api_key')
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'created_at')
    op.drop_column('users', 'updated_at')