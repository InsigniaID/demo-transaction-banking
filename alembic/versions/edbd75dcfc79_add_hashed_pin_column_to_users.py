"""add_hashed_pin_column_to_users

Revision ID: edbd75dcfc79
Revises: 
Create Date: 2025-09-11 21:41:37.077569

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'edbd75dcfc79'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add hashed_pin column to users table."""
    # Add hashed_pin column as nullable first
    op.add_column('users', sa.Column('hashed_pin', sa.String(), nullable=True))
    
    # For existing users, set a default hashed PIN (you should update this with proper values)
    # This is a placeholder - in production, you'd want to handle existing users properly
    op.execute("UPDATE users SET hashed_pin = '$2b$12$default' WHERE hashed_pin IS NULL")
    
    # Make the column NOT NULL after setting values
    op.alter_column('users', 'hashed_pin', nullable=False)


def downgrade() -> None:
    """Remove hashed_pin column from users table."""
    op.drop_column('users', 'hashed_pin')
