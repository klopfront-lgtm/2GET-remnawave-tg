import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete, func, and_, or_
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone, timedelta

from db.models import Subscription, User


async def get_active_subscription_by_user_id(
        session: AsyncSession,
        user_id: int,
        panel_user_uuid: Optional[str] = None) -> Optional[Subscription]:
    # PERFORMANCE: Added selectinload to prevent N+1 queries when accessing tariff
    # TODO: Consider adding composite index on (user_id, is_active, end_date) for faster lookups
    stmt = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.is_active == True,
        Subscription.end_date > datetime.now(timezone.utc),
    ).options(selectinload(Subscription.tariff))
    if panel_user_uuid:
        stmt = stmt.where(Subscription.panel_user_uuid == panel_user_uuid)
    stmt = stmt.order_by(Subscription.end_date.desc()).limit(1)
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_subscription_by_panel_subscription_uuid(
        session: AsyncSession, panel_sub_uuid: str) -> Optional[Subscription]:
    stmt = select(Subscription).where(
        Subscription.panel_subscription_uuid == panel_sub_uuid)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_subscriptions_for_user(session: AsyncSession, user_id: int) -> List[Subscription]:
    """Get all active subscriptions for a user."""
    # PERFORMANCE: Added selectinload to prevent N+1 queries when accessing tariff
    stmt = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.is_active == True
    ).options(selectinload(Subscription.tariff)).order_by(Subscription.end_date.desc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_subscription(
        session: AsyncSession, subscription_id: int,
        update_data: Dict[str, Any]) -> Optional[Subscription]:
    # PERFORMANCE: Using session.get for efficient primary key lookup
    # TODO: For critical updates, consider using with_for_update() to prevent race conditions
    sub = await session.get(Subscription, subscription_id)
    if sub:
        for key, value in update_data.items():
            setattr(sub, key, value)
        await session.flush()
        await session.refresh(sub)
    return sub


async def set_auto_renew(session: AsyncSession, subscription_id: int, enabled: bool) -> Optional[Subscription]:
    """Toggle auto_renew_enabled for a subscription."""
    return await update_subscription(session, subscription_id, {"auto_renew_enabled": enabled})


async def set_user_subscriptions_cancelled_with_grace(
        session: AsyncSession, user_id: int, grace_days: int = 1) -> int:
    """Mark all active user subscriptions as cancelled with a short grace period.

    Sets end_date to now + grace_days, status_from_panel to 'CANCELLED', and
    skip future notifications to reduce noise after cancellation.
    Returns number of updated rows.
    """
    from datetime import datetime, timezone, timedelta
    grace_end = datetime.now(timezone.utc) + timedelta(days=grace_days)
    stmt = (
        update(Subscription)
        .where(Subscription.user_id == user_id, Subscription.is_active == True)
        .values(
            end_date=grace_end,
            status_from_panel="CANCELLED",
            skip_notifications=True,
        )
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def upsert_subscription(session: AsyncSession,
                              sub_payload: Dict[str, Any]) -> Subscription:
    panel_sub_uuid = sub_payload.get("panel_subscription_uuid")
    if not panel_sub_uuid:
        raise ValueError("panel_subscription_uuid is required for upsert.")

    existing_sub = await get_subscription_by_panel_subscription_uuid(
        session, panel_sub_uuid)

    if existing_sub:
        logging.info(
            f"Updating existing subscription {existing_sub.subscription_id} by panel_sub_uuid {panel_sub_uuid}"
        )
        for key, value in sub_payload.items():
            if hasattr(existing_sub, key):
                setattr(existing_sub, key, value)
        await session.flush()
        await session.refresh(existing_sub)
        return existing_sub
    else:
        logging.info(
            f"Creating new subscription with panel_sub_uuid {panel_sub_uuid}")

        if sub_payload.get(
                "user_id") is None and "panel_user_uuid" not in sub_payload:
            raise ValueError(
                "For a new subscription without user_id, panel_user_uuid is required."
            )
        if "end_date" not in sub_payload:
            raise ValueError("Missing 'end_date' for new subscription.")
        if sub_payload.get("user_id") is not None:
            from .user_dal import get_user_by_id
            user = await get_user_by_id(session, sub_payload["user_id"])
            if not user:
                raise ValueError(
                    f"User {sub_payload['user_id']} not found for new subscription with panel_uuid {panel_sub_uuid}."
                )

        new_sub = Subscription(**sub_payload)
        session.add(new_sub)
        await session.flush()
        await session.refresh(new_sub)
        return new_sub


async def deactivate_other_active_subscriptions(
        session: AsyncSession, panel_user_uuid: str,
        current_panel_subscription_uuid: Optional[str]):
    stmt = (update(Subscription).where(
        Subscription.panel_user_uuid == panel_user_uuid,
        Subscription.is_active == True,
    ).values(is_active=False, status_from_panel="INACTIVE_BY_BOT_SYNC"))
    if current_panel_subscription_uuid:
        stmt = stmt.where(Subscription.panel_subscription_uuid !=
                          current_panel_subscription_uuid)

    result = await session.execute(stmt)
    if result.rowcount > 0:
        logging.info(
            f"Deactivated {result.rowcount} other active subscriptions for panel_user_uuid {panel_user_uuid}."
        )


async def deactivate_all_user_subscriptions(
        session: AsyncSession, user_id: int) -> int:
    stmt = (
        update(Subscription)
        .where(Subscription.user_id == user_id, Subscription.is_active == True)
        .values(is_active=False, status_from_panel="INACTIVE_USER_NOT_FOUND")
    )
    result = await session.execute(stmt)
    if result.rowcount > 0:
        logging.info(
            f"Deactivated {result.rowcount} subscriptions for user {user_id} due to missing panel user."
        )
    return result.rowcount


async def delete_all_user_subscriptions(
        session: AsyncSession, user_id: int) -> int:
    """Completely delete all user subscriptions (for trial reset)"""
    stmt = delete(Subscription).where(Subscription.user_id == user_id)
    result = await session.execute(stmt)
    if result.rowcount > 0:
        logging.info(
            f"Deleted {result.rowcount} subscription records for user {user_id} for trial reset."
        )
    return result.rowcount


async def update_subscription_end_date(
        session: AsyncSession, subscription_id: int,
        new_end_date: datetime) -> Optional[Subscription]:

    return await update_subscription(
        session, subscription_id, {
            "end_date": new_end_date,
            "last_notification_sent": None,
            "is_active": True,
            "status_from_panel": "ACTIVE_EXTENDED_BY_BOT"
        })


async def has_any_subscription_for_user(session: AsyncSession,
                                        user_id: int) -> bool:
    stmt = select(Subscription.subscription_id).where(
        Subscription.user_id == user_id).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def get_subscriptions_near_expiration(
        session: AsyncSession, days_threshold: int) -> List[Subscription]:
    # PERFORMANCE: Critical query for notification system
    # TODO: Consider adding index on (is_active, skip_notifications, end_date) for faster filtering
    # TODO: Consider adding index on last_notification_sent for date comparisons
    now_utc = datetime.now(timezone.utc)
    threshold_date = now_utc + timedelta(days=days_threshold)

    stmt = (select(Subscription).join(Subscription.user).where(
        Subscription.is_active == True,
        Subscription.skip_notifications == False,
        Subscription.end_date > now_utc,
        Subscription.end_date <= threshold_date,
        or_(
            Subscription.last_notification_sent == None,
            func.date(Subscription.last_notification_sent)
            < func.date(now_utc))).order_by(
                Subscription.end_date.asc()).options(
                    selectinload(Subscription.user)))
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_subscription_notification_time(
        session: AsyncSession, subscription_id: int,
        notification_time: datetime) -> Optional[Subscription]:
    return await update_subscription(
        session, subscription_id,
        {"last_notification_sent": notification_time})


async def find_subscription_for_notification_update(
        session: AsyncSession, user_id: int,
        subscription_end_date_to_match: datetime) -> Optional[Subscription]:

    if subscription_end_date_to_match.tzinfo is None:
        subscription_end_date_to_match = subscription_end_date_to_match.replace(
            tzinfo=timezone.utc)

    stmt = select(Subscription).where(
        Subscription.user_id == user_id, Subscription.is_active == True,
        Subscription.end_date
        >= subscription_end_date_to_match - timedelta(seconds=1),
        Subscription.end_date
        <= subscription_end_date_to_match + timedelta(seconds=1)).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()





# ============================================================================
# Methods for Multiple Subscriptions Support
# ============================================================================

async def count_active_subscriptions(
    session: AsyncSession,
    user_id: int
) -> int:
    """Подсчет активных подписок пользователя"""
    stmt = select(func.count(Subscription.subscription_id)).where(
        Subscription.user_id == user_id,
        Subscription.is_active == True
    )
    result = await session.execute(stmt)
    return result.scalar() or 0


async def check_subscription_limit(
    session: AsyncSession,
    user_id: int
) -> tuple[bool, int, int]:
    """
    Проверка возможности создания новой подписки.
    
    Returns:
        (can_create, current_count, max_limit)
    """
    # PERFORMANCE: Optimized to use single query instead of separate user fetch
    # Получить max_subscriptions_limit напрямую из User таблицы
    stmt = select(User.max_subscriptions_limit).where(User.user_id == user_id)
    result = await session.execute(stmt)
    max_limit = result.scalar_one_or_none()
    
    if max_limit is None:
        logging.warning(f"User {user_id} not found during subscription limit check")
        return False, 0, 0
    
    # Подсчитать активные подписки
    count = await count_active_subscriptions(session, user_id)
    
    can_create = count < max_limit
    logging.info(
        f"Subscription limit check for user {user_id}: "
        f"{count}/{max_limit} (can_create={can_create})"
    )
    return can_create, count, max_limit


async def get_primary_subscription(
    session: AsyncSession,
    user_id: int
) -> Optional[Subscription]:
    """Получение главной подписки пользователя"""
    stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.is_active == True,
            Subscription.is_primary == True
        )
        .options(selectinload(Subscription.tariff))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def clear_primary_flag_for_user(
    session: AsyncSession,
    user_id: int
) -> None:
    """Снятие флага is_primary со всех подписок пользователя"""
    stmt = (
        update(Subscription)
        .where(Subscription.user_id == user_id)
        .values(is_primary=False)
    )
    result = await session.execute(stmt)
    if result.rowcount > 0:
        logging.info(f"Cleared primary flag for {result.rowcount} subscriptions of user {user_id}")
    await session.flush()


async def set_primary_subscription(
    session: AsyncSession,
    subscription_id: int,
    user_id: int
) -> bool:
    """
    Установка подписки как главной.
    
    Returns:
        True если успешно, False если подписка не найдена/не принадлежит пользователю
    """
    # PERFORMANCE: Using with_for_update() to prevent race condition when setting primary
    # This ensures no concurrent updates can modify primary flag during this transaction
    from sqlalchemy import select as sql_select
    stmt = sql_select(Subscription).where(
        Subscription.subscription_id == subscription_id,
        Subscription.user_id == user_id,
        Subscription.is_active == True
    ).with_for_update()
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        logging.warning(
            f"Cannot set primary subscription: subscription {subscription_id} "
            f"not found or doesn't belong to user {user_id}"
        )
        return False
    
    # Сбросить флаг у всех подписок пользователя
    await clear_primary_flag_for_user(session, user_id)
    
    # Установить флаг для выбранной подписки
    subscription.is_primary = True
    await session.flush()
    
    logging.info(f"Set subscription {subscription_id} as primary for user {user_id}")
    return True


async def get_subscription_by_id_for_user(
    session: AsyncSession,
    subscription_id: int,
    user_id: int
) -> Optional[Subscription]:
    """Получение подписки по ID с проверкой принадлежности пользователю"""
    stmt = (
        select(Subscription)
        .where(
            Subscription.subscription_id == subscription_id,
            Subscription.user_id == user_id
        )
        .options(selectinload(Subscription.tariff))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_subscription_params(
    session: AsyncSession,
    subscription_id: int,
    custom_traffic_limit: Optional[int] = None,
    custom_device_limit: Optional[int] = None,
    subscription_name: Optional[str] = None
) -> Optional[Subscription]:
    """Обновление персональных параметров подписки"""
    stmt = select(Subscription).where(
        Subscription.subscription_id == subscription_id
    )
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        logging.warning(f"Subscription {subscription_id} not found for params update")
        return None
    
    updated_fields = []
    if custom_traffic_limit is not None:
        subscription.custom_traffic_limit_bytes = custom_traffic_limit
        updated_fields.append(f"traffic_limit={custom_traffic_limit}")
    if custom_device_limit is not None:
        subscription.custom_device_limit = custom_device_limit
        updated_fields.append(f"device_limit={custom_device_limit}")
    if subscription_name is not None:
        subscription.subscription_name = subscription_name
        updated_fields.append(f"name={subscription_name}")
    
    if updated_fields:
        logging.info(
            f"Updated subscription {subscription_id} params: {', '.join(updated_fields)}"
        )
    
    await session.flush()
    await session.refresh(subscription)
    
    return subscription
