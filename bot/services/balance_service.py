import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from db.dal import user_dal
from db.dal import balance_dal
from db.models import UserBalance


class InsufficientFundsError(Exception):
    """Исключение при недостаточности средств на балансе"""
    pass


class BalanceService:
    """Сервис для работы с балансом пользователя"""

    async def get_balance(self, session: AsyncSession, user_id: int) -> float:
        """
        Получить текущий баланс пользователя.
        
        Args:
            session: Сессия БД
            user_id: ID пользователя
            
        Returns:
            float: Текущий баланс пользователя
        """
        user = await user_dal.get_user_by_id(session, user_id)
        if not user:
            logging.warning(f"User {user_id} not found when getting balance")
            return 0.0
        
        return user.balance or 0.0

    async def deposit(
        self,
        session: AsyncSession,
        user_id: int,
        amount: float,
        description: Optional[str] = None,
        currency: str = "RUB"
    ) -> Optional[UserBalance]:
        """
        Пополнить баланс пользователя.
        
        Args:
            session: Сессия БД (должна использоваться в транзакции)
            user_id: ID пользователя
            amount: Сумма пополнения (должна быть положительной)
            description: Описание операции
            currency: Валюта операции
            
        Returns:
            UserBalance: Запись об операции или None при ошибке
        """
        if amount <= 0:
            logging.error(f"Attempt to deposit non-positive amount {amount} for user {user_id}")
            return None

        operation = await balance_dal.add_balance_operation(
            session=session,
            user_id=user_id,
            amount=amount,
            operation_type="deposit",
            description=description or "Пополнение баланса",
            currency=currency
        )
        
        if operation:
            logging.info(
                f"Balance deposit successful: user_id={user_id}, "
                f"amount={amount} {currency}, description='{description}'"
            )
        else:
            logging.error(f"Failed to deposit {amount} {currency} for user {user_id}")
        
        return operation

    async def charge(
        self,
        session: AsyncSession,
        user_id: int,
        amount: float,
        description: Optional[str] = None,
        currency: str = "RUB"
    ) -> Optional[UserBalance]:
        """
        Списать средства с баланса пользователя.
        
        Args:
            session: Сессия БД (должна использоваться в транзакции)
            user_id: ID пользователя
            amount: Сумма списания (должна быть положительной)
            description: Описание операции
            currency: Валюта операции
            
        Returns:
            UserBalance: Запись об операции
            
        Raises:
            InsufficientFundsError: Недостаточно средств на балансе
        """
        if amount <= 0:
            logging.error(f"Attempt to charge non-positive amount {amount} for user {user_id}")
            return None

        # Проверяем достаточность средств
        current_balance = await self.get_balance(session, user_id)
        if current_balance < amount:
            raise InsufficientFundsError(
                f"Insufficient funds for user {user_id}: "
                f"balance={current_balance}, required={amount}"
            )

        # Списываем средства (отрицательная сумма)
        operation = await balance_dal.add_balance_operation(
            session=session,
            user_id=user_id,
            amount=-amount,  # Отрицательное значение для списания
            operation_type="withdrawal",
            description=description or "Списание с баланса",
            currency=currency
        )
        
        if operation:
            logging.info(
                f"Balance charge successful: user_id={user_id}, "
                f"amount={amount} {currency}, description='{description}'"
            )
        else:
            logging.error(f"Failed to charge {amount} {currency} from user {user_id}")
        
        return operation

    async def refund(
        self,
        session: AsyncSession,
        user_id: int,
        amount: float,
        reason: Optional[str] = None,
        currency: str = "RUB"
    ) -> Optional[UserBalance]:
        """
        Вернуть средства на баланс пользователя.
        
        Args:
            session: Сессия БД (должна использоваться в транзакции)
            user_id: ID пользователя
            amount: Сумма возврата (должна быть положительной)
            reason: Причина возврата
            currency: Валюта операции
            
        Returns:
            UserBalance: Запись об операции или None при ошибке
        """
        if amount <= 0:
            logging.error(f"Attempt to refund non-positive amount {amount} for user {user_id}")
            return None

        description = f"Возврат средств"
        if reason:
            description += f": {reason}"

        operation = await balance_dal.add_balance_operation(
            session=session,
            user_id=user_id,
            amount=amount,
            operation_type="refund",
            description=description,
            currency=currency
        )
        
        if operation:
            logging.info(
                f"Balance refund successful: user_id={user_id}, "
                f"amount={amount} {currency}, reason='{reason}'"
            )
        else:
            logging.error(f"Failed to refund {amount} {currency} to user {user_id}")
        
        return operation

    async def get_balance_history(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Получить историю операций с балансом.
        
        Args:
            session: Сессия БД
            user_id: ID пользователя
            limit: Максимальное количество записей
            offset: Смещение для пагинации
            
        Returns:
            List[Dict]: Список операций с балансом
        """
        operations = await balance_dal.get_user_balance_history(
            session=session,
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        
        result = []
        for op in operations:
            result.append({
                "id": op.id,
                "amount": op.amount,
                "currency": op.currency,
                "operation_type": op.operation_type,
                "description": op.description,
                "created_at": op.created_at,
            })
        
        logging.debug(f"Retrieved {len(result)} balance history records for user {user_id}")
        return result

    async def add_bonus(
        self,
        session: AsyncSession,
        user_id: int,
        amount: float,
        description: Optional[str] = None,
        currency: str = "RUB"
    ) -> Optional[UserBalance]:
        """
        Добавить бонус на баланс пользователя.
        
        Args:
            session: Сессия БД (должна использоваться в транзакции)
            user_id: ID пользователя
            amount: Сумма бонуса (должна быть положительной)
            description: Описание операции
            currency: Валюта операции
            
        Returns:
            UserBalance: Запись об операции или None при ошибке
        """
        if amount <= 0:
            logging.error(f"Attempt to add non-positive bonus {amount} for user {user_id}")
            return None

        operation = await balance_dal.add_balance_operation(
            session=session,
            user_id=user_id,
            amount=amount,
            operation_type="bonus",
            description=description or "Бонусное начисление",
            currency=currency
        )
        
        if operation:
            logging.info(
                f"Bonus added: user_id={user_id}, "
                f"amount={amount} {currency}, description='{description}'"
            )
        else:
            logging.error(f"Failed to add bonus {amount} {currency} for user {user_id}")
        
        return operation

    async def record_payment(
        self,
        session: AsyncSession,
        user_id: int,
        amount: float,
        description: Optional[str] = None,
        currency: str = "RUB"
    ) -> Optional[UserBalance]:
        """
        Записать оплату подписки с использованием баланса.
        
        Args:
            session: Сессия БД (должна использоваться в транзакции)
            user_id: ID пользователя
            amount: Сумма оплаты (должна быть положительной)
            description: Описание операции
            currency: Валюта операции
            
        Returns:
            UserBalance: Запись об операции
            
        Raises:
            InsufficientFundsError: Недостаточно средств на балансе
        """
        if amount <= 0:
            logging.error(f"Attempt to record non-positive payment {amount} for user {user_id}")
            return None

        # Проверяем достаточность средств
        current_balance = await self.get_balance(session, user_id)
        if current_balance < amount:
            raise InsufficientFundsError(
                f"Insufficient funds for payment: user {user_id}: "
                f"balance={current_balance}, required={amount}"
            )

        # Записываем оплату (отрицательная сумма)
        operation = await balance_dal.add_balance_operation(
            session=session,
            user_id=user_id,
            amount=-amount,  # Отрицательное значение для списания
            operation_type="payment",
            description=description or "Оплата подписки с баланса",
            currency=currency
        )
        
        if operation:
            logging.info(
                f"Payment from balance successful: user_id={user_id}, "
                f"amount={amount} {currency}, description='{description}'"
            )
        else:
            logging.error(f"Failed to record payment {amount} {currency} from user {user_id}")
        
        return operation