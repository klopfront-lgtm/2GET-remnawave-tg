import logging
import secrets
import string
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import update, func, and_, or_, desc

from db.models import (
    GiftedSubscription,
    GiftStatus,
    GiftRecipientType,
    User,
    Tariff,
    Payment
)

# Константы для генерации подарочных кодов
GIFT_CODE_LENGTH = 16
GIFT_CODE_ALPHABET = string.ascii_uppercase + string.digits
MAX_GIFT_CODE_ATTEMPTS = 50
GIFT_EXPIRATION_DAYS = 90  # 3 месяца

logger = logging.getLogger(__name__)


# ============================================================================
# ГЕНЕРАЦИЯ УНИКАЛЬНЫХ КОДОВ
# ============================================================================

def _generate_gift_code_candidate() -> str:
    """Генерирует кандидата кода подарка (16 символов, alphanumeric uppercase)."""
    return "".join(
        secrets.choice(GIFT_CODE_ALPHABET) for _ in range(GIFT_CODE_LENGTH)
    )


async def _gift_code_exists(session: AsyncSession, code: str) -> bool:
    """Проверяет существование подарочного кода в БД."""
    stmt = select(GiftedSubscription.gift_id).where(GiftedSubscription.gift_code == code)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def generate_unique_gift_code(session: AsyncSession) -> str:
    """
    Генерирует уникальный подарочный код.
    
    Возвращает 16-символьный код из uppercase букв и цифр.
    Проверяет уникальность в БД и делает несколько попыток.
    
    Raises:
        RuntimeError: Если не удалось сгенерировать уникальный код 
                     после MAX_GIFT_CODE_ATTEMPTS попыток.
    """
    for attempt in range(MAX_GIFT_CODE_ATTEMPTS):
        candidate = _generate_gift_code_candidate()
        if not await _gift_code_exists(session, candidate):
            logger.debug(f"Generated unique gift code on attempt {attempt + 1}")
            return candidate
    
    logger.error(f"Failed to generate unique gift code after {MAX_GIFT_CODE_ATTEMPTS} attempts")
    raise RuntimeError(
        f"Failed to generate a unique gift code after {MAX_GIFT_CODE_ATTEMPTS} attempts"
    )


# ============================================================================
# CRUD ОПЕРАЦИИ - CREATE
# ============================================================================

async def create_gift_record(
    session: AsyncSession,
    gift_data: Dict[str, Any]
) -> GiftedSubscription:
    """
    Создает новую запись подарочной подписки.
    
    Args:
        session: Сессия БД
        gift_data: Словарь с данными подарка, должен содержать:
            - donor_user_id: ID дарителя
            - recipient_type: Тип получателя (GiftRecipientType)
            - tariff_id: ID тарифа
            - duration_days: Длительность в днях
            - amount: Стоимость
            - currency: Валюта (по умолчанию RUB)
            - idempotency_key: Ключ идемпотентности
            - recipient_user_id: ID получателя (опционально для direct)
            - message_to_recipient: Сообщение получателю (опционально)
            - metadata: Дополнительные данные (опционально)
    
    Returns:
        GiftedSubscription: Созданная запись подарка
        
    Raises:
        ValueError: Если не найден пользователь или тариф
    """
    # Валидация дарителя
    from .user_dal import get_user_by_id
    donor = await get_user_by_id(session, gift_data["donor_user_id"])
    if not donor:
        raise ValueError(f"Donor user {gift_data['donor_user_id']} not found")
    
    # Валидация тарифа
    from .tariff_dal import get_tariff_by_id
    tariff = await get_tariff_by_id(session, gift_data["tariff_id"])
    if not tariff:
        raise ValueError(f"Tariff {gift_data['tariff_id']} not found")
    
    # Валидация получателя для direct типа
    if gift_data["recipient_type"] == GiftRecipientType.direct:
        if not gift_data.get("recipient_user_id"):
            raise ValueError("recipient_user_id is required for direct gift type")
        recipient = await get_user_by_id(session, gift_data["recipient_user_id"])
        if not recipient:
            raise ValueError(f"Recipient user {gift_data['recipient_user_id']} not found")
    
    # Генерация уникального кода подарка
    if "gift_code" not in gift_data:
        gift_data["gift_code"] = await generate_unique_gift_code(session)
    
    # Установка дефолтных значений
    if "currency" not in gift_data:
        gift_data["currency"] = "RUB"
    if "status" not in gift_data:
        gift_data["status"] = GiftStatus.pending_payment
    
    # Добавление donor_username если есть
    if donor.username:
        gift_data["donor_username"] = donor.username
    
    new_gift = GiftedSubscription(**gift_data)
    session.add(new_gift)
    await session.flush()
    await session.refresh(new_gift)
    
    logger.info(
        f"Gift record {new_gift.gift_id} created by user {new_gift.donor_user_id}, "
        f"code: {new_gift.gift_code}, type: {new_gift.recipient_type.value}"
    )
    
    return new_gift


