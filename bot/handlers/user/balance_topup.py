import logging
from datetime import datetime
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import Settings
from bot.keyboards.inline.user_keyboards import (
    get_balance_topup_amount_keyboard,
    get_balance_topup_payment_methods_keyboard,
    get_payment_url_keyboard,
    get_back_to_main_menu_markup,
)
from bot.states.user_states import BalanceTopupStates
from bot.services.yookassa_service import YooKassaService
from bot.services.freekassa_service import FreeKassaService
from bot.services.crypto_pay_service import CryptoPayService
from bot.services.stars_service import StarsService
from bot.services.balance_service import BalanceService
from bot.middlewares.i18n import JsonI18n
from db.dal import payment_dal

router = Router(name="balance_topup_router")

# Константы для валидации
MIN_TOPUP_AMOUNT = 50
MAX_TOPUP_AMOUNT = 50000


@router.callback_query(F.data == "profile_action:top_up_balance")
async def start_balance_topup(
    callback: types.CallbackQuery,
    settings: Settings,
    i18n_data: dict,
):
    """Начало процесса пополнения баланса - выбор суммы"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    text = _("balance_topup_select_amount")
    keyboard = get_balance_topup_amount_keyboard(current_lang, i18n)
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logging.warning(f"Failed to edit message for balance topup: {e}")
        try:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            pass
    
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "balance_topup:select_amount")
async def select_amount_again(
    callback: types.CallbackQuery,
    settings: Settings,
    i18n_data: dict,
    state: FSMContext,
):
    """Возврат к выбору суммы"""
    await state.clear()
    await start_balance_topup(callback, settings, i18n_data)


@router.callback_query(F.data.startswith("balance_topup:amount:"))
async def select_fixed_amount(
    callback: types.CallbackQuery,
    settings: Settings,
    i18n_data: dict,
):
    """Обработка выбора фиксированной суммы"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        amount = float(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        logging.error(f"Invalid amount in callback_data: {callback.data}")
        await callback.answer(_("error_try_again"), show_alert=True)
        return
    
    # Валидация суммы
    if amount < MIN_TOPUP_AMOUNT or amount > MAX_TOPUP_AMOUNT:
        await callback.answer(
            _("balance_topup_amount_invalid", min=MIN_TOPUP_AMOUNT, max=MAX_TOPUP_AMOUNT),
            show_alert=True
        )
        return
    
    text = _("balance_topup_select_payment_method", amount=amount)
    keyboard = get_balance_topup_payment_methods_keyboard(amount, current_lang, i18n, settings)
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logging.warning(f"Failed to edit message: {e}")
        try:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            pass
    
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "balance_topup:custom_amount")
async def request_custom_amount(
    callback: types.CallbackQuery,
    settings: Settings,
    i18n_data: dict,
    state: FSMContext,
):
    """Запрос пользовательской суммы"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    text = _("balance_topup_enter_custom_amount", min=MIN_TOPUP_AMOUNT, max=MAX_TOPUP_AMOUNT)
    
    # Клавиатура с кнопкой отмены
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=_("cancel_button"),
            callback_data="balance_topup:select_amount"
        )]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=builder, parse_mode="HTML")
    except Exception as e:
        logging.warning(f"Failed to edit message: {e}")
        try:
            await callback.message.answer(text, reply_markup=builder, parse_mode="HTML")
        except Exception:
            pass
    
    await state.set_state(BalanceTopupStates.waiting_for_custom_amount)
    
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(BalanceTopupStates.waiting_for_custom_amount)
async def process_custom_amount(
    message: types.Message,
    settings: Settings,
    i18n_data: dict,
    state: FSMContext,
):
    """Обработка введенной пользовательской суммы"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        return
    
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        amount = float(message.text.replace(",", ".").strip())
    except (ValueError, AttributeError):
        await message.answer(
            _("balance_topup_amount_invalid_format"),
            parse_mode="HTML"
        )
        return
    
    # Валидация суммы
    if amount < MIN_TOPUP_AMOUNT or amount > MAX_TOPUP_AMOUNT:
        await message.answer(
            _("balance_topup_amount_invalid", min=MIN_TOPUP_AMOUNT, max=MAX_TOPUP_AMOUNT),
            parse_mode="HTML"
        )
        return
    
    await state.clear()
    
    text = _("balance_topup_select_payment_method", amount=amount)
    keyboard = get_balance_topup_payment_methods_keyboard(amount, current_lang, i18n, settings)
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


