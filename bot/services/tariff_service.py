import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from db.dal import tariff_dal, promo_code_dal
from db.dal.discount_dal import get_best_user_discount
from db.models import Tariff, PromoCode


class TariffService:
    """Сервис для работы с тарифами и расчетом цен"""

    async def get_active_tariffs(self, session: AsyncSession) -> List[Tariff]:
        """
        Получить список всех активных тарифов.
        
        Args:
            session: Сессия БД
            
        Returns:
            List[Tariff]: Список активных тарифов, отсортированных по цене
        """
        tariffs = await tariff_dal.get_active_tariffs(session)
        logging.debug(f"Retrieved {len(tariffs)} active tariffs")
        return tariffs

    async def get_tariff_by_id(
        self,
        session: AsyncSession,
        tariff_id: int
    ) -> Optional[Tariff]:
        """
        Получить тариф по ID.
        
        Args:
            session: Сессия БД
            tariff_id: ID тарифа
            
        Returns:
            Optional[Tariff]: Тариф или None, если не найден
        """
        tariff = await tariff_dal.get_tariff_by_id(session, tariff_id)
        if not tariff:
            logging.warning(f"Tariff {tariff_id} not found")
        return tariff

    async def calculate_final_price(
        self,
        session: AsyncSession,
        user_id: int,
        tariff_id: int,
        promo_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Рассчитать финальную цену тарифа с учетом всех скидок.
        
        Порядок применения скидок:
        1. Базовая цена тарифа
        2. Персональная скидка пользователя (процент от базовой цены)
        3. Промокод (процент или фиксированная сумма от цены после персональной скидки)
        
        Args:
            session: Сессия БД
            user_id: ID пользователя
            tariff_id: ID тарифа
            promo_code: Код промокода (опционально)
            
        Returns:
            Dict с ключами:
                - base_price: Базовая цена тарифа
                - discount_applied: Сумма персональной скидки
                - discount_percentage: Процент персональной скидки
                - promo_applied: Сумма скидки по промокоду
                - promo_details: Детали промокода (если применен)
                - final_price: Итоговая цена
                - details: Список примененных скидок (описание)
                - currency: Валюта
                - error: Сообщение об ошибке (если есть)
        """
        result: Dict[str, Any] = {
            "base_price": 0.0,
            "discount_applied": 0.0,
            "discount_percentage": 0.0,
            "promo_applied": 0.0,
            "promo_details": None,
            "final_price": 0.0,
            "details": [],
            "currency": "RUB",
            "error": None,
        }

        # Получаем тариф
        tariff = await self.get_tariff_by_id(session, tariff_id)
        if not tariff:
            result["error"] = f"Tariff {tariff_id} not found"
            logging.error(result["error"])
            return result

        if not tariff.is_active:
            result["error"] = f"Tariff {tariff_id} is not active"
            logging.warning(result["error"])
            return result

        base_price = tariff.price
        result["base_price"] = base_price
        result["currency"] = tariff.currency
        current_price = base_price

        # 1. Применяем персональную скидку пользователя
        user_discount = await get_best_user_discount(session, user_id, tariff_id)
        if user_discount and user_discount.discount_percentage > 0:
            discount_amount = round(base_price * (user_discount.discount_percentage / 100.0), 2)
            result["discount_applied"] = discount_amount
            result["discount_percentage"] = user_discount.discount_percentage
            current_price -= discount_amount
            
            tariff_info = f" для тарифа {tariff_id}" if user_discount.tariff_id else " (общая)"
            result["details"].append(
                f"Персональная скидка {user_discount.discount_percentage}%{tariff_info}: "
                f"-{discount_amount} {tariff.currency}"
            )
            logging.info(
                f"Applied personal discount for user {user_id}: "
                f"{user_discount.discount_percentage}% = {discount_amount} {tariff.currency}"
            )

        # 2. Применяем промокод (если указан)
        if promo_code:
            promo_result = await self._apply_promo_code(
                session=session,
                promo_code=promo_code,
                user_id=user_id,
                tariff_id=tariff_id,
                current_price=current_price,
                currency=tariff.currency
            )
            
            if promo_result["applied"]:
                result["promo_applied"] = promo_result["discount_amount"]
                result["promo_details"] = promo_result["promo_details"]
                current_price -= promo_result["discount_amount"]
                result["details"].append(promo_result["description"])
            elif promo_result["error"]:
                result["details"].append(f"Промокод не применен: {promo_result['error']}")
                logging.warning(f"Promo code '{promo_code}' not applied: {promo_result['error']}")

        # Финальная цена не может быть отрицательной
        result["final_price"] = max(0.0, round(current_price, 2))

        logging.info(
            f"Price calculation for user {user_id}, tariff {tariff_id}: "
            f"base={base_price}, personal_discount={result['discount_applied']}, "
            f"promo_discount={result['promo_applied']}, final={result['final_price']} {result['currency']}"
        )

        return result

    async def _apply_promo_code(
        self,
        session: AsyncSession,
        promo_code: str,
        user_id: int,
        tariff_id: int,
        current_price: float,
        currency: str
    ) -> Dict[str, Any]:
        """
        Применить промокод к текущей цене.
        
        Returns:
            Dict с ключами:
                - applied: bool - применен ли промокод
                - discount_amount: float - сумма скидки
                - promo_details: Dict - детали промокода
                - description: str - описание скидки
                - error: Optional[str] - ошибка, если не применен
        """
        result = {
            "applied": False,
            "discount_amount": 0.0,
            "promo_details": None,
            "description": "",
            "error": None,
        }

        # Получаем промокод
        promo = await promo_code_dal.get_promo_code_by_code(session, promo_code)
        
        if not promo:
            result["error"] = "Промокод не найден"
            return result

        # Проверяем активность промокода
        if not promo.is_active:
            result["error"] = "Промокод не активен"
            return result

        # Проверяем лимит активаций
        if promo.current_activations >= promo.max_activations:
            result["error"] = "Промокод исчерпан"
            return result

        # Проверяем срок действия
        if promo.valid_until:
            from datetime import datetime, timezone
            if promo.valid_until < datetime.now(timezone.utc):
                result["error"] = "Срок действия промокода истек"
                return result

        # Проверяем, активировал ли пользователь этот промокод ранее
        existing_activation = await promo_code_dal.get_user_activation_for_promo(
            session, promo.promo_code_id, user_id
        )
        if existing_activation:
            result["error"] = "Промокод уже использован"
            return result

        # Проверяем применимость к тарифу
        if promo.applicable_tariff_ids:
            if tariff_id not in promo.applicable_tariff_ids:
                result["error"] = f"Промокод не применим к данному тарифу"
                return result

        # Проверяем минимальную сумму покупки
        if promo.min_purchase_amount and current_price < promo.min_purchase_amount:
            result["error"] = (
                f"Минимальная сумма для применения промокода: "
                f"{promo.min_purchase_amount} {currency}"
            )
            return result

        # Промокод типа 'discount' - применяется к цене
        if promo.type == "discount" and promo.value:
            # Определяем тип скидки по значению value
            # Если value <= 100, считаем процентной скидкой
            # Если value > 100, считаем фиксированной суммой
            
            if promo.value <= 100:
                # Процентная скидка
                discount_amount = round(current_price * (promo.value / 100.0), 2)
                result["description"] = (
                    f"Промокод '{promo.code}' (скидка {promo.value}%): "
                    f"-{discount_amount} {currency}"
                )
            else:
                # Фиксированная скидка
                discount_amount = min(promo.value, current_price)  # Не больше текущей цены
                result["description"] = (
                    f"Промокод '{promo.code}' (скидка {promo.value} {currency}): "
                    f"-{discount_amount} {currency}"
                )
            
            result["applied"] = True
            result["discount_amount"] = discount_amount
            result["promo_details"] = {
                "code": promo.code,
                "type": promo.type,
                "value": promo.value,
                "promo_code_id": promo.promo_code_id,
            }
            
            logging.info(
                f"Applied promo code '{promo.code}' (type={promo.type}, value={promo.value}) "
                f"for user {user_id}: discount={discount_amount} {currency}"
            )
        
        # Промокод типа 'bonus_days' - не влияет на цену, только на продолжительность
        elif promo.type == "bonus_days":
            result["applied"] = True
            result["discount_amount"] = 0.0
            result["promo_details"] = {
                "code": promo.code,
                "type": promo.type,
                "bonus_days": promo.bonus_days,
                "promo_code_id": promo.promo_code_id,
            }
            result["description"] = (
                f"Промокод '{promo.code}': +{promo.bonus_days} дней к подписке"
            )
            logging.info(
                f"Applied promo code '{promo.code}' (type=bonus_days, days={promo.bonus_days}) "
                f"for user {user_id}"
            )
        
        # Промокод типа 'balance' - начисление на баланс, не влияет на цену подписки
        elif promo.type == "balance":
            result["applied"] = True
            result["discount_amount"] = 0.0
            result["promo_details"] = {
                "code": promo.code,
                "type": promo.type,
                "value": promo.value,
                "promo_code_id": promo.promo_code_id,
            }
            result["description"] = (
                f"Промокод '{promo.code}': +{promo.value} {currency} на баланс"
            )
            logging.info(
                f"Applied promo code '{promo.code}' (type=balance, value={promo.value}) "
                f"for user {user_id}"
            )
        else:
            result["error"] = f"Неизвестный тип промокода: {promo.type}"

        return result

    async def get_tariff_info(
        self,
        session: AsyncSession,
        tariff_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о тарифе в виде словаря.
        
        Args:
            session: Сессия БД
            tariff_id: ID тарифа
            
        Returns:
            Optional[Dict]: Информация о тарифе или None
        """
        tariff = await self.get_tariff_by_id(session, tariff_id)
        if not tariff:
            return None

        return {
            "id": tariff.id,
            "name": tariff.name,
            "description": tariff.description,
            "price": tariff.price,
            "currency": tariff.currency,
            "duration_days": tariff.duration_days,
            "traffic_limit_bytes": tariff.traffic_limit_bytes,
            "device_limit": tariff.device_limit,
            "speed_limit_mbps": tariff.speed_limit_mbps,
            "is_active": tariff.is_active,
            "is_default": tariff.is_default,
        }

    async def get_all_tariffs_info(
        self,
        session: AsyncSession,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Получить информацию о всех тарифах в виде списка словарей.
        
        Args:
            session: Сессия БД
            active_only: Возвращать только активные тарифы
            
        Returns:
            List[Dict]: Список тарифов
        """
        if active_only:
            tariffs = await self.get_active_tariffs(session)
        else:
            tariffs = await tariff_dal.get_all_tariffs(session)

        result = []
        for tariff in tariffs:
            result.append({
                "id": tariff.id,
                "name": tariff.name,
                "description": tariff.description,
                "price": tariff.price,
                "currency": tariff.currency,
                "duration_days": tariff.duration_days,
                "traffic_limit_bytes": tariff.traffic_limit_bytes,
                "device_limit": tariff.device_limit,
                "speed_limit_mbps": tariff.speed_limit_mbps,
                "is_active": tariff.is_active,
                "is_default": tariff.is_default,
            })

        return result