# ============================================================================
# CRUD ОПЕРАЦИИ - READ
# ============================================================================

async def get_gift_by_id(
    session: AsyncSession,
    gift_id: int,
    load_relationships: bool = True
) -> Optional[GiftedSubscription]:
    """
    Получает подарок по ID.
    
    Args:
        session: Сессия БД
        gift_id: ID подарка
        load_relationships: Загружать ли связанные объекты
    
    Returns:
        GiftedSubscription или None
    """
    stmt = select(GiftedSubscription).where(GiftedSubscription.gift_id == gift_id)
    
    if load_relationships:
        stmt = stmt.options(
            selectinload(GiftedSubscription.donor),
            selectinload(GiftedSubscription.recipient),
            selectinload(GiftedSubscription.tariff),
            selectinload(GiftedSubscription.payment)
        )
    
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_gift_by_code(
    session: AsyncSession,
    gift_code: str,
    for_update: bool = False,
    load_relationships: bool = True
) -> Optional[GiftedSubscription]:
    """
    Получает подарок по коду.
    
    Args:
        session: Сессия БД
        gift_code: Код подарка
        for_update: Использовать SELECT FOR UPDATE для блокировки
        load_relationships: Загружать ли связанные объекты
    
    Returns:
        GiftedSubscription или None
    """
    stmt = select(GiftedSubscription).where(GiftedSubscription.gift_code == gift_code)
    
    if for_update:
        stmt = stmt.with_for_update()
    
    if load_relationships:
        stmt = stmt.options(
            selectinload(GiftedSubscription.donor),
            selectinload(GiftedSubscription.recipient),
            selectinload(GiftedSubscription.tariff),
            selectinload(GiftedSubscription.payment)
        )
    
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_gift_by_payment_id(
    session: AsyncSession,
    payment_id: int,
    load_relationships: bool = True
) -> Optional[GiftedSubscription]:
    """
    Получает подарок по ID платежа.
    
    Args:
        session: Сессия БД
        payment_id: ID платежа
        load_relationships: Загружать ли связанные объекты
    
    Returns:
        GiftedSubscription или None
    """
    stmt = select(GiftedSubscription).where(GiftedSubscription.payment_id == payment_id)
    
    if load_relationships:
        stmt = stmt.options(
            selectinload(GiftedSubscription.donor),
            selectinload(GiftedSubscription.recipient),
            selectinload(GiftedSubscription.tariff),
            selectinload(GiftedSubscription.payment)
        )
    
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_gifts_by_donor(
    session: AsyncSession,
    donor_user_id: int,
    status: Optional[GiftStatus] = None,
    limit: int = 50,
    offset: int = 0
) -> List[GiftedSubscription]:
    """
    Получает список подарков, отправленных пользователем.
    
    Args:
        session: Сессия БД
        donor_user_id: ID дарителя
        status: Фильтр по статусу (опционально)
        limit: Максимальное количество записей
        offset: Смещение для пагинации
    
    Returns:
        Список подарков
    """
    stmt = (
        select(GiftedSubscription)
        .where(GiftedSubscription.donor_user_id == donor_user_id)
        .options(
            selectinload(GiftedSubscription.recipient),
            selectinload(GiftedSubscription.tariff),
            selectinload(GiftedSubscription.payment)
        )
        .order_by(desc(GiftedSubscription.created_at))
        .limit(limit)
        .offset(offset)
    )
    
    if status is not None:
        stmt = stmt.where(GiftedSubscription.status == status)
    
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_gifts_by_recipient(
    session: AsyncSession,
    recipient_user_id: int,
    status: Optional[GiftStatus] = None,
    limit: int = 50,
    offset: int = 0
) -> List[GiftedSubscription]:
    """
    Получает список подарков, полученных пользователем.
    
    Args:
        session: Сессия БД
        recipient_user_id: ID получателя
        status: Фильтр по статусу (опционально)
        limit: Максимальное количество записей
        offset: Смещение для пагинации
    
    Returns:
        Список подарков
    """
    stmt = (
        select(GiftedSubscription)
        .where(GiftedSubscription.recipient_user_id == recipient_user_id)
        .options(
            selectinload(GiftedSubscription.donor),
            selectinload(GiftedSubscription.tariff),
            selectinload(GiftedSubscription.payment)
        )
        .order_by(desc(GiftedSubscription.created_at))
        .limit(limit)
        .offset(offset)
    )
    
    if status is not None:
        stmt = stmt.where(GiftedSubscription.status == status)
    
    result = await session.execute(stmt)
    return result.scalars().all()


