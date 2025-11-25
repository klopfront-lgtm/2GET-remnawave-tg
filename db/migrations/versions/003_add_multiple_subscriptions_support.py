"""add_multiple_subscriptions_support

Revision ID: 003
Revises: 002
Create Date: 2025-11-23 23:47:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Расширение таблицы users
    op.add_column('users', 
        sa.Column('max_subscriptions_limit', sa.Integer(), nullable=False, server_default='1')
    )
    
    # 2. Расширение таблицы subscriptions
    op.add_column('subscriptions', 
        sa.Column('custom_traffic_limit_bytes', sa.BigInteger(), nullable=True)
    )
    op.add_column('subscriptions',
        sa.Column('custom_device_limit', sa.Integer(), nullable=True)
    )
    op.add_column('subscriptions',
        sa.Column('subscription_name', sa.String(length=100), nullable=True)
    )
    op.add_column('subscriptions',
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false')
    )
    op.add_column('subscriptions',
        sa.Column('can_be_deleted', sa.Boolean(), nullable=False, server_default='true')
    )
    
    # 3. Создание индексов
    op.create_index('idx_subscriptions_is_primary', 'subscriptions', ['is_primary'], unique=False)
    op.create_index('idx_subscriptions_user_primary', 'subscriptions', ['user_id', 'is_primary'], unique=False)
    
    # 4. Data migration: пометить существующие активные подписки как primary
    # Помечаем самую свежую активную подписку каждого пользователя как primary
    op.execute("""
        WITH ranked_subs AS (
            SELECT 
                subscription_id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id 
                    ORDER BY end_date DESC NULLS LAST, subscription_id DESC
                ) as rn
            FROM subscriptions
            WHERE is_active = TRUE
        )
        UPDATE subscriptions 
        SET is_primary = TRUE
        WHERE subscription_id IN (
            SELECT subscription_id FROM ranked_subs WHERE rn = 1
        )
    """)
    
    # 5. Data migration: сгенерировать названия для существующих подписок
    op.execute("""
        UPDATE subscriptions s
        SET subscription_name = COALESCE(
            (SELECT t.name FROM tariffs t WHERE t.id = s.tariff_id),
            'Подписка #' || s.subscription_id
        )
        WHERE subscription_name IS NULL
    """)


def downgrade() -> None:
    # Удаление индексов
    op.drop_index('idx_subscriptions_user_primary', table_name='subscriptions')
    op.drop_index('idx_subscriptions_is_primary', table_name='subscriptions')
    
    # Удаление столбцов из subscriptions
    op.drop_column('subscriptions', 'can_be_deleted')
    op.drop_column('subscriptions', 'is_primary')
    op.drop_column('subscriptions', 'subscription_name')
    op.drop_column('subscriptions', 'custom_device_limit')
    op.drop_column('subscriptions', 'custom_traffic_limit_bytes')
    
    # Удаление столбца из users
    op.drop_column('users', 'max_subscriptions_limit')