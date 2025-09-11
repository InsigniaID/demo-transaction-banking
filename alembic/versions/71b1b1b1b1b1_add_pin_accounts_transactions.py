"""Add PIN field and create accounts and transaction_histories tables

Revision ID: 71b1b1b1b1b1
Revises: edbd75dcfc79
Create Date: 2025-09-11 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '71b1b1b1b1b1'
down_revision: Union[str, Sequence[str], None] = 'edbd75dcfc79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Skip adding hashed_pin column as it already exists
    
    # Create accounts table
    op.create_table('accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_number', sa.String(), nullable=False),
        sa.Column('account_type', sa.String(), nullable=False),
        sa.Column('balance', sa.Numeric(15, 2), nullable=False, server_default='0.00'),
        sa.Column('currency', sa.String(), nullable=False, server_default='IDR'),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_accounts_id'), 'accounts', ['id'], unique=False)
    op.create_unique_constraint('uq_accounts_account_number', 'accounts', ['account_number'])
    op.create_index(op.f('ix_accounts_account_number'), 'accounts', ['account_number'], unique=True)
    
    # Create transaction_histories table
    op.create_table('transaction_histories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transaction_id', sa.String(), nullable=False),
        sa.Column('transaction_type', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('currency', sa.String(), nullable=False, server_default='IDR'),
        sa.Column('balance_before', sa.Numeric(15, 2), nullable=False),
        sa.Column('balance_after', sa.Numeric(15, 2), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('reference_number', sa.String(), nullable=True),
        sa.Column('recipient_account', sa.String(), nullable=True),
        sa.Column('recipient_name', sa.String(), nullable=True),
        sa.Column('channel', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transaction_histories_id'), 'transaction_histories', ['id'], unique=False)
    op.create_unique_constraint('uq_transaction_histories_transaction_id', 'transaction_histories', ['transaction_id'])
    op.create_index(op.f('ix_transaction_histories_transaction_id'), 'transaction_histories', ['transaction_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('transaction_histories')
    op.drop_table('accounts')
    op.drop_column('users', 'hashed_pin')