# ============================================================================
# CRUD ОПЕРАЦИИ - UPDATE
# ============================================================================

async def update_gift_status(
    session: AsyncSession,
    gift_id: int,
    new_status: GiftStatus,
    **additional_fields
) -> Optional[GiftedSubscription]:
    """
    Обновляет статус подарка и дополнительные поля.
    
    Args:
        session: Сессия БД
        gift_id: ID подарка
        new_status: Новый статус
        **additional_fields: Дополнительные поля для обновления
    
    Returns:
        Обновленный подарок или None
    """
    gift = await get_gift_by_id(session, gift_id, load_relationships=False)
    if not gift:
        logger.warning(f"Gift {gift_id} not found for status update")
        return None
    
    gift.status = new_status
    
    # Обновляем дополнительные поля
    for field, value in additional_fields.items():
        if hasattr(gift, field):
            setattr(gift, field, value)
    
    await session.flush()
    await session.refresh(gift)
    
    logger.info(f"Gift {gift_id} status updated to {new_status.value}")
    
    return gift


async def mark_gift_as_paid(
    session: AsyncSession,
    gift_id: int,
    payment_id: int
) -> Optional[GiftedSubscription]:
    """
    Помечает подарок как оплаченный.
    
    Устанавливает статус 'ready', связывает с платежом,
    устанавливает paid_at и expires_at.
    
    Args:
        session: Сессия БД
        gift_id: ID подарка
        payment_id: ID платежа
    
    Returns:
        Обновленный подарок или None
    """
    gift = await get_gift_by_id(session, gift_id, load_relationships=False)
    if not gift:
        logger.warning(f"Gift {gift_id} not found for payment marking")
        return None
    
    # Проверяем, что подарок в правильном статусе
    if gift.status != GiftStatus.pending_payment:
        logger.warning(
            f"Gift {gift_id} is in status {gift.status.value}, "
            "cannot mark as paid (expected pending_payment)"
        )
        return gift
    
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=GIFT_EXPIRATION_DAYS)
    
    gift.status = GiftStatus.ready
    gift.payment_id = payment_id
    gift.paid_at = now
    gift.expires_at = expires_at
    
    await session.flush()
    await session.refresh(gift)
    
    logger.info(
        f"Gift {gift_id} marked as paid with payment {payment_id}, "
        f"expires at {expires_at.isoformat()}"
    )
    
    return gift


