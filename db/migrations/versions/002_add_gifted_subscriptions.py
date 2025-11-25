"""add_gifted_subscriptions

Revision ID: 002
Revises: 001
Create Date: 2025-11-23 23:09:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types for PostgreSQL
    gift_recipient_type = postgresql.ENUM('random', 'direct', name='giftrecipienttype', create_type=True)
    gift_recipient_type.create(op.get_bind(), checkfirst=True)
    
    gift_status = postgresql.ENUM(
        'pending_payment',
        'payment_failed',
        'ready',
        'activated',
        'expired',
        'cancelled',
        'refunded',
        name='giftstatus',
        create_type=True
    )
    gift_status.create(op.get_bind(), checkfirst=True)
    
    # Create gifted_subscriptions table
    op.create_table('gifted_subscriptions',
        # Идентификация подарка
        sa.Column('gift_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('gift_code', sa.String(length=32), nullable=False),
        
        # Даритель
        sa.Column('donor_user_id', sa.BigInteger(), nullable=False),
        sa.Column('donor_username', sa.String(), nullable=True),
        sa.Column('donor_lock_key', sa.String(length=64), nullable=True),
        
        # Получатель
        sa.Column('recipient_type', gift_recipient_type, nullable=False),
        sa.Column('recipient_user_id', sa.BigInteger(), nullable=True),
        sa.Column('recipient_username', sa.String(), nullable=True),
        
        # Конфигурация подарка
        sa.Column('tariff_id', sa.Integer(), nullable=False),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        
        # Платежная информация
        sa.Column('payment_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        
        # Статусы и временные метки
        sa.Column('status', gift_status, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        
        # Метаданные и защита
        sa.Column('idempotency_key', sa.String(length=64), nullable=False),
        sa.Column('message_to_recipient', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        
        # Constraints
        sa.PrimaryKeyConstraint('gift_id'),
        sa.ForeignKeyConstraint(['donor_user_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['recipient_user_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['tariff_id'], ['tariffs.id'], ),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.payment_id'], ),
        sa.UniqueConstraint('gift_code'),
        sa.UniqueConstraint('payment_id'),
        sa.UniqueConstraint('idempotency_key')
    )
    
    # Create single-column indexes
    op.create_index(op.f('ix_gifted_subscriptions_gift_code'), 'gifted_subscriptions', ['gift_code'], unique=True)
    op.create_index(op.f('ix_gifted_subscriptions_donor_user_id'), 'gifted_subscriptions', ['donor_user_id'], unique=False)
    op.create_index(op.f('ix_gifted_subscriptions_donor_lock_key'), 'gifted_subscriptions', ['donor_lock_key'], unique=False)
    op.create_index(op.f('ix_gifted_subscriptions_recipient_type'), 'gifted_subscriptions', ['recipient_type'], unique=False)
    op.create_index(op.f('ix_gifted_subscriptions_recipient_user_id'), 'gifted_subscriptions', ['recipient_user_id'], unique=False)
    op.create_index(op.f('ix_gifted_subscriptions_payment_id'), 'gifted_subscriptions', ['payment_id'], unique=True)
    op.create_index(op.f('ix_gifted_subscriptions_status'), 'gifted_subscriptions', ['status'], unique=False)
    op.create_index(op.f('ix_gifted_subscriptions_expires_at'), 'gifted_subscriptions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_gifted_subscriptions_idempotency_key'), 'gifted_subscriptions', ['idempotency_key'], unique=True)
    
    # Create composite indexes for optimized queries
    op.create_index('ix_gifted_subs_status_expires', 'gifted_subscriptions', ['status', 'expires_at'], unique=False)
    op.create_index('ix_gifted_subs_donor_status', 'gifted_subscriptions', ['donor_user_id', 'status'], unique=False)
    op.create_index('ix_gifted_subs_recipient_status', 'gifted_subscriptions', ['recipient_user_id', 'status'], unique=False)


def downgrade() -> None:
    # Drop composite indexes
    op.drop_index('ix_gifted_subs_recipient_status', table_name='gifted_subscriptions')
    op.drop_index('ix_gifted_subs_donor_status', table_name='gifted_subscriptions')
    op.drop_index('ix_gifted_subs_status_expires', table_name='gifted_subscriptions')
    
    # Drop single-column indexes
    op.drop_index(op.f('ix_gifted_subscriptions_idempotency_key'), table_name='gifted_subscriptions')
    op.drop_index(op.f('ix_gifted_subscriptions_expires_at'), table_name='gifted_subscriptions')
    op.drop_index(op.f('ix_gifted_subscriptions_status'), table_name='gifted_subscriptions')
    op.drop_index(op.f('ix_gifted_subscriptions_payment_id'), table_name='gifted_subscriptions')
    op.drop_index(op.f('ix_gifted_subscriptions_recipient_user_id'), table_name='gifted_subscriptions')
    op.drop_index(op.f('ix_gifted_subscriptions_recipient_type'), table_name='gifted_subscriptions')
    op.drop_index(op.f('ix_gifted_subscriptions_donor_lock_key'), table_name='gifted_subscriptions')
    op.drop_index(op.f('ix_gifted_subscriptions_donor_user_id'), table_name='gifted_subscriptions')
    op.drop_index(op.f('ix_gifted_subscriptions_gift_code'), table_name='gifted_subscriptions')
    
    # Drop table
    op.drop_table('gifted_subscriptions')
    
    # Drop enum types
    sa.Enum(name='giftstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='giftrecipienttype').drop(op.get_bind(), checkfirst=True)