import logging
from typing import Optional
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import Settings
from bot.keyboards.inline.user_keyboards import (
    get_tariffs_list_keyboard,
    get_tariff_detail_keyboard,
    get_tariff_payment_options_keyboard,
    get_back_to_main_menu_markup,
    get_subscription_options_keyboard,
)
from bot.states.user_states import TariffSelectionStates
from bot.services.tariff_service import TariffService
from bot.services.balance_service import BalanceService
from bot.middlewares.i18n import JsonI18n
from db.dal import user_dal

router = Router(name="tariff_selection_router")


def format_traffic(traffic_bytes: Optional[int], i18n: JsonI18n, lang: str) -> str:
    """Форматирует трафик в читаемый вид"""
    _ = lambda key, **kwargs: i18n.gettext(lang, key, **kwargs)
    
    if traffic_bytes is None:
        return _("traffic_unlimited")
    
    traffic_gb = traffic_bytes / (1024 ** 3)
    if traffic_gb >= 1000:
        traffic_tb = traffic_gb / 1024
        return f"{traffic_tb:.1f} TB"
    return f"{traffic_gb:.0f} GB"


def format_speed(speed_mbps: Optional[float]) -> str:
    """Форматирует скорость"""
    if speed_mbps is None:
        return "∞"
    if speed_mbps >= 1000:
        return f"{speed_mbps/1000:.1f} Gbps"
    return f"{speed_mbps:.0f} Mbps"


