"""Migrate database schema

Revision ID: be5292f9309f
Revises: 151aca250ee0
Create Date: 2025-05-08 23:57:49.951861

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be5292f9309f'
down_revision: Union[str, None] = '151aca250ee0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_blacklisted_tokens_id', table_name='blacklisted_tokens')
    op.drop_index('ix_blacklisted_tokens_token', table_name='blacklisted_tokens')
    op.drop_table('blacklisted_tokens')
    op.drop_table('user_points')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_id', table_name='users')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_table('users')
    op.drop_index('ix_point_transactions_id', table_name='point_transactions')
    op.drop_table('point_transactions')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('point_transactions',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('giver_id', sa.VARCHAR(length=64), nullable=True),
    sa.Column('giver_email', sa.VARCHAR(length=255), nullable=True),
    sa.Column('receiver_id', sa.VARCHAR(length=64), nullable=True),
    sa.Column('receiver_email', sa.VARCHAR(length=255), nullable=True),
    sa.Column('points', sa.INTEGER(), nullable=False),
    sa.Column('transaction_type', sa.VARCHAR(length=20), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['giver_email'], ['users.email'], ),
    sa.ForeignKeyConstraint(['giver_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['receiver_email'], ['users.email'], ),
    sa.ForeignKeyConstraint(['receiver_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_point_transactions_id', 'point_transactions', ['id'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.VARCHAR(length=10), nullable=False),
    sa.Column('username', sa.VARCHAR(), nullable=True),
    sa.Column('email', sa.VARCHAR(), nullable=True),
    sa.Column('hashed_password', sa.VARCHAR(), nullable=True),
    sa.Column('role', sa.VARCHAR(length=12), nullable=True),
    sa.Column('api_key', sa.VARCHAR(), nullable=True),
    sa.Column('is_active', sa.BOOLEAN(), nullable=True),
    sa.Column('created_at', sa.DATETIME(), nullable=True),
    sa.Column('updated_at', sa.DATETIME(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_username', 'users', ['username'], unique=1)
    op.create_index('ix_users_id', 'users', ['id'], unique=False)
    op.create_index('ix_users_email', 'users', ['email'], unique=1)
    op.create_table('user_points',
    sa.Column('user_id', sa.VARCHAR(length=10), nullable=False),
    sa.Column('user_email', sa.VARCHAR(length=255), nullable=True),
    sa.Column('total_points', sa.INTEGER(), nullable=True),
    sa.Column('current_points', sa.INTEGER(), nullable=True),
    sa.Column('total_used_points', sa.INTEGER(), nullable=True),
    sa.Column('updated_at', sa.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['user_email'], ['users.email'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('blacklisted_tokens',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('token', sa.VARCHAR(), nullable=True),
    sa.Column('created_at', sa.DATETIME(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_blacklisted_tokens_token', 'blacklisted_tokens', ['token'], unique=1)
    op.create_index('ix_blacklisted_tokens_id', 'blacklisted_tokens', ['id'], unique=False)
    # ### end Alembic commands ###
