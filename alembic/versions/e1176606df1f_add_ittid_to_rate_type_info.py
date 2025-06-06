"""Add ittid to rate_type_info

Revision ID: f3c4d5e6a7b8
Revises: 260c6f83324d
Create Date: 2025-06-01 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'f3c4d5e6a7b8'
down_revision = '260c6f83324d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) Ensure no NULL values remain in contacts.value
    op.execute(
        """
        UPDATE contacts
        SET value = ''
        WHERE value IS NULL;
        """
    )
    # 2) Alter contacts.value to NOT NULL
    op.alter_column(
        'contacts', 'value',
        existing_type=sa.String(length=255),
        nullable=False
    )

    # 3) Alter rate_type_info.ittid to NOT NULL
    op.alter_column(
        'rate_type_info', 'ittid',
        existing_type=mysql.VARCHAR(length=100),
        nullable=False
    )

    # 4) Drop duplicate autogenerated index on rate_type_info if it exists
    try:
        op.drop_index('rate_type_info_ibfk_1_copy', table_name='rate_type_info')
    except Exception:
        pass

    # 5) Create a proper foreign key constraint
    op.create_foreign_key(
        'fk_rate_type_info_ittid_hotels',
        'rate_type_info', 'hotels',
        ['ittid'], ['ittid'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 1) Drop the foreign key constraint
    op.drop_constraint('fk_rate_type_info_ittid_hotels', 'rate_type_info', type_='foreignkey')

    # 2) Revert rate_type_info.ittid to nullable
    op.alter_column(
        'rate_type_info', 'ittid',
        existing_type=mysql.VARCHAR(length=100),
        nullable=True
    )

    # 3) Re-create the duplicated index on rate_type_info
    op.create_index(
        'rate_type_info_ibfk_1_copy',
        'rate_type_info', ['provider_mapping_id'], unique=False
    )

    # 4) Revert contacts.value to nullable
    op.alter_column(
        'contacts', 'value',
        existing_type=mysql.VARCHAR(length=255),
        nullable=True
    )
    # Note: No index drops/creates on provider_mappings and hotels
