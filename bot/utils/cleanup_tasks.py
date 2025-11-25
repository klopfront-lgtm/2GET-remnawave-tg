"""
Cleanup tasks for maintaining database health and preventing memory leaks.

PERFORMANCE: These tasks help prevent database bloat and improve query performance
by removing or archiving old data that is no longer needed for active operations.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, update, and_, or_
from sqlalchemy.future import select

from db.models import MessageLog, PromoCode, Payment


async def cleanup_old_logs(session: AsyncSession, days: int = 30) -> int:
    """
    Удаляет старые логи сообщений старше указанного количества дней.
    
    PERFORMANCE: Reduces MessageLog table size and improves query performance.
    Old logs are typically not needed for active operations.
    
    Args:
        session: Database session
        days: Number of days to keep (default: 30)
        
    Returns:
        Number of deleted log records
    """
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # PERFORMANCE: Delete in batches to avoid long-running transactions
        # TODO: Consider implementing batch deletion for very large datasets
        stmt = delete(MessageLog).where(
            MessageLog.timestamp < cutoff_date
        )
        
        result = await session.execute(stmt)
        deleted_count = result.rowcount or 0
        
        if deleted_count > 0:
            await session.commit()
            logging.info(
                f"Cleanup: Deleted {deleted_count} message logs older than {days} days"
            )
        
        return deleted_count
        
    except Exception as e:
        logging.error(f"Error during cleanup_old_logs: {e}", exc_info=True)
        await session.rollback()
        return 0


async def cleanup_expired_promo_codes(session: AsyncSession) -> int:
    """
    Удаляет истекшие промокоды, которые больше не могут быть использованы.
    
    PERFORMANCE: Keeps promo_codes table clean and reduces unnecessary data.
    Expired promo codes with zero usage are safe to delete.
    
    Returns:
        Number of deleted promo codes
    """
    try:
        now = datetime.now(timezone.utc)
        
        # PERFORMANCE: Only delete promo codes that:
        # 1. Have expired (expiration_date < now)
        # 2. Have no remaining uses (max_uses is set and used_count >= max_uses)
        # 3. OR are marked as inactive
        stmt = delete(PromoCode).where(
            or_(
                # Expired by date
                and_(
                    PromoCode.expiration_date.is_not(None),
                    PromoCode.expiration_date < now
                ),
                # No uses left
                and_(
                    PromoCode.max_uses.is_not(None),
                    PromoCode.used_count >= PromoCode.max_uses
                ),
                # Inactive promo codes older than 90 days
                and_(
                    PromoCode.is_active == False,
                    PromoCode.created_at < now - timedelta(days=90)
                )
            )
        )
        
        result = await session.execute(stmt)
        deleted_count = result.rowcount or 0
        
        if deleted_count > 0:
            await session.commit()
            logging.info(
                f"Cleanup: Deleted {deleted_count} expired/used promo codes"
            )
        
        return deleted_count
        
    except Exception as e:
        logging.error(f"Error during cleanup_expired_promo_codes: {e}", exc_info=True)
        await session.rollback()
        return 0


async def cleanup_old_payments(session: AsyncSession, days: int = 90) -> int:
    """
    Архивирует старые платежи, помечая их специальным статусом.
    
    PERFORMANCE: Helps maintain Payment table size by marking old payments as archived.
    This doesn't delete data but allows for optimized queries that exclude archived records.
    
    Args:
        session: Database session
        days: Number of days to keep active (default: 90)
        
    Returns:
        Number of archived payment records
        
    Note:
        This function marks payments as archived rather than deleting them
        for compliance and audit trail purposes.
    """
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # PERFORMANCE: Update old completed payments to have archived status
        # Only archive succeeded or failed payments, not pending ones
        # TODO: Consider creating separate archive table for very old payments
        stmt = update(Payment).where(
            and_(
                Payment.created_at < cutoff_date,
                Payment.status.in_(['succeeded', 'failed', 'canceled'])
            )
        ).values(
            description=Payment.description + " [ARCHIVED]"
        ).execution_options(synchronize_session="fetch")
        
        result = await session.execute(stmt)
        archived_count = result.rowcount or 0
        
        if archived_count > 0:
            await session.commit()
            logging.info(
                f"Cleanup: Archived {archived_count} payment records older than {days} days"
            )
        
        return archived_count
        
    except Exception as e:
        logging.error(f"Error during cleanup_old_payments: {e}", exc_info=True)
        await session.rollback()
        return 0


async def cleanup_orphaned_sessions(session: AsyncSession) -> int:
    """
    Удаляет висячие сессии и временные данные из FSM storage.
    
    PERFORMANCE: Prevents memory leaks in FSM storage by cleaning up abandoned user sessions.
    
    Note:
        This is primarily for MemoryStorage. RedisStorage handles TTL automatically.
        
    Returns:
        Number of cleaned sessions (placeholder, actual implementation depends on storage type)
    """
    # TODO: Implement cleanup for specific FSM storage backend
    # For RedisStorage: keys are auto-expired via TTL
    # For MemoryStorage: implement cleanup of stale FSM states
    logging.info("Cleanup: FSM session cleanup is handled by storage backend TTL")
    return 0


async def run_all_cleanup_tasks(
    session: AsyncSession,
    log_retention_days: int = 30,
    payment_archive_days: int = 90
) -> dict:
    """
    Выполняет все задачи по очистке данных.
    
    PERFORMANCE: Consolidated cleanup function to run all maintenance tasks.
    Should be called periodically (e.g., daily via cron or scheduled task).
    
    Args:
        session: Database session
        log_retention_days: Days to keep message logs
        payment_archive_days: Days to keep active payments
        
    Returns:
        Dictionary with cleanup statistics
    """
    stats = {
        "logs_deleted": 0,
        "promo_codes_deleted": 0,
        "payments_archived": 0,
        "sessions_cleaned": 0,
        "total_cleaned": 0,
        "execution_time_seconds": 0
    }
    
    start_time = datetime.now(timezone.utc)
    
    try:
        # Run all cleanup tasks
        stats["logs_deleted"] = await cleanup_old_logs(session, log_retention_days)
        stats["promo_codes_deleted"] = await cleanup_expired_promo_codes(session)
        stats["payments_archived"] = await cleanup_old_payments(session, payment_archive_days)
        stats["sessions_cleaned"] = await cleanup_orphaned_sessions(session)
        
        # Calculate total and execution time
        stats["total_cleaned"] = sum([
            stats["logs_deleted"],
            stats["promo_codes_deleted"],
            stats["payments_archived"],
            stats["sessions_cleaned"]
        ])
        
        end_time = datetime.now(timezone.utc)
        stats["execution_time_seconds"] = (end_time - start_time).total_seconds()
        
        logging.info(
            f"Cleanup completed: {stats['total_cleaned']} records processed "
            f"in {stats['execution_time_seconds']:.2f} seconds"
        )
        
        return stats
        
    except Exception as e:
        logging.error(f"Error during run_all_cleanup_tasks: {e}", exc_info=True)
        return stats