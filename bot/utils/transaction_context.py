"""
Context manager для атомарных транзакций с поддержкой автоматического rollback.

Использование:
    async with TransactionContext(session) as tx:
        # Выполнить операции с БД
        await some_db_operation(tx.session)
        # Если нужно явно откатить транзакцию
        tx.mark_for_rollback()
        
    # Автоматический commit/rollback в __aexit__
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession


class TransactionContext:
    """
    Async context manager для атомарных транзакций с гарантированным commit/rollback.
    
    Обеспечивает:
    - Автоматический commit при успешном завершении
    - Автоматический rollback при исключениях
    - Возможность явного rollback через mark_for_rollback()
    - Защиту от несогласованности данных
    """
    
    def __init__(self, session: AsyncSession, auto_commit: bool = True):
        """
        Инициализация контекста транзакции.
        
        Args:
            session: Активная сессия SQLAlchemy
            auto_commit: Автоматически коммитить при успешном завершении (по умолчанию True)
        """
        self.session = session
        self.auto_commit = auto_commit
        self._should_rollback = False
        self._committed = False
        
    async def __aenter__(self):
        """Вход в контекст - начало транзакции"""
        # SQLAlchemy автоматически начинает транзакцию при первой операции
        # но мы можем явно начать, если нужно
        self._should_rollback = False
        self._committed = False
        logging.debug("TransactionContext: Entering transaction context")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Выход из контекста - commit или rollback.
        
        Args:
            exc_type: Тип исключения (если произошло)
            exc_val: Значение исключения
            exc_tb: Traceback исключения
            
        Returns:
            False - исключение будет прокинуто дальше
        """
        try:
            if exc_type is not None:
                # Произошло исключение - откатываем
                logging.warning(
                    f"TransactionContext: Exception occurred, rolling back: {exc_type.__name__}"
                )
                await self.session.rollback()
                self._committed = False
                
            elif self._should_rollback:
                # Явно запрошен rollback через mark_for_rollback()
                logging.info("TransactionContext: Explicit rollback requested")
                await self.session.rollback()
                self._committed = False
                
            elif self.auto_commit and not self._committed:
                # Успешное завершение и автокоммит включен - коммитим
                logging.debug("TransactionContext: Committing transaction")
                await self.session.commit()
                self._committed = True
                
            else:
                # Автокоммит отключен - оставляем транзакцию открытой
                logging.debug("TransactionContext: Auto-commit disabled, transaction left open")
                
        except Exception as e:
            # Ошибка при commit/rollback - пытаемся откатить
            logging.error(
                f"TransactionContext: Error during commit/rollback: {e}",
                exc_info=True
            )
            try:
                await self.session.rollback()
            except Exception as rollback_error:
                logging.critical(
                    f"TransactionContext: Failed to rollback after error: {rollback_error}",
                    exc_info=True
                )
            raise
        
        # Не подавляем исключения - пробрасываем дальше
        return False
    
    def mark_for_rollback(self):
        """
        Пометить транзакцию для отката.
        Используется когда нужно откатить изменения без выброса исключения.
        """
        logging.debug("TransactionContext: Transaction marked for rollback")
        self._should_rollback = True
    
    async def commit(self):
        """
        Явный commit транзакции внутри контекста.
        Полезно для промежуточных коммитов в длинных операциях.
        """
        if not self._committed and not self._should_rollback:
            logging.debug("TransactionContext: Explicit commit called")
            await self.session.commit()
            self._committed = True
        else:
            logging.warning("TransactionContext: Commit called but transaction already committed or marked for rollback")
    
    async def rollback(self):
        """
        Явный rollback транзакции внутри контекста.
        """
        logging.debug("TransactionContext: Explicit rollback called")
        await self.session.rollback()
        self._should_rollback = True
        self._committed = False