async def activate_gift(
    session: AsyncSession,
    gift_id: int,
    recipient_user_id: int
) -> Tuple[Optional[GiftedSubscription], Optional[str]]:
    """
    Активирует подарок для получателя.
    
    Проверяет все условия активации и обновляет статус.
    Эта функция НЕ создает подписку - это должен делать service layer.
    
    Args:
        session: Сессия БД
        gift_id: ID подарка
        recipient_user_id: ID получателя
    
    Returns:
        Tuple (подарок, ошибка).
        Если ошибка None - активация успешна.
        Если ошибка присутствует - активация не выполнена.
    """
    gift = await get_gift_by_id(session, gift_id, load_relationships=False)
    if not gift:
        return None, "Gift not found"
    
    # Проверка статуса
    if gift.status != GiftStatus.ready:
        return gift, f"Gift is not ready for activation (status: {gift.status.value})"
    
    # Проверка срока действия
    now = datetime.now(timezone.utc)
    if gift.expires_at and gift.expires_at < now:
        # Автоматически помечаем как истекший
        gift.status = GiftStatus.expired
        await session.flush()
        return gift, "Gift has expired"
    
    # Проверка типа получателя
    if gift.recipient_type == GiftRecipientType.direct:
        # Для direct подарка проверяем, что активирует правильный пользователь
        if gift.recipient_user_id != recipient_user_id:
            return gift, "This gift is intended for another user"
    elif gift.recipient_type == GiftRecipientType.random:
        # Для random подарка проверяем, что получатель не является дарителем
        if gift.donor_user_id == recipient_user_id:
            return gift, "Cannot activate your own gift"
        # Устанавливаем получателя
        gift.recipient_user_id = recipient_user_id
        
        # Получаем username получателя если есть
        from .user_dal import get_user_by_id
        recipient = await get_user_by_id(session, recipient_user_id)
        if recipient and recipient.username:
            gift.recipient_username = recipient.username
    
    # Активируем подарок
    gift.status = GiftStatus.activated
    gift.activated_at = now
    
    await session.flush()
    await session.refresh(gift)
    
    logger.info(
        f"Gift {gift_id} activated by user {recipient_user_id}, "
        f"donor: {gift.donor_user_id}"
    )
    
    return gift, None


async def cancel_gift(
    session: AsyncSession,
    gift_id: int,
    donor_user_id: int
) -> Tuple[Optional[GiftedSubscription], Optional[str]]:
    """
    Отменяет подарок дарителем.
    
    Подарок можно отменить только в статусах: pending_payment, ready.
    
    Args:
        session: Сессия БД
        gift_id: ID подарка
        donor_user_id: ID дарителя (для проверки прав)
    
    Returns:
        Tuple (подарок, ошибка).
        Если ошибка None - отмена успешна.
    """
    gift = await get_gift_by_id(session, gift_id, load_relationships=False)
    if not gift:
        return None, "Gift not found"
    
    # Проверка прав
    if gift.donor_user_id != donor_user_id:
        return gift, "You are not the donor of this gift"
    
    # Проверка статуса
    cancellable_statuses = [GiftStatus.pending_payment, GiftStatus.ready]
    if gift.status not in cancellable_statuses:
        return gift, f"Cannot cancel gift in status {gift.status.value}"
    
    # Отменяем подарок
    gift.status = GiftStatus.cancelled
    gift.cancelled_at = datetime.now(timezone.utc)
    
    await session.flush()
    await session.refresh(gift)
    
    logger.info(f"Gift {gift_id} cancelled by donor {donor_user_id}")
    
    return gift, None


# ============================================================================
# ВАЛИДАЦИЯ И БЕЗОПАСНОСТЬ
# ============================================================================

async def validate_gift_code_for_activation(
    session: AsyncSession,
    gift_code: str,
    recipient_user_id: int
) -> Tuple[Optional[GiftedSubscription], Optional[str]]:
    """
    Полная валидация подарочного кода для активации.
    
    Использует SELECT FOR UPDATE для предотвращения гонок.
    Проверяет все условия активации.
    
    Args:
        session: Сессия БД
        gift_code: Код подарка
        recipient_user_id: ID пользователя, который хочет активировать
    
    Returns:
        Tuple (подарок, ошибка).
        Если ошибка None - код валиден и можно активировать.
        Если ошибка присутствует - активация невозможна.
    """
    # Получаем подарок с блокировкой
    gift = await get_gift_by_code(
        session,
        gift_code,
        for_update=True,
        load_relationships=False
    )
    
    if not gift:
        return None, "Invalid gift code"
    
    # Проверка статуса
    if gift.status != GiftStatus.ready:
        if gift.status == GiftStatus.activated:
            return gift, "This gift has already been activated"
        elif gift.status == GiftStatus.expired:
            return gift, "This gift has expired"
        elif gift.status == GiftStatus.cancelled:
            return gift, "This gift has been cancelled"
        else:
            return gift, f"Gift is not available (status: {gift.status.value})"
    
    # Проверка срока действия
    now = datetime.now(timezone.utc)
    if gift.expires_at and gift.expires_at < now:
        # Автоматически обновить статус на истекший
        await update_gift_status(session, gift.gift_id, GiftStatus.expired)
        await session.flush()
        return gift, "This gift has expired"
    
    # Проверка типа получателя
    if gift.recipient_type == GiftRecipientType.direct:
        if gift.recipient_user_id != recipient_user_id:
            return gift, "This gift is intended for another user"
    elif gift.recipient_type == GiftRecipientType.random:
        if gift.donor_user_id == recipient_user_id:
            return gift, "You cannot activate your own gift"
    
    return gift, None


