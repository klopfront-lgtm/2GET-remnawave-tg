import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from db.models import UserDiscount


async def get_user_active_discounts(
    session: AsyncSession,
    user_id: int,
    tariff_id: Optional[int] = None
) -> List[UserDiscount]:
    """
    Получить активные скидки пользователя.
    Если tariff_id указан, возвращает скидки для конкретного тарифа или общие.
    """
    if tariff_id is not None:
        stmt = select(UserDiscount).where(
            and_(
                UserDiscount.user_id == user_id,
                UserDiscount.is_active == True,
                (UserDiscount.tariff_id == tariff_id) | (UserDiscount.tariff_id == None)
            )
        ).order_by(UserDiscount.discount_percentage.desc())
    else:
        stmt = select(UserDiscount).where(
            and_(
                UserDiscount.user_id == user_id,
                UserDiscount.is_active == True
            )
        ).order_by(UserDiscount.discount_percentage.desc())
    
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_best_user_discount(
    session: AsyncSession,
    user_id: int,
    tariff_id: Optional[int] = None
) -> Optional[UserDiscount]:
    """
    Получить лучшую (максимальную) активную скидку для пользователя и тарифа.
    """
    discounts = await get_user_active_discounts(session, user_id, tariff_id)
    if not discounts:
        return None
    
    # Находим скидку с максимальным процентом
    # Приоритет: специфичная для тарифа > общая
    specific_discount = None
    general_discount = None
    
    for discount in discounts:
        if discount.tariff_id == tariff_id:
            if not specific_discount or discount.discount_percentage > specific_discount.discount_percentage:
                specific_discount = discount
        elif discount.tariff_id is None:
            if not general_discount or discount.discount_percentage > general_discount.discount_percentage:
                general_discount = discount
    
    # Возвращаем специфичную скидку если есть, иначе общую
    return specific_discount if specific_discount else general_discount


async def create_user_discount(
    session: AsyncSession,
    user_id: int,
    discount_percentage: float,
    tariff_id: Optional[int] = None
) -> UserDiscount:
    """
    Создать новую скидку для пользователя.
    """
    discount = UserDiscount(
        user_id=user_id,
        discount_percentage=discount_percentage,
        tariff_id=tariff_id,
        is_active=True
    )
    session.add(discount)
    await session.flush()
    await session.refresh(discount)
    logging.info(
        f"Created discount {discount.id} for user {user_id}: {discount_percentage}% "
        f"for tariff_id={tariff_id or 'all'}"
    )
    return discount


async def deactivate_user_discount(
    session: AsyncSession,
    discount_id: int
) -> Optional[UserDiscount]:
    """
    Деактивировать скидку пользователя.
    """
    discount = await session.get(UserDiscount, discount_id)
    if not discount:
        return None
    
    discount.is_active = False
    await session.flush()
    await session.refresh(discount)
    logging.info(f"Deactivated discount {discount_id}")
    return discount


async def get_all_user_discounts(
    session: AsyncSession,
    user_id: int
) -> List[UserDiscount]:
    """
    Получить все скидки пользователя (активные и неактивные).
    """
    stmt = select(UserDiscount).where(
        UserDiscount.user_id == user_id
    ).order_by(UserDiscount.created_at.desc())
    
    result = await session.execute(stmt)
    return result.scalars().all()