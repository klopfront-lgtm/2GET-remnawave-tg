from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, ForeignKey, UniqueConstraint, Text, BigInteger, JSON, Enum, Index
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
import enum


class Base(AsyncAttrs, DeclarativeBase):
    pass


class GiftRecipientType(enum.Enum):
    """Тип получателя подарочной подписки"""
    random = "random"  # Случайный получатель через маркетплейс
    direct = "direct"  # Прямое дарение конкретному пользователю


class GiftStatus(enum.Enum):
    """Статус подарочной подписки"""
    pending_payment = "pending_payment"  # Ожидает оплаты
    payment_failed = "payment_failed"    # Оплата не прошла
    ready = "ready"                      # Оплачен, готов к активации
    activated = "activated"              # Активирован получателем
    expired = "expired"                  # Истек срок активации
    cancelled = "cancelled"              # Отменен дарителем
    refunded = "refunded"                # Возврат средств выполнен


class User(Base):
    """
    Модель пользователя системы.
    
    user_id: Telegram ID пользователя
    username: Telegram username
    first_name: Имя пользователя
    last_name: Фамилия пользователя
    language_code: Код языка пользователя (по умолчанию 'ru')
    registration_date: Дата регистрации
    is_banned: Флаг блокировки пользователя
    panel_user_uuid: UUID пользователя в панели управления
    referral_code: Реферальный код пользователя
    referred_by_id: ID пользователя, пригласившего данного пользователя
    channel_subscription_verified: Флаг подписки на канал
    channel_subscription_checked_at: Время последней проверки подписки
    channel_subscription_verified_for: ID канала, на который подписан
    balance: Баланс пользователя
    max_subscriptions_limit: Максимальное количество одновременных подписок (по умолчанию 1)
    """
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    language_code = Column(String, default="ru")
    registration_date = Column(DateTime(timezone=True),
                               server_default=func.now())
    is_banned = Column(Boolean, default=False)
    panel_user_uuid = Column(String, nullable=True, unique=True, index=True)
    referral_code = Column(String(16), nullable=True, unique=True, index=True)
    referred_by_id = Column(BigInteger,
                            ForeignKey("users.user_id"),
                            nullable=True)
    channel_subscription_verified = Column(Boolean, nullable=True)
    channel_subscription_checked_at = Column(DateTime(timezone=True),
                                             nullable=True)
    channel_subscription_verified_for = Column(BigInteger, nullable=True)
    balance = Column(Float, default=0.0)
    max_subscriptions_limit = Column(Integer, nullable=False, default=1)

    referrer = relationship("User", remote_side=[user_id], backref="referrals")
    subscriptions = relationship("Subscription",
                                 back_populates="user",
                                 cascade="all, delete-orphan")
    payments = relationship("Payment",
                            back_populates="user",
                            cascade="all, delete-orphan")
    promo_code_activations = relationship("PromoCodeActivation",
                                          back_populates="user",
                                          cascade="all, delete-orphan")
    message_logs_authored = relationship("MessageLog",
                                         foreign_keys="MessageLog.user_id",
                                         back_populates="author_user",
                                         cascade="all, delete-orphan")
    message_logs_targeted = relationship(
        "MessageLog",
        foreign_keys="MessageLog.target_user_id",
        back_populates="target_user",
        cascade="all, delete-orphan")
    
    balance_operations = relationship("UserBalance", back_populates="user", cascade="all, delete-orphan")
    discounts = relationship("UserDiscount", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(user_id={self.user_id}, username='{self.username}')>"


class Tariff(Base):
    __tablename__ = "tariffs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    currency = Column(String, default="RUB")
    duration_days = Column(Integer, nullable=False)
    traffic_limit_bytes = Column(BigInteger, nullable=True)
    device_limit = Column(Integer, nullable=True)
    speed_limit_mbps = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    subscriptions = relationship("Subscription", back_populates="tariff")
    discounts = relationship("UserDiscount", back_populates="tariff")


class Subscription(Base):
    """
    Модель подписки пользователя.
    
    subscription_id: ID подписки
    user_id: ID пользователя
    tariff_id: ID тарифа
    panel_user_uuid: UUID пользователя в панели
    panel_subscription_uuid: UUID подписки в панели
    start_date: Дата начала подписки
    end_date: Дата окончания подписки
    duration_months: Длительность в месяцах
    is_active: Активна ли подписка
    status_from_panel: Статус из панели
    traffic_limit_bytes: Лимит трафика в байтах
    traffic_used_bytes: Использованный трафик в байтах
    last_notification_sent: Время последнего уведомления
    provider: Провайдер платежа
    skip_notifications: Пропускать уведомления
    auto_renew_enabled: Включено ли автопродление
    custom_traffic_limit_bytes: Персональный лимит трафика (переопределяет лимит тарифа)
    custom_device_limit: Персональный лимит устройств (переопределяет лимит тарифа)
    subscription_name: Название подписки для различия (генерируется автоматически)
    is_primary: Флаг главной подписки (отображается в профиле как основная)
    can_be_deleted: Можно ли удалить подписку (админ может заблокировать удаление)
    """
    __tablename__ = "subscriptions"

    subscription_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger,
                     ForeignKey("users.user_id"),
                     nullable=False,
                     index=True)
    tariff_id = Column(Integer, ForeignKey("tariffs.id"), nullable=True)
    panel_user_uuid = Column(String, nullable=False, index=True)
    panel_subscription_uuid = Column(String,
                                     unique=True,
                                     index=True,
                                     nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_months = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    status_from_panel = Column(String, nullable=True)
    traffic_limit_bytes = Column(BigInteger, nullable=True)
    traffic_used_bytes = Column(BigInteger, nullable=True)
    last_notification_sent = Column(DateTime(timezone=True), nullable=True)
    provider = Column(String, nullable=True)
    skip_notifications = Column(Boolean, default=False)
    auto_renew_enabled = Column(Boolean, default=True, index=True)
    
    # Персональные настройки подписки
    custom_traffic_limit_bytes = Column(BigInteger, nullable=True)
    custom_device_limit = Column(Integer, nullable=True)
    subscription_name = Column(String(100), nullable=True)
    
    # Управление множественными подписками
    is_primary = Column(Boolean, nullable=False, default=False)
    can_be_deleted = Column(Boolean, nullable=False, default=True)

    user = relationship("User", back_populates="subscriptions")
    tariff = relationship("Tariff", back_populates="subscriptions")
    
    def get_effective_traffic_limit(self) -> Optional[int]:
        """Получить эффективный лимит трафика (custom или из тарифа)"""
        if self.custom_traffic_limit_bytes is not None:
            return self.custom_traffic_limit_bytes
        return self.traffic_limit_bytes
    
    def get_effective_device_limit(self) -> Optional[int]:
        """Получить эффективный лимит устройств (custom или из тарифа)"""
        if self.custom_device_limit is not None:
            return self.custom_device_limit
        if self.tariff and hasattr(self.tariff, 'device_limit'):
            return self.tariff.device_limit
        return None

    def __repr__(self):
        return f"<Subscription(id={self.subscription_id}, user_id={self.user_id}, panel_uuid='{self.panel_user_uuid}', ends='{self.end_date}')>"


class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger,
                     ForeignKey("users.user_id"),
                     nullable=False,
                     index=True)
    yookassa_payment_id = Column(String,
                                 unique=True,
                                 index=True,
                                 nullable=True)
    provider_payment_id = Column(String, unique=True, nullable=True)
    provider = Column(String, nullable=False, default="yookassa", index=True)
    idempotence_key = Column(String, unique=True, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    status = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    subscription_duration_months = Column(Integer, nullable=True)
    tariff_id = Column(Integer, ForeignKey("tariffs.id"), nullable=True)
    promo_code_id = Column(Integer,
                           ForeignKey("promo_codes.promo_code_id"),
                           nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                        onupdate=func.now(),
                        nullable=True)

    user = relationship("User", back_populates="payments")
    tariff = relationship("Tariff")
    promo_code_used = relationship("PromoCode",
                                   back_populates="payments_where_used")


class UserBilling(Base):
    __tablename__ = "user_billing"

    user_id = Column(BigInteger, ForeignKey("users.user_id"), primary_key=True)
    # Saved payment method for off-session recurring charges (YooKassa)
    yookassa_payment_method_id = Column(String, nullable=True, unique=True)
    card_last4 = Column(String, nullable=True)
    card_network = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    user = relationship("User")

class UserPaymentMethod(Base):
    __tablename__ = "user_payment_methods"

    method_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    provider = Column(String, nullable=False, default="yookassa", index=True)
    provider_payment_method_id = Column(String, nullable=False, unique=True, index=True)
    card_last4 = Column(String, nullable=True)
    card_network = Column(String, nullable=True)
    is_default = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    user = relationship("User")
    __table_args__ = (
        UniqueConstraint('user_id', 'provider_payment_method_id', name='uq_user_provider_method'),
    )

class PromoCode(Base):
    __tablename__ = "promo_codes"

    promo_code_id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, unique=True, nullable=False, index=True)
    type = Column(String, default='bonus_days')  # 'bonus_days', 'discount', 'balance'
    value = Column(Float, nullable=True)  # Amount of discount or balance
    min_purchase_amount = Column(Float, nullable=True)
    applicable_tariff_ids = Column(JSON, nullable=True)
    bonus_days = Column(Integer, nullable=False, default=0)
    max_activations = Column(Integer, nullable=False)
    current_activations = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_by_admin_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    valid_until = Column(DateTime(timezone=True), nullable=True)

    activations = relationship("PromoCodeActivation",
                               back_populates="promo_code",
                               cascade="all, delete-orphan")
    payments_where_used = relationship("Payment",
                                       back_populates="promo_code_used")