async def check_user_gift_rate_limit(
    session: AsyncSession,
    user_id: int,
    hours: int = 24,
    max_gifts: int = 10
) -> Tuple[bool, int]:
    """
    Проверяет rate limit на создание подарков пользователем.
    
    Args:
        session: Сессия БД
        user_id: ID пользователя
        hours: Период проверки в часах
        max_gifts: Максимальное количество подарков за период
    
    Returns:
        Tuple (можно_создавать, количество_созданных_за_период)
    """
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    stmt = (
        select(func.count(GiftedSubscription.gift_id))
        .where(
            and_(
                GiftedSubscription.donor_user_id == user_id,
                GiftedSubscription.created_at >= time_threshold
            )
        )
    )
    
    result = await session.execute(stmt)
    count = result.scalar() or 0
    
    can_create = count < max_gifts
    
    if not can_create:
        logger.warning(
            f"User {user_id} exceeded gift rate limit: "
            f"{count}/{max_gifts} in last {hours} hours"
        )
    
    return can_create, count


async def check_user_daily_gift_spending(
    session: AsyncSession,
    user_id: int,
    max_amount: float = 10000.0
) -> Tuple[bool, float]:
    """
    Проверяет лимит расходов пользователя на подарки за день.
    
    Args:
        session: Сессия БД
        user_id: ID пользователя
        max_amount: Максимальная сумма за день
    
    Returns:
        Tuple (можно_тратить, сумма_потраченная_сегодня)
    """
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    
    stmt = (
        select(func.sum(GiftedSubscription.amount))
        .where(
            and_(
                GiftedSubscription.donor_user_id == user_id,
                GiftedSubscription.created_at >= today_start,
                GiftedSubscription.status.in_([
                    GiftStatus.pending_payment,
                    GiftStatus.ready,
                    GiftStatus.activated
                ])
            )
        )
    )
    
    result = await session.execute(stmt)
    total_spent = result.scalar() or 0.0
    
    can_spend = total_spent < max_amount
    
    if not can_spend:
        logger.warning(
            f"User {user_id} exceeded daily gift spending limit: "
            f"{total_spent:.2f}/{max_amount:.2f}"
        )
    
    return can_spend, total_spent


# ============================================================================
# СТАТИСТИКА И АНАЛИТИКА
# ============================================================================

async def get_gift_statistics(session: AsyncSession) -> Dict[str, Any]:
    """
    Получает общую статистику по подаркам.
    
    Returns:
        Словарь со статистикой
    """
    # Общее количество подарков
    total_stmt = select(func.count(GiftedSubscription.gift_id))
    total_count = (await session.execute(total_stmt)).scalar() or 0
    
    # Количество по статусам
    status_stats = {}
    for status in GiftStatus:
        status_stmt = select(func.count(GiftedSubscription.gift_id)).where(
            GiftedSubscription.status == status
        )
        status_stats[status.value] = (await session.execute(status_stmt)).scalar() or 0
    
    # Сумма активированных подарков
    activated_sum_stmt = select(func.sum(GiftedSubscription.amount)).where(
        GiftedSubscription.status == GiftStatus.activated
    )
    activated_sum = (await session.execute(activated_sum_stmt)).scalar() or 0.0
    
    # Количество уникальных дарителей
    donors_stmt = select(func.count(func.distinct(GiftedSubscription.donor_user_id)))
    unique_donors = (await session.execute(donors_stmt)).scalar() or 0
    
    # Количество уникальных получателей
    recipients_stmt = select(
        func.count(func.distinct(GiftedSubscription.recipient_user_id))
    ).where(GiftedSubscription.recipient_user_id.is_not(None))
    unique_recipients = (await session.execute(recipients_stmt)).scalar() or 0
    
    # Статистика за последние 24 часа
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
    created_24h_stmt = select(func.count(GiftedSubscription.gift_id)).where(
        GiftedSubscription.created_at >= time_threshold
    )
    created_24h = (await session.execute(created_24h_stmt)).scalar() or 0
    
    activated_24h_stmt = select(func.count(GiftedSubscription.gift_id)).where(
        and_(
            GiftedSubscription.status == GiftStatus.activated,
            GiftedSubscription.activated_at >= time_threshold
        )
    )
    activated_24h = (await session.execute(activated_24h_stmt)).scalar() or 0
    
    return {
        "total_gifts": total_count,
        "status_breakdown": status_stats,
        "activated_total_amount": float(activated_sum),
        "unique_donors": unique_donors,
        "unique_recipients": unique_recipients,
        "created_last_24h": created_24h,
        "activated_last_24h": activated_24h
    }


