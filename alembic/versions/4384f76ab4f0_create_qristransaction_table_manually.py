"""Create QRISTransaction table manually

Revision ID: 4384f76ab4f0
Revises: f13ca4f32f5b
Create Date: 2025-09-11 22:28:01.615965

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4384f76ab4f0'
down_revision: Union[str, Sequence[str], None] = 'f13ca4f32f5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create qris_transactions table
    op.create_table(
        'qris_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('qris_id', sa.String(), nullable=False),
        sa.Column('customer_id', sa.String(), nullable=False),
        sa.Column('account_number', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('currency', sa.String(), nullable=False, default='IDR'),
        sa.Column('merchant_name', sa.String(), nullable=False),
        sa.Column('merchant_category', sa.String(), nullable=False),
        sa.Column('qris_code', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='ACTIVE'),
        sa.Column('expired_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    
    # Create indexes
    op.create_index('ix_qris_transactions_id', 'qris_transactions', ['id'])
    op.create_index('ix_qris_transactions_qris_id', 'qris_transactions', ['qris_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('ix_qris_transactions_qris_id', table_name='qris_transactions')
    op.drop_index('ix_qris_transactions_id', table_name='qris_transactions')
    
    # Drop table
    op.drop_table('qris_transactions')