class PromoCodeActivation(Base):
    __tablename__ = "promo_code_activations"

    activation_id = Column(Integer, primary_key=True, autoincrement=True)
    promo_code_id = Column(Integer,
                           ForeignKey("promo_codes.promo_code_id"),
                           nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    activated_at = Column(DateTime(timezone=True), server_default=func.now())
    payment_id = Column(Integer,
                        ForeignKey("payments.payment_id"),
                        nullable=True)

    promo_code = relationship("PromoCode", back_populates="activations")
    user = relationship("User", back_populates="promo_code_activations")
    payment = relationship("Payment")

    __table_args__ = (UniqueConstraint('promo_code_id',
                                       'user_id',
                                       name='uq_promo_user_activation'), )


class MessageLog(Base):
    __tablename__ = "message_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger,
                     ForeignKey("users.user_id"),
                     nullable=True,
                     index=True)
    telegram_username = Column(String, nullable=True)
    telegram_first_name = Column(String, nullable=True)
    event_type = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=True)
    raw_update_preview = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True),
                       server_default=func.now(),
                       index=True)
    is_admin_event = Column(Boolean, default=False)
    target_user_id = Column(BigInteger,
                            ForeignKey("users.user_id"),
                            nullable=True,
                            index=True)

    author_user = relationship("User",
                               foreign_keys=[user_id],
                               back_populates="message_logs_authored")
    target_user = relationship("User",
                               foreign_keys=[target_user_id],
                               back_populates="message_logs_targeted")


