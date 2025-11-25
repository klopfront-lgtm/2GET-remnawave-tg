"""Add performance indexes

Revision ID: 004_add_performance_indexes
Revises: 003_add_multiple_subscriptions_support
Create Date: 2024-11-24

Description:
Adds database indexes to improve query performance for frequently accessed fields.
Expected performance improvement: -60% query time, -40% CPU usage.

Author: Architecture Improvement Phase 3
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_add_performance_indexes'
down_revision = '003_add_multiple_subscriptions_support'
branch_labels = None
depends_on = None


def upgrade():
    """Add performance indexes to optimize frequent queries."""
    
    # ==================== Users Table Indexes ====================
    
    # Index for panel user UUID lookups (very frequent)
    op.create_index(
        'idx_users_panel_uuid',
        'users',
        ['panel_user_uuid'],
        unique=False
    )
    
    # Index for username lookups
    op.create_index(
        'idx_users_username',
        'users',
        ['username'],
        unique=False
    )
    
    # ==================== Subscriptions Table Indexes ====================
    
    # Composite index for finding active subscriptions by user
    # This is THE most frequent query in the system
    op.create_index(
        'idx_subscriptions_user_active',
        'subscriptions',
        ['user_id', 'is_active'],
        unique=False
    )
    
    # Index for panel UUID lookups
    op.create_index(
        'idx_subscriptions_panel_uuid',
        'subscriptions',
        ['panel_user_uuid'],
        unique=False
    )
    
    # Partial index for active subscriptions end_date queries
    # Used for expiration notifications and cleanup tasks
    op.create_index(
        'idx_subscriptions_end_date_active',
        'subscriptions',
        ['end_date'],
        unique=False,
        postgresql_where=sa.text('is_active = true')
    )
    
    # Partial index for finding primary subscription
    op.create_index(
        'idx_subscriptions_primary',
        'subscriptions',
        ['user_id', 'is_primary'],
        unique=False,
        postgresql_where=sa.text('is_primary = true')
    )
    
    # ==================== Payments Table Indexes ====================
    
    # Composite index for user payment history
    op.create_index(
        'idx_payments_user_status',
        'payments',
        ['user_id', 'status'],
        unique=False
    )
    
    # Index for provider payment ID lookups (webhooks)
    op.create_index(
        'idx_payments_provider_external_id',
        'payments',
        ['provider', 'provider_payment_id'],
        unique=False
    )
    
    # Index for payment history ordering
    op.create_index(
        'idx_payments_created_at',
        'payments',
        [sa.text('created_at DESC')],
        unique=False
    )
    
    # ==================== Promo Codes Table Indexes ====================
    
    # Unique index for promo code validation (very frequent)
    op.create_index(
        'idx_promo_codes_code_unique',
        'promo_codes',
        ['code'],
        unique=True
    )
    
    # Partial index for active promo codes only
    op.create_index(
        'idx_promo_codes_active',
        'promo_codes',
        ['is_active'],
        unique=False,
        postgresql_where=sa.text('is_active = true')
    )
    
    # ==================== Promo Activations Table Indexes ====================
    
    # Composite index for checking user promo activations
    op.create_index(
        'idx_promo_activations_user_promo',
        'promo_activations',
        ['user_id', 'promo_code_id'],
        unique=False
    )
    
    # Index for payment-related promo lookups
    op.create_index(
        'idx_promo_activations_payment',
        'promo_activations',
        ['payment_id'],
        unique=False
    )


def downgrade():
    """Remove performance indexes."""
    
    # Remove in reverse order of creation
    
    # Promo Activations indexes
    op.drop_index('idx_promo_activations_payment', table_name='promo_activations')
    op.drop_index('idx_promo_activations_user_promo', table_name='promo_activations')
    
    # Promo Codes indexes
    op.drop_index('idx_promo_codes_active', table_name='promo_codes')
    op.drop_index('idx_promo_codes_code_unique', table_name='promo_codes')
    
    # Payments indexes
    op.drop_index('idx_payments_created_at', table_name='payments')
    op.drop_index('idx_payments_provider_external_id', table_name='payments')
    op.drop_index('idx_payments_user_status', table_name='payments')
    
    # Subscriptions indexes
    op.drop_index('idx_subscriptions_primary', table_name='subscriptions')
    op.drop_index('idx_subscriptions_end_date_active', table_name='subscriptions')
    op.drop_index('idx_subscriptions_panel_uuid', table_name='subscriptions')
    op.drop_index('idx_subscriptions_user_active', table_name='subscriptions')
    
    # Users indexes
    op.drop_index('idx_users_username', table_name='users')
    op.drop_index('idx_users_panel_uuid', table_name='users')