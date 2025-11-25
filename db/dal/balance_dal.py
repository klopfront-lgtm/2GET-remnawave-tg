from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.models import UserBalance, User
from db.dal.user_dal import get_user_by_id

async def add_balance_operation(
    session: AsyncSession,
    user_id: int,
    amount: float,
    operation_type: str,
    description: Optional[str] = None,
    currency: str = "RUB"
) -> Optional[UserBalance]:
    """
    Adds a balance operation and updates the user's current balance transactionally.
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        return None

    # Create balance operation record
    operation = UserBalance(
        user_id=user_id,
        amount=amount,
        currency=currency,
        operation_type=operation_type,
        description=description
    )
    session.add(operation)
    
    # Update user balance
    # Ensure balance doesn't go below zero if needed, or handle logic here
    # For now, we assume validation happens before calling this or negative balance is allowed
    user.balance += amount
    
    await session.flush()
    await session.refresh(operation)
    
    return operation

async def get_user_balance_history(
    session: AsyncSession, 
    user_id: int, 
    limit: int = 20, 
    offset: int = 0
) -> List[UserBalance]:
    stmt = (
        select(UserBalance)
        .where(UserBalance.user_id == user_id)
        .order_by(UserBalance.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.scalars().all()

async def get_user_balance_count(session: AsyncSession, user_id: int) -> int:
    from sqlalchemy import func
    stmt = select(func.count(UserBalance.id)).where(UserBalance.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one()