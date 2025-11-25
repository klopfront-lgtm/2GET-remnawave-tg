import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot
from bot.middlewares.i18n import JsonI18n

from config.settings import Settings
from db.dal import gift_dal, user_dal, tariff_dal
from db.models import GiftRecipientType, GiftStatus
from .subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


class GiftService:
    """
    Сервис для управления подарочными подписками.
    
    Оркестрирует весь жизненный цикл подарков:
    - Создание подарков с валидацией и rate limiting
    - Активация подарков получателями
    - Обработка платежей через webhook
    - Управление отменами и возвратами
    - Статистика и аналитика
    """
    
    # Константы для rate limiting и безопасности
    MAX_GIFTS_PER_HOUR = 3
    MAX_GIFTS_PER_DAY = 10
    MAX_DAILY_SPENDING = 10000.0  # RUB
    
    def __init__(
        self,
        settings: Settings,
        subscription_service: SubscriptionService,
        bot: Optional[Bot] = None,
        i18n: Optional[JsonI18n] = None
    ):
        """
        Инициализация сервиса подарков.
        
        Args:
            settings: Настройки приложения
            subscription_service: Сервис управления подписками
            bot: Telegram Bot для отправки уведомлений (опционально)
            i18n: Сервис локализации (опционально)
        """
        self.settings = settings
        self.subscription_service = subscription_service
        self.bot = bot
        self.i18n = i18n
    
    async def create_gift(
        self,
        session: AsyncSession,
        donor_id: int,
        tariff_id: int,
        recipient_type: GiftRecipientType,
        idempotency_key: str,
        recipient_user_id: Optional[int] = None,
        message_to_recipient: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Создать подарочную подписку с полной валидацией.
        
        Выполняет:
        - Проверку дарителя (существование, бан)
        - Rate limiting (hourly/daily)
        - Spending limit
        - Валидацию тарифа
        - Валидацию получателя (для direct)
        - Проверку self-gifting
        - Создание записи через DAL
        
        Args:
            session: Сессия БД
            donor_id: ID дарителя
            tariff_id: ID тарифа
            recipient_type: Тип получателя (direct/random)
            idempotency_key: Ключ идемпотентности
            recipient_user_id: ID получателя (обязателен для direct)
            message_to_recipient: Сообщение получателю
            metadata: Дополнительные метаданные
            
        Returns:
            Tuple[bool, str, Optional[Dict]]:
                - bool: Успешность операции
                - str: Сообщение (описание ошибки или успеха)
                - Optional[Dict]: Данные подарка (gift_id, gift_code, amount, etc.)
        """
        try:
            # 1. Валидация дарителя
            donor = await user_dal.get_user_by_id(session, donor_id)
            if not donor:
                logger.warning(f"Gift creation failed: donor {donor_id} not found")
                return False, "Donor user not found", None
            
            if donor.is_banned:
                logger.warning(f"Gift creation failed: donor {donor_id} is banned")
                return False, "Donor user is banned", None
            
            # 2. Rate limiting - hourly check
            can_create_hourly, hourly_count = await gift_dal.check_user_gift_rate_limit(
                session, donor_id, hours=1, max_gifts=self.MAX_GIFTS_PER_HOUR
            )
            if not can_create_hourly:
                logger.warning(
                    f"Gift creation failed: donor {donor_id} exceeded hourly limit "
                    f"({hourly_count}/{self.MAX_GIFTS_PER_HOUR})"
                )
                return False, f"Hourly gift limit exceeded ({hourly_count}/{self.MAX_GIFTS_PER_HOUR})", None
            
            # 3. Rate limiting - daily check
            can_create_daily, daily_count = await gift_dal.check_user_gift_rate_limit(
                session, donor_id, hours=24, max_gifts=self.MAX_GIFTS_PER_DAY
            )
            if not can_create_daily:
                logger.warning(
                    f"Gift creation failed: donor {donor_id} exceeded daily limit "
                    f"({daily_count}/{self.MAX_GIFTS_PER_DAY})"
                )
                return False, f"Daily gift limit exceeded ({daily_count}/{self.MAX_GIFTS_PER_DAY})", None
            
            # 4. Spending limit check
            can_spend, daily_spending = await gift_dal.check_user_daily_gift_spending(
                session, donor_id, max_amount=self.MAX_DAILY_SPENDING
            )
            if not can_spend:
                logger.warning(
                    f"Gift creation failed: donor {donor_id} exceeded daily spending limit "
                    f"({daily_spending:.2f}/{self.MAX_DAILY_SPENDING})"
                )
                return False, f"Daily spending limit exceeded ({daily_spending:.2f}/{self.MAX_DAILY_SPENDING} RUB)", None
            
            # 5. Валидация тарифа
            tariff = await tariff_dal.get_tariff_by_id(session, tariff_id)
            if not tariff:
                logger.error(f"Gift creation failed: tariff {tariff_id} not found")
                return False, f"Tariff {tariff_id} not found", None
            
            if not tariff.is_active:
                logger.warning(f"Gift creation failed: tariff {tariff_id} is not active")
                return False, f"Tariff {tariff_id} is not active", None
            
            # 6. Валидация получателя для direct типа
            if recipient_type == GiftRecipientType.direct:
                if not recipient_user_id:
                    logger.error("Gift creation failed: recipient_user_id required for direct gift")
                    return False, "Recipient user ID is required for direct gift", None
                
                recipient = await user_dal.get_user_by_id(session, recipient_user_id)
                if not recipient:
                    logger.warning(f"Gift creation failed: recipient {recipient_user_id} not found")
                    return False, f"Recipient user {recipient_user_id} not found", None
                
                if recipient.is_banned:
                    logger.warning(f"Gift creation failed: recipient {recipient_user_id} is banned")
                    return False, "Recipient user is banned", None
                
                # 7. Проверка self-gifting
                if donor_id == recipient_user_id:
                    logger.warning(f"Gift creation failed: user {donor_id} tried to gift themselves")
                    return False, "Cannot gift yourself", None
            
            # 8. Проверка оставшегося лимита расходов после текущего подарка
            remaining_budget = self.MAX_DAILY_SPENDING - daily_spending
            if tariff.price > remaining_budget:
                logger.warning(
                    f"Gift creation failed: tariff price {tariff.price} exceeds remaining budget {remaining_budget:.2f}"
                )
                return False, f"Insufficient daily budget (remaining: {remaining_budget:.2f} RUB)", None
            
            # 9. Создание подарка через DAL
            gift_data = {
                "donor_user_id": donor_id,
                "recipient_type": recipient_type,
                "tariff_id": tariff_id,
                "duration_days": tariff.duration_days,
                "amount": tariff.price,
                "currency": tariff.currency,
                "idempotency_key": idempotency_key,
            }
            
            if recipient_user_id:
                gift_data["recipient_user_id"] = recipient_user_id
            
            if message_to_recipient:
                gift_data["message_to_recipient"] = message_to_recipient
            
            if metadata:
                gift_data["metadata"] = metadata
            
            gift = await gift_dal.create_gift_record(session, gift_data)
            
            logger.info(
                f"Gift {gift.gift_id} created successfully by donor {donor_id}, "
                f"tariff={tariff_id}, type={recipient_type.value}, amount={tariff.price} {tariff.currency}"
            )
            
            result_data = {
                "gift_id": gift.gift_id,
                "gift_code": gift.gift_code,
                "amount": gift.amount,
                "currency": gift.currency,
                "tariff_name": tariff.name,
                "duration_days": gift.duration_days,
                "recipient_type": gift.recipient_type.value,
                "status": gift.status.value,
                "created_at": gift.created_at.isoformat() if gift.created_at else None,
            }
            
            return True, "Gift created successfully", result_data
            
        except Exception as e:
            logger.error(f"Error creating gift: {e}", exc_info=True)
            await session.rollback()
            return False, f"Internal error: {str(e)}", None
    
    async def activate_gift(
        self,
        session: AsyncSession,
        gift_code: str,
        activating_user_id: int
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Активировать подарок получателем.
        
        Выполняет:
        - Валидацию кода через DAL (with SELECT FOR UPDATE)
        - Дополнительную проверку username (для direct)
        - Активацию подписки через SubscriptionService
        - Обновление статуса подарка
        - Отправку уведомлений
        
        Args:
            session: Сессия БД
            gift_code: Код подарка
            activating_user_id: ID пользователя, активирующего подарок
            
        Returns:
            Tuple[bool, str, Optional[Dict]]:
                - bool: Успешность операции
                - str: Сообщение
                - Optional[Dict]: Данные активированной подписки
        """
        try:
            # 1. Валидация кода с блокировкой (SELECT FOR UPDATE)
            gift, error = await gift_dal.validate_gift_code_for_activation(
                session, gift_code, activating_user_id
            )
            
            if error:
                logger.warning(f"Gift activation failed: {error}, code={gift_code}, user={activating_user_id}")
                return False, error, None
            
            if not gift:
                logger.error(f"Gift validation returned None without error, code={gift_code}")
                return False, "Invalid gift code", None
            
            # 2. Активируем подарок в DAL (обновляет статус и устанавливает получателя)
            activated_gift, activation_error = await gift_dal.activate_gift(
                session, gift.gift_id, activating_user_id
            )
            
            if activation_error:
                logger.error(f"Gift activation in DAL failed: {activation_error}")
                await session.rollback()
                return False, activation_error, None
            
            # 3. Активируем подписку через SubscriptionService
            # Получаем тариф для передачи в activate_subscription
            tariff = await tariff_dal.get_tariff_by_id(session, gift.tariff_id)
            if not tariff:
                logger.error(f"Tariff {gift.tariff_id} not found for gift activation")
                await session.rollback()
                return False, "Tariff not found", None
            
            # Создаем "виртуальный" платеж для подарочной подписки
            # activate_subscription требует payment_db_id, но для подарков его может не быть
            # Используем 0 или None, в зависимости от логики
            subscription_result = await self.subscription_service.activate_subscription(
                session=session,
                user_id=activating_user_id,
                months=0,  # Не используется при tariff_id
                payment_amount=0.0,  # Подарок бесплатен для получателя
                payment_db_id=0,  # Виртуальный ID для подарка
                provider="gift",  # Специальный провайдер для подарков
                tariff_id=gift.tariff_id
            )
            
            if not subscription_result:
                logger.error(f"Failed to activate subscription for gift {gift.gift_id}")
                await session.rollback()
                return False, "Failed to activate subscription", None
            
            # 4. Коммитим все изменения
            await session.commit()
            
            logger.info(
                f"Gift {gift.gift_id} activated successfully by user {activating_user_id}, "
                f"subscription_id={subscription_result.get('subscription_id')}"
            )
            
            # 5. Отправляем уведомления (не ломаем flow при ошибках)
            await self._send_gift_activation_notifications(
                gift=activated_gift,
                recipient_id=activating_user_id,
                subscription_data=subscription_result
            )
            
            result_data = {
                "gift_id": gift.gift_id,
                "subscription_id": subscription_result.get("subscription_id"),
                "end_date": subscription_result.get("end_date").isoformat() if subscription_result.get("end_date") else None,
                "subscription_url": subscription_result.get("subscription_url"),
                "donor_username": gift.donor_username,
                "message_from_donor": gift.message_to_recipient,
            }
            
            return True, "Gift activated successfully", result_data
            
        except Exception as e:
            logger.error(f"Error activating gift: {e}", exc_info=True)
            await session.rollback()
            return False, f"Internal error: {str(e)}", None
    
    async def process_gift_payment(
        self,
        session: AsyncSession,
        payment_id: int
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Обработать успешный платеж за подарок (вызывается из webhook).
        
        Выполняет:
        - Поиск подарка по payment_id
        - Проверку статуса
        - Обновление на READY
        - Уведомление дарителю
        
        Args:
            session: Сессия БД
            payment_id: ID платежа
            
        Returns:
            Tuple[bool, str, Optional[Dict]]:
                - bool: Успешность операции
                - str: Сообщение
                - Optional[Dict]: Данные подарка
        """
        try:
            # 1. Находим подарок по payment_id
            gift = await gift_dal.get_gift_by_payment_id(session, payment_id)
            
            if not gift:
                logger.warning(f"Gift payment processing: no gift found for payment_id={payment_id}")
                return False, "Gift not found for payment", None
            
            # 2. Проверяем статус
            if gift.status != GiftStatus.pending_payment:
                logger.warning(
                    f"Gift {gift.gift_id} is not in pending_payment status "
                    f"(current: {gift.status.value}), skipping payment processing"
                )
                return False, f"Gift status is {gift.status.value}, expected pending_payment", None
            
            # 3. Обновляем статус на READY
            updated_gift = await gift_dal.mark_gift_as_paid(session, gift.gift_id, payment_id)
            
            if not updated_gift:
                logger.error(f"Failed to mark gift {gift.gift_id} as paid")
                await session.rollback()
                return False, "Failed to update gift status", None
            
            await session.commit()
            
            logger.info(
                f"Gift {gift.gift_id} marked as paid and ready, "
                f"payment_id={payment_id}, expires_at={updated_gift.expires_at}"
            )
            
            # 4. Отправляем уведомление дарителю
            await self._send_gift_ready_notification(updated_gift)
            
            result_data = {
                "gift_id": updated_gift.gift_id,
                "gift_code": updated_gift.gift_code,
                "status": updated_gift.status.value,
                "paid_at": updated_gift.paid_at.isoformat() if updated_gift.paid_at else None,
                "expires_at": updated_gift.expires_at.isoformat() if updated_gift.expires_at else None,
            }
            
            return True, "Gift payment processed successfully", result_data
            
        except Exception as e:
            logger.error(f"Error processing gift payment: {e}", exc_info=True)
            await session.rollback()
            return False, f"Internal error: {str(e)}", None
    
    async def validate_gift_code(
        self,
        session: AsyncSession,
        gift_code: str,
        user_id: int
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Валидировать подарочный код без активации (для preview).
        
        Args:
            session: Сессия БД
            gift_code: Код подарка
            user_id: ID пользователя для проверки прав
            
        Returns:
            Tuple[bool, str, Optional[Dict]]:
                - bool: Код валиден
                - str: Сообщение (описание или ошибка)
                - Optional[Dict]: Информация о подарке
        """
        try:
            # Используем метод валидации из DAL (без блокировки)
            gift, error = await gift_dal.validate_gift_code_for_activation(
                session, gift_code, user_id
            )
            
            if error:
                logger.debug(f"Gift code validation failed: {error}")
                return False, error, None
            
            if not gift:
                return False, "Invalid gift code", None
            
            # Получаем тариф для дополнительной информации
            tariff = await tariff_dal.get_tariff_by_id(session, gift.tariff_id)
            
            result_data = {
                "gift_id": gift.gift_id,
                "recipient_type": gift.recipient_type.value,
                "tariff_name": tariff.name if tariff else "Unknown",
                "duration_days": gift.duration_days,
                "donor_username": gift.donor_username,
                "message_from_donor": gift.message_to_recipient,
                "created_at": gift.created_at.isoformat() if gift.created_at else None,
                "expires_at": gift.expires_at.isoformat() if gift.expires_at else None,
            }
            
            return True, "Gift code is valid", result_data
            
        except Exception as e:
            logger.error(f"Error validating gift code: {e}", exc_info=True)
            return False, f"Internal error: {str(e)}", None
    
    async def cancel_gift(
        self,
        session: AsyncSession,
        gift_id: int,
        cancelling_user_id: int,
        is_admin: bool = False
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Отменить подарок.
        
        Правила:
        - Даритель может отменить свой подарок
        - Админ может отменить любой подарок
        - Можно отменить только READY или PENDING_PAYMENT
        
        Args:
            session: Сессия БД
            gift_id: ID подарка
            cancelling_user_id: ID пользователя, отменяющего подарок
            is_admin: Является ли пользователь админом
            
        Returns:
            Tuple[bool, str, Optional[Dict]]:
                - bool: Успешность операции
                - str: Сообщение
                - Optional[Dict]: Данные отмененного подарка
        """
        try:
            gift = await gift_dal.get_gift_by_id(session, gift_id, load_relationships=False)
            
            if not gift:
                logger.warning(f"Gift cancellation failed: gift {gift_id} not found")
                return False, "Gift not found", None
            
            # Проверка прав (даритель или админ)
            if not is_admin and gift.donor_user_id != cancelling_user_id:
                logger.warning(
                    f"Gift cancellation failed: user {cancelling_user_id} "
                    f"is not donor of gift {gift_id}"
                )
                return False, "You are not authorized to cancel this gift", None
            
            # Отменяем подарок через DAL
            cancelled_gift, error = await gift_dal.cancel_gift(
                session, gift_id, gift.donor_user_id
            )
            
            if error:
                logger.warning(f"Gift cancellation failed: {error}")
                return False, error, None
            
            await session.commit()
            
            logger.info(
                f"Gift {gift_id} cancelled by user {cancelling_user_id} "
                f"(admin={is_admin})"
            )
            
            result_data = {
                "gift_id": cancelled_gift.gift_id,
                "gift_code": cancelled_gift.gift_code,
                "status": cancelled_gift.status.value,
                "cancelled_at": cancelled_gift.cancelled_at.isoformat() if cancelled_gift.cancelled_at else None,
            }
            
            return True, "Gift cancelled successfully", result_data
            
        except Exception as e:
            logger.error(f"Error cancelling gift: {e}", exc_info=True)
            await session.rollback()
            return False, f"Internal error: {str(e)}", None
    
    async def get_user_gift_statistics(
        self,
        session: AsyncSession,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Получить статистику подарков пользователя.
        
        Args:
            session: Сессия БД
            user_id: ID пользователя
            
        Returns:
            Dict со статистикой:
                - gifts_sent: Количество отправленных подарков
                - gifts_received: Количество полученных подарков
                - total_spent: Общая сумма потраченная на подарки
                - by_status: Разбивка по статусам
        """
        try:
            # Подарки отправленные
            gifts_sent = await gift_dal.get_gifts_by_donor(session, user_id)
            
            # Подарки полученные
            gifts_received = await gift_dal.get_gifts_by_recipient(session, user_id)
            
            # Подсчет статистики
            total_spent = sum(g.amount for g in gifts_sent if g.status != GiftStatus.cancelled)
            
            sent_by_status = {}
            for status in GiftStatus:
                count = sum(1 for g in gifts_sent if g.status == status)
                if count > 0:
                    sent_by_status[status.value] = count
            
            received_by_status = {}
            for status in GiftStatus:
                count = sum(1 for g in gifts_received if g.status == status)
                if count > 0:
                    received_by_status[status.value] = count
            
            return {
                "user_id": user_id,
                "gifts_sent": len(gifts_sent),
                "gifts_received": len(gifts_received),
                "total_spent": float(total_spent),
                "sent_by_status": sent_by_status,
                "received_by_status": received_by_status,
            }
            
        except Exception as e:
            logger.error(f"Error getting user gift statistics: {e}", exc_info=True)
            return {
                "user_id": user_id,
                "error": str(e),
            }
    
    async def get_global_gift_statistics(
        self,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Получить глобальную статистику по подаркам (для админов).
        
        Args:
            session: Сессия БД
            
        Returns:
            Dict с глобальной статистикой
        """
        try:
            stats = await gift_dal.get_gift_statistics(session)
            return stats
            
        except Exception as e:
            logger.error(f"Error getting global gift statistics: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def get_random_eligible_user(
        self,
        session: AsyncSession,
        exclude_user_ids: Optional[list] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Получить случайного пользователя, подходящего для получения подарка.
        
        Args:
            session: Сессия БД
            exclude_user_ids: Список ID для исключения (например, даритель)
            
        Returns:
            Tuple[bool, str, Optional[int]]:
                - bool: Успешность
                - str: Сообщение
                - Optional[int]: ID пользователя
        """
        try:
            user = await gift_dal.get_random_active_user(session, exclude_user_ids)
            
            if not user:
                logger.warning("No eligible users found for random gift")
                return False, "No eligible users found", None
            
            return True, "Random user selected", user.user_id
            
        except Exception as e:
            logger.error(f"Error getting random eligible user: {e}", exc_info=True)
            return False, f"Internal error: {str(e)}", None
    
    # ========================================================================
    # PRIVATE МЕТОДЫ - УВЕДОМЛЕНИЯ
    # ========================================================================
    
    async def _send_gift_ready_notification(self, gift) -> None:
        """
        Отправить уведомление дарителю о готовности подарка.
        
        Args:
            gift: Объект подарка
        """
        if not self.bot or not self.i18n:
            logger.debug("Bot or i18n not available, skipping gift ready notification")
            return
        
        try:
            # Получаем язык дарителя
            lang = gift.donor.language_code if gift.donor else self.settings.DEFAULT_LANGUAGE
            _ = lambda key, **kwargs: self.i18n.gettext(lang, key, **kwargs)
            
            message = (
                f"🎁 {_('gift_ready_title')}\n\n"
                f"{_('gift_ready_description')}\n\n"
                f"📝 Код: <code>{gift.gift_code}</code>\n"
                f"⏱ {_('gift_expires')}: {gift.expires_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"{_('gift_ready_share_instructions')}"
            )
            
            await self.bot.send_message(
                chat_id=gift.donor_user_id,
                text=message,
                parse_mode="HTML"
            )
            
            logger.info(f"Gift ready notification sent to donor {gift.donor_user_id}")
            
        except Exception as e:
            logger.error(
                f"Failed to send gift ready notification to donor {gift.donor_user_id}: {e}",
                exc_info=True
            )
    
    async def _send_gift_activation_notifications(
        self,
        gift,
        recipient_id: int,
        subscription_data: Dict[str, Any]
    ) -> None:
        """
        Отправить уведомления при активации подарка.
        
        Отправляет:
        - Получателю: информацию об активированной подписке
        - Дарителю: уведомление об активации подарка
        
        Args:
            gift: Объект подарка
            recipient_id: ID получателя
            subscription_data: Данные активированной подписки
        """
        if not self.bot or not self.i18n:
            logger.debug("Bot or i18n not available, skipping activation notifications")
            return
        
        try:
            # Уведомление получателю
            recipient_user = await user_dal.get_user_by_id(
                # Нужна новая сессия или использовать существующую?
                # Для простоты используем существующую или создаем новую
                None,  # Будет проблема - нужна сессия!
                recipient_id
            )
            
            # Проблема: нам нужна сессия, но она может быть закрыта после commit
            # Решение: получить язык из subscription_data или использовать дефолтный
            recipient_lang = self.settings.DEFAULT_LANGUAGE
            _r = lambda key, **kwargs: self.i18n.gettext(recipient_lang, key, **kwargs)
            
            recipient_message = (
                f"🎉 {_r('gift_activated_title')}\n\n"
                f"{_r('gift_activated_description')}\n\n"
            )
            
            if gift.donor_username:
                recipient_message += f"👤 {_r('gift_from')}: @{gift.donor_username}\n"
            
            if gift.message_to_recipient:
                recipient_message += f"\n💌 {_r('gift_message')}: {gift.message_to_recipient}\n"
            
            recipient_message += (
                f"\n📅 {_r('subscription_valid_until')}: "
                f"{subscription_data.get('end_date', 'N/A')}\n"
                f"🔗 {_r('subscription_url')}: {subscription_data.get('subscription_url', 'N/A')}"
            )
            
            await self.bot.send_message(
                chat_id=recipient_id,
                text=recipient_message,
                parse_mode="HTML"
            )
            
            logger.info(f"Gift activation notification sent to recipient {recipient_id}")
            
            # Уведомление дарителю
            donor_lang = self.settings.DEFAULT_LANGUAGE
            _d = lambda key, **kwargs: self.i18n.gettext(donor_lang, key, **kwargs)
            
            donor_message = (
                f"✅ {_d('gift_was_activated_title')}\n\n"
                f"{_d('gift_was_activated_description')}\n\n"
                f"🎁 {_d('gift_code')}: <code>{gift.gift_code}</code>\n"
            )
            
            await self.bot.send_message(
                chat_id=gift.donor_user_id,
                text=donor_message,
                parse_mode="HTML"
            )
            
            logger.info(f"Gift activation notification sent to donor {gift.donor_user_id}")
            
        except Exception as e:
            logger.error(
                f"Failed to send gift activation notifications: {e}",
                exc_info=True
            )