class PanelSyncStatus(Base):
    __tablename__ = "panel_sync_status"

    id = Column(Integer, primary_key=True, default=1, autoincrement=False)
    last_sync_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=True)
    details = Column(Text, nullable=True)
    users_processed_from_panel = Column(Integer, default=0)
    subscriptions_synced = Column(Integer, default=0)

    __table_args__ = (UniqueConstraint('id'), )


class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    ad_campaign_id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False, index=True)
    start_param = Column(String, nullable=False, unique=True, index=True)
    cost = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    attributions = relationship(
        "AdAttribution",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<AdCampaign(id={self.ad_campaign_id}, source='{self.source}', start_param='{self.start_param}', cost={self.cost})>"


class AdAttribution(Base):
    __tablename__ = "ad_attributions"

    user_id = Column(BigInteger, ForeignKey("users.user_id"), primary_key=True, index=True)
    ad_campaign_id = Column(Integer, ForeignKey("ad_campaigns.ad_campaign_id"), nullable=False, index=True)
    first_start_at = Column(DateTime(timezone=True), server_default=func.now())
    trial_activated_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    campaign = relationship("AdCampaign", back_populates="attributions")


class UserBalance(Base):
    __tablename__ = "user_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="RUB")
    operation_type = Column(String, nullable=False)  # 'deposit', 'withdrawal', 'payment', 'refund', 'bonus'
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="balance_operations")