@router.callback_query(F.data == "main_action:subscribe")
async def show_tariffs_list(
    callback: types.CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    i18n_data: dict,
    tariff_service: TariffService,
):
    """Отображает список доступных тарифов"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(lang=current_lang, key=key, **kwargs)
    
    try:
        # Получаем активные тарифы
        tariffs = await tariff_service.get_active_tariffs(session)
        
        if not tariffs:
            # Fallback к старой системе с месяцами
            text = _("select_subscription_period")
            keyboard = get_subscription_options_keyboard(
                settings.subscription_options,
                settings.DEFAULT_CURRENCY_SYMBOL,
                current_lang,
                i18n
            )
            
            try:
                await callback.message.edit_text(text, reply_markup=keyboard)
            except Exception:
                await callback.message.answer(text, reply_markup=keyboard)
            
            await callback.answer()
            return
        
        # Показываем список тарифов
        text = _("tariffs_list_title")
        keyboard = get_tariffs_list_keyboard(tariffs, current_lang, i18n)
        
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logging.warning(f"Failed to edit message: {e}")
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error showing tariffs list: {e}", exc_info=True)
        await callback.answer(_("error_occurred_try_again"), show_alert=True)


@router.callback_query(F.data.startswith("tariff:view:"))
async def show_tariff_details(
    callback: types.CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    i18n_data: dict,
    tariff_service: TariffService,
):
    """Показывает детальную информацию о тарифе"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(lang=current_lang, key=key, **kwargs)
    
    try:
        tariff_id = int(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        logging.error(f"Invalid tariff_id in callback: {callback.data}")
        await callback.answer(_("error_try_again"), show_alert=True)
        return
    
    try:
        # Получаем информацию о тарифе
        user_id = callback.from_user.id
        tariff = await tariff_service.get_tariff_by_id(session, tariff_id)
        
        if not tariff:
            await callback.answer(_("tariff_not_found"), show_alert=True)
            return
        
        # Рассчитываем цену с учетом скидок пользователя (без промокода пока)
        price_calc = await tariff_service.calculate_final_price(
            session,
            user_id,
            tariff_id
        )
        
        # Получаем баланс пользователя
        user = await user_dal.get_user_by_id(session, user_id)
        user_balance = user.balance if user else 0.0
        
        # Формируем текст с детальной информацией о тарифе
        lines = [
            f"📦 <b>{tariff.name}</b>\n",
        ]
        
        if tariff.description:
            lines.append(f"{tariff.description}\n")
        
        lines.append(f"💰 <b>{_('tariff_price')}:</b>")
        
        # Показываем базовую цену
        if price_calc["discount_applied"] > 0:
            lines.append(f"  <s>{price_calc['base_price']:.2f} {tariff.currency}</s>")
            lines.append(f"  <b>{price_calc['final_price']:.2f} {tariff.currency}</b>")
            lines.append(f"  🎁 {_('tariff_your_discount')}: {price_calc['discount_percentage']}%")
        else:
            lines.append(f"  <b>{price_calc['final_price']:.2f} {tariff.currency}</b>")
        
        lines.append(f"\n⏱ <b>{_('tariff_duration')}:</b> {tariff.duration_days} {_('days')}")
        lines.append(f"📊 <b>{_('tariff_traffic')}:</b> {format_traffic(tariff.traffic_limit_bytes, i18n, current_lang)}")
        
        if tariff.device_limit:
            lines.append(f"📱 <b>{_('tariff_devices')}:</b> {tariff.device_limit}")
        
        if tariff.speed_limit_mbps:
            lines.append(f"⚡ <b>{_('tariff_speed')}:</b> {format_speed(tariff.speed_limit_mbps)}")
        
        # Показываем информацию о возможности использования баланса
        final_price = price_calc["final_price"]
        if user_balance > 0:
            lines.append(f"\n💳 <b>{_('your_balance')}:</b> {user_balance:.2f} {tariff.currency}")
            
            if user_balance >= final_price:
                lines.append(f"✅ {_('tariff_can_pay_from_balance')}")
            else:
                to_pay = final_price - user_balance
                lines.append(f"⚠️ {_('tariff_need_topup')}: {to_pay:.2f} {tariff.currency}")
        
        text = "\n".join(lines)
        
        # Клавиатура с действиями
        keyboard = get_tariff_detail_keyboard(
            tariff_id,
            price_calc["final_price"],
            user_balance,
            current_lang,
            i18n
        )
        
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logging.warning(f"Failed to edit message: {e}")
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error showing tariff details: {e}", exc_info=True)
        await callback.answer(_("error_occurred_try_again"), show_alert=True)


@router.callback_query(F.data.startswith("tariff:buy:"))
async def start_tariff_purchase(
    callback: types.CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    i18n_data: dict,
    tariff_service: TariffService,
    state: FSMContext,
):
    """Начинает процесс покупки тарифа (с возможностью ввода промокода)"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(lang=current_lang, key=key, **kwargs)
    
    try:
        tariff_id = int(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        logging.error(f"Invalid tariff_id in callback: {callback.data}")
        await callback.answer(_("error_try_again"), show_alert=True)
        return
    
    try:
        user_id = callback.from_user.id
        tariff = await tariff_service.get_tariff_by_id(session, tariff_id)
        
        if not tariff:
            await callback.answer(_("tariff_not_found"), show_alert=True)
            return
        
        # Сохраняем tariff_id в состояние для дальнейшего использования
        await state.update_data(tariff_id=tariff_id, promo_code=None)
        
        # Показываем опции: применить промокод или продолжить к оплате
        text = _("tariff_purchase_options", tariff_name=tariff.name)
        
        keyboard = get_tariff_payment_options_keyboard(
            tariff_id,
            current_lang,
            i18n,
            show_promo=True
        )
        
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logging.warning(f"Failed to edit message: {e}")
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error starting tariff purchase: {e}", exc_info=True)
        await callback.answer(_("error_occurred_try_again"), show_alert=True)


@router.callback_query(F.data.startswith("tariff:apply_promo:"))
async def request_promo_code(
    callback: types.CallbackQuery,
    settings: Settings,
    i18n_data: dict,
    state: FSMContext,
):
    """Запрашивает ввод промокода"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(lang=current_lang, key=key, **kwargs)
    
    try:
        tariff_id = int(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        logging.error(f"Invalid tariff_id in callback: {callback.data}")
        await callback.answer(_("error_try_again"), show_alert=True)
        return
    
    await state.update_data(tariff_id=tariff_id)
    await state.set_state(TariffSelectionStates.waiting_for_promo_code)
    
    text = _("tariff_enter_promo_code")
    
    # Клавиатура с кнопкой отмены
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=_("cancel_button"),
            callback_data=f"tariff:view:{tariff_id}"
        )]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logging.warning(f"Failed to edit message: {e}")
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


