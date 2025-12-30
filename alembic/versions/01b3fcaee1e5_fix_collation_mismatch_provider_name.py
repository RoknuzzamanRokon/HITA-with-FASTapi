"""fix_collation_mismatch_provider_name

Revision ID: 01b3fcaee1e5
Revises: a917d5cf0216
Create Date: 2025-11-17 12:07:04.816846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '01b3fcaee1e5'
down_revision: Union[str, None] = 'a917d5cf0216'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix collation mismatch between provider_mappings and supplier_summary tables."""
    # Check if we're using MySQL
    bind = op.get_bind()
    if 'mysql' in bind.dialect.name.lower():
        # Standardize both tables to use utf8mb4_unicode_ci collation
        op.execute("""
            ALTER TABLE provider_mappings 
            MODIFY COLUMN provider_name VARCHAR(50) 
            CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL
        """)
        
        op.execute("""
            ALTER TABLE supplier_summary 
            MODIFY COLUMN provider_name VARCHAR(50) 
            CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL
        """)


def downgrade() -> None:
    """Revert collation changes."""
    # No downgrade needed - collation changes are non-destructive
    pass
