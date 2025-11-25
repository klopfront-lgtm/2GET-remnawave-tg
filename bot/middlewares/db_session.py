import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Update
from sqlalchemy.orm import sessionmaker


class DBSessionMiddleware(BaseMiddleware):

    def __init__(self, async_session_factory: sessionmaker):
        super().__init__()
        self.async_session_factory = async_session_factory

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        if self.async_session_factory is None:
            logging.critical("DBSessionMiddleware: async_session_factory is None!")
            raise RuntimeError(
                "async_session_factory not provided to DBSessionMiddleware"
            )

        async with self.async_session_factory() as session:
            data["session"] = session
            # Флаг для явного контроля коммита (по умолчанию True для обратной совместимости)
            data["auto_commit"] = True
            try:
                result = await handler(event, data)

                # Коммит только если handler успешно завершился и автокоммит не отключен
                if data.get("auto_commit", True) and result is not None:
                    await session.commit()
                elif data.get("auto_commit", True):
                    # Handler вернул None, но ошибок не было - коммитим
                    await session.commit()
                else:
                    # Автокоммит отключен явно - handler сам управляет транзакцией
                    logging.debug("Auto-commit disabled by handler")
                    
                return result
            except Exception:
                await session.rollback()
                logging.error(
                    "DBSessionMiddleware: Exception caused rollback.", exc_info=True
                )
                raise