@router.message(TariffSelectionStates.waiting_for_promo_code)
async def process_promo_code(
    message: types.Message,
    session: AsyncSession,
    settings: Settings,
    i18n_data: dict,
    tariff_service: TariffService,
    state: FSMContext,
):
    """Обрабатывает введенный промокод и показывает обновленную цену"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        return
    
    _ = lambda key, **kwargs: i18n.gettext(lang=current_lang, key=key, **kwargs)
    
    user_data = await state.get_data()
    tariff_id = user_data.get("tariff_id")
    
    if not tariff_id:
        await message.answer(_("error_occurred_try_again"))
        await state.clear()
        return
    
    promo_code = message.text.strip()
    user_id = message.from_user.id
    
    try:
        # Рассчитываем цену с промокодом
        price_calc = await tariff_service.calculate_final_price(
            session,
            user_id,
            tariff_id,
            promo_code=promo_code
        )
        
        tariff = await tariff_service.get_tariff_by_id(session, tariff_id)
        if not tariff:
            await message.answer(_("tariff_not_found"))
            await state.clear()
            return
        
        # Сохраняем промокод в состояние
        await state.update_data(promo_code=promo_code if price_calc["promo_applied"] > 0 else None)
        await state.clear()
        
        # Формируем сообщение с результатом
        lines = [
            f"📦 <b>{tariff.name}</b>\n",
        ]
        
        # Показываем расчет цены
        lines.append(f"💰 <b>{_('price_calculation')}:</b>")
        lines.append(f"  {_('base_price')}: {price_calc['base_price']:.2f} {tariff.currency}")
        
        for detail in price_calc["details"]:
            lines.append(f"  {detail}")
        
        lines.append(f"\n<b>{_('final_price')}:</b> {price_calc['final_price']:.2f} {tariff.currency}")
        
        # Информация об экономии
        total_discount = price_calc["discount_applied"] + price_calc["promo_applied"]
        if total_discount > 0:
            lines.append(f"💚 <b>{_('you_save')}:</b> {total_discount:.2f} {tariff.currency}")
        
        text = "\n".join(lines)
        
        # Клавиатура для продолжения к оплате
        keyboard = get_tariff_payment_options_keyboard(
            tariff_id,
            current_lang,
            i18n,
            show_promo=False,
            has_promo=bool(promo_code and price_calc["promo_applied"] > 0)
        )
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logging.error(f"Error processing promo code: {e}", exc_info=True)
        await message.answer(_("error_occurred_try_again"))
        await state.clear()


@router.callback_query(F.data.startswith("tariff:pay:"))
async def proceed_to_payment(
    callback: types.CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    i18n_data: dict,
    tariff_service: TariffService,
    balance_service: BalanceService,
    state: FSMContext,
):
    """Переходит к выбору способа оплаты с учетом баланса"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(lang=current_lang, key=key, **kwargs)
    
    try:
        tariff_id = int(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        logging.error(f"Invalid tariff_id in callback: {callback.data}")
        await callback.answer(_("error_try_again"), show_alert=True)
        return
    
    try:
        user_id = callback.from_user.id
        
        # Получаем промокод из состояния (если был введен)
        user_data = await state.get_data()
        promo_code = user_data.get("promo_code")
        
        # Рассчитываем финальную цену
        price_calc = await tariff_service.calculate_final_price(
            session,
            user_id,
            tariff_id,
            promo_code=promo_code
        )
        
        tariff = await tariff_service.get_tariff_by_id(session, tariff_id)
        if not tariff:
            await callback.answer(_("tariff_not_found"), show_alert=True)
            return
        
        final_price = price_calc["final_price"]
        
        # Получаем баланс
        user = await user_dal.get_user_by_id(session, user_id)
        user_balance = user.balance if user else 0.0
        
        # Определяем логику оплаты
        if user_balance >= final_price:
            # Достаточно баланса - оплата полностью с баланса
            text = _("tariff_pay_from_balance_confirm",
                    tariff_name=tariff.name,
                    price=final_price,
                    currency=tariff.currency,
                    balance=user_balance)
            
            # TODO: Реализовать оплату с баланса
            # Пока показываем информацию
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=_("confirm_payment_button"),
                    callback_data=f"tariff:confirm_balance:{tariff_id}"
                )],
                [InlineKeyboardButton(
                    text=_("cancel_button"),
                    callback_data=f"tariff:view:{tariff_id}"
                )]
            ])
            
        else:
            # Недостаточно баланса - нужна доплата через платежную систему
            to_pay = final_price - user_balance
            
            text = _("tariff_partial_payment_info",
                    tariff_name=tariff.name,
                    total=final_price,
                    from_balance=user_balance,
                    to_pay=to_pay,
                    currency=tariff.currency)
            
            # Показываем способы оплаты для доплаты
            # Перенаправляем на старую систему с передачей tariff_id
            # Пока используем месяцы как proxy
            months = tariff.duration_days // 30 if tariff.duration_days >= 30 else 1
            
            from bot.keyboards.inline.user_keyboards import get_payment_method_keyboard
            
            keyboard = get_payment_method_keyboard(
                months,
                to_pay,
                settings.tribute_payment_links.get(months),
                settings.stars_subscription_options.get(months),
                tariff.currency,
                current_lang,
                i18n,
                settings
            )
        
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logging.warning(f"Failed to edit message: {e}")
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error proceeding to payment: {e}", exc_info=True)
        await callback.answer(_("error_occurred_try_again"), show_alert=True)