class UserDiscount(Base):
    __tablename__ = "user_discounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    discount_percentage = Column(Float, nullable=False)
    tariff_id = Column(Integer, ForeignKey("tariffs.id"), nullable=True)  # If null, applies to all tariffs
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="discounts")
    tariff = relationship("Tariff", back_populates="discounts")


class GiftedSubscription(Base):
    """
    Модель для управления подарочными подписками.
    
    Поддерживает два типа дарения:
    - direct: прямое дарение конкретному пользователю
    - random: размещение подарка в маркетплейсе для случайного получателя
    
    Жизненный цикл:
    1. pending_payment -> ready (после успешной оплаты)
    2. ready -> activated (после активации получателем)
    3. ready -> expired (если не активирован в срок)
    4. ready -> cancelled/refunded (отмена дарителем)
    """
    __tablename__ = "gifted_subscriptions"

    # Идентификация подарка
    gift_id = Column(Integer, primary_key=True, autoincrement=True)
    gift_code = Column(String(32), unique=True, nullable=False, index=True)
    
    # Даритель
    donor_user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    donor_username = Column(String, nullable=True)
    donor_lock_key = Column(String(64), nullable=True, index=True)
    
    # Получатель
    recipient_type = Column(Enum(GiftRecipientType), nullable=False, index=True)
    recipient_user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=True, index=True)
    recipient_username = Column(String, nullable=True)
    
    # Конфигурация подарка
    tariff_id = Column(Integer, ForeignKey("tariffs.id"), nullable=False)
    duration_days = Column(Integer, nullable=False)
    
    # Платежная информация
    payment_id = Column(Integer, ForeignKey("payments.payment_id"), nullable=True, unique=True, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="RUB")
    
    # Статусы и временные метки
    status = Column(Enum(GiftStatus), nullable=False, default=GiftStatus.pending_payment, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    
    # Метаданные и защита
    idempotency_key = Column(String(64), unique=True, nullable=False, index=True)
    message_to_recipient = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    donor = relationship("User", foreign_keys=[donor_user_id], backref="gifts_sent")
    recipient = relationship("User", foreign_keys=[recipient_user_id], backref="gifts_received")
    tariff = relationship("Tariff")
    payment = relationship("Payment")
    
    # Composite indexes для оптимизации частых запросов
    __table_args__ = (
        Index('ix_gifted_subs_status_expires', 'status', 'expires_at'),
        Index('ix_gifted_subs_donor_status', 'donor_user_id', 'status'),
        Index('ix_gifted_subs_recipient_status', 'recipient_user_id', 'status'),
    )
    
    def __repr__(self):
        return f"<GiftedSubscription(gift_id={self.gift_id}, code='{self.gift_code}', donor={self.donor_user_id}, status='{self.status}')>"
