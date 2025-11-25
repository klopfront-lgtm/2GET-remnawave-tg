"""add_tariffs_balance_discounts

Revision ID: 001
Revises: 
Create Date: 2025-11-23 21:47:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tariffs table
    op.create_table('tariffs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column('traffic_limit_bytes', sa.BigInteger(), nullable=True),
        sa.Column('device_limit', sa.Integer(), nullable=True),
        sa.Column('speed_limit_mbps', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create user_balances table
    op.create_table('user_balances',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('operation_type', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_balances_user_id'), 'user_balances', ['user_id'], unique=False)
    
    # Create user_discounts table
    op.create_table('user_discounts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('discount_percentage', sa.Float(), nullable=False),
        sa.Column('tariff_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['tariff_id'], ['tariffs.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_discounts_user_id'), 'user_discounts', ['user_id'], unique=False)
    
    # Add tariff_id column to subscriptions table
    op.add_column('subscriptions', sa.Column('tariff_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_subscriptions_tariff_id', 'subscriptions', 'tariffs', ['tariff_id'], ['id'])
    
    # Add tariff_id column to payments table
    op.add_column('payments', sa.Column('tariff_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_payments_tariff_id', 'payments', 'tariffs', ['tariff_id'], ['id'])


def downgrade() -> None:
    # Drop foreign key and column from payments
    op.drop_constraint('fk_payments_tariff_id', 'payments', type_='foreignkey')
    op.drop_column('payments', 'tariff_id')
    
    # Drop foreign key and column from subscriptions
    op.drop_constraint('fk_subscriptions_tariff_id', 'subscriptions', type_='foreignkey')
    op.drop_column('subscriptions', 'tariff_id')
    
    # Drop user_discounts table
    op.drop_index(op.f('ix_user_discounts_user_id'), table_name='user_discounts')
    op.drop_table('user_discounts')
    
    # Drop user_balances table
    op.drop_index(op.f('ix_user_balances_user_id'), table_name='user_balances')
    op.drop_table('user_balances')
    
    # Drop tariffs table
    op.drop_table('tariffs')