# Обработчики для каждого платежного провайдера

@router.callback_query(F.data.startswith("balance_topup:pay_yk:"))
async def pay_yk_balance_topup(
    callback: types.CallbackQuery,
    settings: Settings,
    i18n_data: dict,
    yookassa_service: YooKassaService,
    session: AsyncSession,
):
    """Оплата пополнения баланса через YooKassa"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    get_text = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs) if i18n else key
    
    if not i18n or not callback.message:
        try:
            await callback.answer(get_text("error_occurred_try_again"), show_alert=True)
        except Exception:
            pass
        return
    
    if not yookassa_service or not yookassa_service.configured:
        logging.error("YooKassa service is not configured.")
        try:
            await callback.answer(get_text("payment_service_unavailable_alert"), show_alert=True)
        except Exception:
            pass
        return
    
    try:
        amount = float(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        logging.error(f"Invalid amount in callback_data: {callback.data}")
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return
    
    user_id = callback.from_user.id
    payment_description = get_text("balance_topup_payment_description", amount=amount)
    currency_code = "RUB"
    
    # Создаем запись платежа в БД
    payment_record_data = {
        "user_id": user_id,
        "amount": amount,
        "currency": currency_code,
        "status": "pending_yookassa",
        "description": payment_description,
        "provider": "yookassa",
    }
    
    try:
        db_payment_record = await payment_dal.create_payment_record(session, payment_record_data)
        await session.commit()
        logging.info(f"Balance topup payment record {db_payment_record.payment_id} created for user {user_id}")
    except Exception as e:
        await session.rollback()
        logging.error(f"Failed to create payment record: {e}", exc_info=True)
        try:
            await callback.message.edit_text(get_text("error_creating_payment_record"))
        except Exception:
            pass
        return
    
    # Создаем платеж в YooKassa
    yookassa_metadata = {
        "user_id": str(user_id),
        "payment_db_id": str(db_payment_record.payment_id),
        "payment_type": "balance",
    }
    
    payment_response = await yookassa_service.create_payment(
        amount=amount,
        currency=currency_code,
        description=payment_description,
        metadata=yookassa_metadata,
        receipt_email=settings.YOOKASSA_DEFAULT_RECEIPT_EMAIL,
        save_payment_method=False,
    )
    
    if payment_response and payment_response.get("confirmation_url"):
        try:
            await payment_dal.update_payment_status_by_db_id(
                session,
                payment_db_id=db_payment_record.payment_id,
                new_status=payment_response.get("status", "pending"),
                yk_payment_id=payment_response.get("id"),
            )
            await session.commit()
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to update payment record: {e}", exc_info=True)
        
        try:
            await callback.message.edit_text(
                get_text("balance_topup_payment_link", amount=amount),
                reply_markup=get_payment_url_keyboard(
                    payment_response["confirmation_url"],
                    current_lang,
                    i18n,
                    back_callback="balance_topup:select_amount",
                    back_text_key="back_to_main_menu_button",
                ),
                disable_web_page_preview=False,
            )
        except Exception as e:
            logging.warning(f"Failed to edit message: {e}")
            try:
                await callback.message.answer(
                    get_text("balance_topup_payment_link", amount=amount),
                    reply_markup=get_payment_url_keyboard(
                        payment_response["confirmation_url"],
                        current_lang,
                        i18n,
                        back_callback="balance_topup:select_amount",
                        back_text_key="back_to_main_menu_button",
                    ),
                    disable_web_page_preview=False,
                )
            except Exception:
                pass
        try:
            await callback.answer()
        except Exception:
            pass
        return
    
    # Ошибка создания платежа
    try:
        await payment_dal.update_payment_status_by_db_id(
            session, db_payment_record.payment_id, "failed_creation"
        )
        await session.commit()
    except Exception:
        await session.rollback()
    
    logging.error(f"Failed to create YooKassa payment for balance topup. Response: {payment_response}")
    try:
        await callback.message.edit_text(get_text("error_payment_gateway"))
    except Exception:
        pass
    try:
        await callback.answer(get_text("error_payment_gateway"), show_alert=True)
    except Exception:
        pass


@router.callback_query(F.data.startswith("balance_topup:pay_fk:"))
async def pay_fk_balance_topup(
    callback: types.CallbackQuery,
    settings: Settings,
    i18n_data: dict,
    freekassa_service: FreeKassaService,
    session: AsyncSession,
):
    """Оплата пополнения баланса через FreeKassa"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    get_text = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs) if i18n else key
    
    if not i18n or not callback.message:
        try:
            await callback.answer(get_text("error_occurred_try_again"), show_alert=True)
        except Exception:
            pass
        return
    
    if not freekassa_service or not freekassa_service.configured:
        logging.error("FreeKassa service is not configured.")
        try:
            await callback.answer(get_text("payment_service_unavailable_alert"), show_alert=True)
        except Exception:
            pass
        return
    
    try:
        amount = float(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        logging.error(f"Invalid amount in callback_data: {callback.data}")
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return
    
    user_id = callback.from_user.id
    payment_description = get_text("balance_topup_payment_description", amount=amount)
    currency_code = getattr(freekassa_service, "default_currency", "RUB")
    
    payment_record_payload = {
        "user_id": user_id,
        "amount": amount,
        "currency": currency_code,
        "status": "pending_freekassa",
        "description": payment_description,
        "provider": "freekassa",
    }
    
    try:
        payment_record = await payment_dal.create_payment_record(session, payment_record_payload)
        await session.commit()
    except Exception as e:
        await session.rollback()
        logging.error(f"FreeKassa: failed to create payment record: {e}", exc_info=True)
        try:
            await callback.message.edit_text(get_text("error_creating_payment_record"))
        except Exception:
            pass
        return
    
    success, response_data = await freekassa_service.create_order(
        payment_db_id=payment_record.payment_id,
        user_id=payment_record.user_id,
        months=0,  # Для баланса не используется
        amount=amount,
        currency=freekassa_service.default_currency,
        payment_method_id=freekassa_service.payment_method_id,
        ip_address=freekassa_service.server_ip,
        extra_params={
            "us_method": freekassa_service.payment_method_id,
            "payment_type": "balance",
        },
    )
    
    if success:
        location = response_data.get("location")
        order_hash = response_data.get("orderHash")
        order_id_api = response_data.get("orderId")
        provider_identifier = order_hash or order_id_api
        
        if provider_identifier:
            try:
                await payment_dal.update_provider_payment_and_status(
                    session,
                    payment_record.payment_id,
                    str(provider_identifier),
                    payment_record.status,
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                logging.error(f"FreeKassa: failed to store provider order id: {e}", exc_info=True)
        
        if location:
            order_identifier_display = str(order_id_api or provider_identifier or payment_record.payment_id)
            order_info_text = get_text(
                "free_kassa_order_info",
                order_id=order_identifier_display,
                date=datetime.now().strftime("%Y-%m-%d"),
            )
            try:
                await callback.message.edit_text(
                    f"{order_info_text}\n\n" + get_text("balance_topup_payment_link", amount=amount),
                    reply_markup=get_payment_url_keyboard(
                        location,
                        current_lang,
                        i18n,
                        back_callback="balance_topup:select_amount",
                        back_text_key="back_to_main_menu_button",
                    ),
                    disable_web_page_preview=False,
                )
            except Exception:
                try:
                    await callback.message.answer(
                        f"{order_info_text}\n\n" + get_text("balance_topup_payment_link", amount=amount),
                        reply_markup=get_payment_url_keyboard(
                            location,
                            current_lang,
                            i18n,
                            back_callback="balance_topup:select_amount",
                            back_text_key="back_to_main_menu_button",
                        ),
                        disable_web_page_preview=False,
                    )
                except Exception:
                    pass
            try:
                await callback.answer()
            except Exception:
                pass
            return
    
    # Ошибка
    try:
        await payment_dal.update_payment_status_by_db_id(
            session, payment_record.payment_id, "failed_creation"
        )
        await session.commit()
    except Exception:
        await session.rollback()
    
    try:
        await callback.message.edit_text(get_text("error_payment_gateway"))
    except Exception:
        pass
    try:
        await callback.answer(get_text("error_payment_gateway"), show_alert=True)
    except Exception:
        pass


@router.callback_query(F.data.startswith("balance_topup:pay_crypto:"))
async def pay_crypto_balance_topup(
    callback: types.CallbackQuery,
    settings: Settings,
    i18n_data: dict,
    session: AsyncSession,
    cryptopay_service: CryptoPayService,
):
    """Оплата пополнения баланса через CryptoPay"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    get_text = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs) if i18n else key
    
    if not i18n or not callback.message:
        try:
            await callback.answer(get_text("error_occurred_try_again"), show_alert=True)
        except Exception:
            pass
        return
    
    if not cryptopay_service or not getattr(cryptopay_service, "configured", False):
        try:
            await callback.answer(get_text("payment_service_unavailable_alert"), show_alert=True)
        except Exception:
            pass
        return
    
    try:
        amount = float(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return
    
    user_id = callback.from_user.id
    payment_description = get_text("balance_topup_payment_description", amount=amount)
    
    invoice_url = await cryptopay_service.create_invoice(
        session=session,
        user_id=user_id,
        months=0,  # Для баланса не используется
        amount=amount,
        description=payment_description,
        payment_type="balance",
    )
    
    if invoice_url:
        try:
            await callback.message.edit_text(
                get_text("balance_topup_payment_link", amount=amount),
                reply_markup=get_payment_url_keyboard(
                    invoice_url,
                    current_lang,
                    i18n,
                    back_callback="balance_topup:select_amount",
                    back_text_key="back_to_main_menu_button",
                ),
                disable_web_page_preview=False,
            )
        except Exception:
            try:
                await callback.message.answer(
                    get_text("balance_topup_payment_link", amount=amount),
                    reply_markup=get_payment_url_keyboard(
                        invoice_url,
                        current_lang,
                        i18n,
                        back_callback="balance_topup:select_amount",
                        back_text_key="back_to_main_menu_button",
                    ),
                    disable_web_page_preview=False,
                )
            except Exception:
                pass
        try:
            await callback.answer()
        except Exception:
            pass
        return
    
    try:
        await callback.answer(get_text("error_payment_gateway"), show_alert=True)
    except Exception:
        pass


@router.callback_query(F.data.startswith("balance_topup:pay_stars:"))
async def pay_stars_balance_topup(
    callback: types.CallbackQuery,
    settings: Settings,
    i18n_data: dict,
    session: AsyncSession,
    stars_service: StarsService,
):
    """Оплата пополнения баланса через Telegram Stars"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    get_text = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs) if i18n else key
    
    if not i18n or not callback.message:
        try:
            await callback.answer(get_text("error_occurred_try_again"), show_alert=True)
        except Exception:
            pass
        return
    
    if not settings.STARS_ENABLED:
        try:
            await callback.answer(get_text("payment_service_unavailable_alert"), show_alert=True)
        except Exception:
            pass
        return
    
    try:
        parts = callback.data.split(":")
        amount = float(parts[-2])
        stars_price = int(parts[-1])
    except (ValueError, IndexError):
        await callback.answer(get_text("error_try_again"), show_alert=True)
        return
    
    user_id = callback.from_user.id
    payment_description = get_text("balance_topup_payment_description", amount=amount)
    
    payment_db_id = await stars_service.create_invoice(
        session=session,
        user_id=user_id,
        months=0,  # Для баланса не используется
        stars_price=stars_price,
        description=payment_description,
        payment_type="balance",
        balance_amount=amount,
    )
    
    if payment_db_id:
        try:
            await callback.message.edit_text(
                get_text("payment_invoice_sent_message"),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=get_text("back_to_main_menu_button"),
                        callback_data="balance_topup:select_amount",
                    )]
                ]),
            )
        except Exception as e:
            logging.warning(f"Stars payment: failed to show invoice info message ({e})")
        try:
            await callback.answer()
        except Exception:
            pass
        return
    
    try:
        await callback.answer(get_text("error_payment_gateway"), show_alert=True)
    except Exception:
        pass