async def get_gifts_for_admin(
    session: AsyncSession,
    status: Optional[GiftStatus] = None,
    recipient_type: Optional[GiftRecipientType] = None,
    limit: int = 50,
    offset: int = 0
) -> List[GiftedSubscription]:
    """
    Получает список подарков для админ-панели.
    
    Args:
        session: Сессия БД
        status: Фильтр по статусу
        recipient_type: Фильтр по типу получателя
        limit: Максимальное количество записей
        offset: Смещение для пагинации
    
    Returns:
        Список подарков с загруженными связями
    """
    stmt = (
        select(GiftedSubscription)
        .options(
            selectinload(GiftedSubscription.donor),
            selectinload(GiftedSubscription.recipient),
            selectinload(GiftedSubscription.tariff),
            selectinload(GiftedSubscription.payment)
        )
        .order_by(desc(GiftedSubscription.created_at))
        .limit(limit)
        .offset(offset)
    )
    
    conditions = []
    if status is not None:
        conditions.append(GiftedSubscription.status == status)
    if recipient_type is not None:
        conditions.append(GiftedSubscription.recipient_type == recipient_type)
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    result = await session.execute(stmt)
    return result.scalars().all()


async def count_gifts_for_admin(
    session: AsyncSession,
    status: Optional[GiftStatus] = None,
    recipient_type: Optional[GiftRecipientType] = None
) -> int:
    """
    Подсчитывает количество подарков для админ-панели (для пагинации).
    
    Args:
        session: Сессия БД
        status: Фильтр по статусу
        recipient_type: Фильтр по типу получателя
    
    Returns:
        Количество подарков
    """
    stmt = select(func.count(GiftedSubscription.gift_id))
    
    conditions = []
    if status is not None:
        conditions.append(GiftedSubscription.status == status)
    if recipient_type is not None:
        conditions.append(GiftedSubscription.recipient_type == recipient_type)
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    result = await session.execute(stmt)
    return result.scalar() or 0


# ============================================================================
# УТИЛИТЫ
# ============================================================================

async def get_random_active_user(
    session: AsyncSession,
    exclude_user_ids: Optional[List[int]] = None
) -> Optional[User]:
    """
    Выбирает случайного активного пользователя для random gift.
    
    Активный пользователь определяется как:
    - Не забанен
    - Не в списке исключений
    
    Args:
        session: Сессия БД
        exclude_user_ids: Список ID пользователей для исключения
    
    Returns:
        Случайный пользователь или None
    """
    stmt = select(User).where(User.is_banned == False)
    
    if exclude_user_ids:
        stmt = stmt.where(~User.user_id.in_(exclude_user_ids))
    
    # PostgreSQL специфичная функция random()
    stmt = stmt.order_by(func.random()).limit(1)
    
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def expire_old_gifts(session: AsyncSession) -> int:
    """
    Помечает истекшие подарки как expired.
    
    Обновляет все подарки в статусе 'ready' со сроком действия в прошлом.
    
    Args:
        session: Сессия БД
    
    Returns:
        Количество помеченных подарков
    """
    now = datetime.now(timezone.utc)
    
    stmt = (
        update(GiftedSubscription)
        .where(
            and_(
                GiftedSubscription.status == GiftStatus.ready,
                GiftedSubscription.expires_at < now
            )
        )
        .values(status=GiftStatus.expired)
    )
    
    result = await session.execute(stmt)
    count = result.rowcount
    
    if count > 0:
        logger.info(f"Marked {count} gifts as expired")
    
    return count