@router.callback_query(F.data.startswith("tariff:confirm_balance:"))
async def confirm_balance_payment(
    callback: types.CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    i18n_data: dict,
    tariff_service: TariffService,
    balance_service: BalanceService,
    state: FSMContext,
):
    """Подтверждает оплату тарифа с баланса"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(lang=current_lang, key=key, **kwargs)
    
    try:
        tariff_id = int(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        logging.error(f"Invalid tariff_id in callback: {callback.data}")
        await callback.answer(_("error_try_again"), show_alert=True)
        return
    
    try:
        user_id = callback.from_user.id
        
        # Получаем промокод из состояния (если был введен)
        user_data = await state.get_data()
        promo_code = user_data.get("promo_code")
        
        # Рассчитываем финальную цену
        price_calc = await tariff_service.calculate_final_price(
            session,
            user_id,
            tariff_id,
            promo_code=promo_code
        )
        
        if price_calc.get("error"):
            await callback.answer(price_calc["error"], show_alert=True)
            return
        
        tariff = await tariff_service.get_tariff_by_id(session, tariff_id)
        if not tariff:
            await callback.answer(_("tariff_not_found"), show_alert=True)
            return
        
        final_price = price_calc["final_price"]
        
        # Проверяем баланс
        user = await user_dal.get_user_by_id(session, user_id)
        if not user:
            await callback.answer(_("error_user_not_found"), show_alert=True)
            return
        
        if user.balance < final_price:
            await callback.answer(_("insufficient_balance"), show_alert=True)
            return
        
        # Списываем с баланса
        withdrawal_success = await balance_service.withdraw_from_balance(
            session,
            user_id,
            final_price,
            tariff.currency,
            description=_("balance_withdrawal_for_tariff", tariff_name=tariff.name)
        )
        
        if not withdrawal_success:
            await callback.answer(_("error_occurred_try_again"), show_alert=True)
            return
        
        # Создаем платеж с типом balance
        from db.dal import payment_dal
        payment_data = {
            "user_id": user_id,
            "amount": final_price,
            "currency": tariff.currency,
            "status": "succeeded",
            "description": _("payment_description_tariff", tariff_name=tariff.name, days=tariff.duration_days),
            "subscription_duration_months": 0,  # Используем duration_days из тарифа
            "tariff_id": tariff_id,
            "provider": "balance",
        }
        
        # Добавляем promo_code_id если промокод был применен
        if price_calc.get("promo_details") and price_calc["promo_details"].get("promo_code_id"):
            payment_data["promo_code_id"] = price_calc["promo_details"]["promo_code_id"]
        
        try:
            payment_record = await payment_dal.create_payment_record(session, payment_data)
            await session.commit()
            logging.info(f"Balance payment {payment_record.payment_id} created for user {user_id}")
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to create balance payment: {e}", exc_info=True)
            # Возвращаем деньги на баланс
            await balance_service.add_to_balance(
                session,
                user_id,
                final_price,
                tariff.currency,
                description=_("balance_refund_failed_payment")
            )
            await session.commit()
            await callback.answer(_("error_creating_payment_record"), show_alert=True)
            return
        
        # Активируем подписку
        from bot.services.subscription_service import SubscriptionService
        from bot.services.panel_api_service import PanelApiService
        
        # Получаем сервисы через dependency injection
        panel_service = PanelApiService(settings)
        subscription_service = SubscriptionService(
            settings=settings,
            panel_service=panel_service,
            bot=None,
            i18n=i18n
        )
        
        months = tariff.duration_days // 30 if tariff.duration_days >= 30 else 1
        
        activation_result = await subscription_service.activate_subscription(
            session=session,
            user_id=user_id,
            months=months,
            payment_amount=final_price,
            payment_db_id=payment_record.payment_id,
            promo_code_id_from_payment=payment_data.get("promo_code_id"),
            provider="balance",
            tariff_id=tariff_id,
        )
        
        if not activation_result:
            await callback.answer(_("error_occurred_try_again"), show_alert=True)
            return
        
        await state.clear()
        
        # Формируем сообщение об успешной оплате
        end_date_str = activation_result["end_date"].strftime("%Y-%m-%d")
        config_link = activation_result.get("subscription_url") or _("config_link_not_available")
        
        success_text = _("tariff_payment_success",
                        tariff_name=tariff.name,
                        days=tariff.duration_days,
                        end_date=end_date_str,
                        config_link=config_link)
        
        # Добавляем информацию об экономии
        total_discount = price_calc["discount_applied"] + price_calc["promo_applied"]
        if total_discount > 0:
            success_text += f"\n\n💚 {_('you_save')}: {total_discount:.2f} {tariff.currency}"
        
        from bot.keyboards.inline.user_keyboards import get_connect_and_main_keyboard
        keyboard = get_connect_and_main_keyboard(
            current_lang,
            i18n,
            settings,
            config_link if config_link != _("config_link_not_available") else None,
            preserve_message=False
        )
        
        try:
            await callback.message.edit_text(success_text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logging.warning(f"Failed to edit message: {e}")
            await callback.message.answer(success_text, reply_markup=keyboard, parse_mode="HTML")
        
        await callback.answer(_("payment_successful_alert"), show_alert=True)
        
    except Exception as e:
        logging.error(f"Error confirming balance payment: {e}", exc_info=True)
        await callback.answer(_("error_occurred_try_again"), show_alert=True)