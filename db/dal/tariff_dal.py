from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.models import Tariff

async def create_tariff(session: AsyncSession, tariff_data: dict) -> Tariff:
    new_tariff = Tariff(**tariff_data)
    session.add(new_tariff)
    await session.flush()
    await session.refresh(new_tariff)
    return new_tariff

async def get_tariff_by_id(session: AsyncSession, tariff_id: int) -> Optional[Tariff]:
    return await session.get(Tariff, tariff_id)

async def get_active_tariffs(session: AsyncSession) -> List[Tariff]:
    stmt = select(Tariff).where(Tariff.is_active == True).order_by(Tariff.price)
    result = await session.execute(stmt)
    return result.scalars().all()

async def get_all_tariffs(session: AsyncSession) -> List[Tariff]:
    stmt = select(Tariff).order_by(Tariff.id)
    result = await session.execute(stmt)
    return result.scalars().all()

async def update_tariff(session: AsyncSession, tariff_id: int, update_data: dict) -> Optional[Tariff]:
    tariff = await get_tariff_by_id(session, tariff_id)
    if not tariff:
        return None
    
    for key, value in update_data.items():
        setattr(tariff, key, value)
    
    await session.flush()
    await session.refresh(tariff)
    return tariff

async def delete_tariff(session: AsyncSession, tariff_id: int) -> bool:
    tariff = await get_tariff_by_id(session, tariff_id)
    if not tariff:
        return False
    
    await session.delete(tariff)
    await session.flush()
    return True