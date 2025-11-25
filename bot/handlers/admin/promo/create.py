import logging
from aiogram import Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import Settings
from db.dal import promo_code_dal, tariff_dal
from bot.states.admin_states import AdminStates
from bot.keyboards.inline.admin_keyboards import (
    get_back_to_admin_panel_keyboard,
    get_admin_panel_keyboard,
    get_promo_type_selection_keyboard,
    get_promo_tariff_selection_keyboard
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from bot.middlewares.i18n import JsonI18n

router = Router(name="promo_create_router")


async def create_promo_prompt_handler(callback: types.CallbackQuery,
                                      state: FSMContext, i18n_data: dict,
                                      settings: Settings,
                                      session: AsyncSession):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error preparing promo creation.",
                              show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    # Step 1: Ask for promo code
    prompt_text = _(
        "admin_promo_step1_code",
        default="🎟 <b>Создание промокода</b>\n\n<b>Шаг 1:</b> Код промокода\n\nВведите код промокода (3-30 символов, только буквы и цифры):"
    )

    try:
        await callback.message.edit_text(
            prompt_text,
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
            parse_mode="HTML")
    except Exception as e:
        logging.warning(
            f"Could not edit message for promo prompt: {e}. Sending new.")
        await callback.message.answer(
            prompt_text,
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
            parse_mode="HTML")
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_promo_code)


# Step 1: Process promo code
@router.message(AdminStates.waiting_for_promo_code, F.text)
async def process_promo_code_handler(message: types.Message,
                                    state: FSMContext,
                                    i18n_data: dict,
                                    settings: Settings,
                                    session: AsyncSession):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    try:
        code_str = message.text.strip().upper()
        if not (3 <= len(code_str) <= 30 and code_str.isalnum()):
            await message.answer(_(
                "admin_promo_invalid_code_format",
                default="❌ Код промокода должен содержать 3-30 символов (только буквы и цифры)"
            ))
            return
        
        # Check if code already exists
        existing_promo = await promo_code_dal.get_promo_code_by_code(session, code_str)
        if existing_promo:
            await message.answer(_(
                "admin_promo_code_already_exists",
                default="❌ Промокод с таким кодом уже существует"
            ))
            return
        
        await state.update_data(promo_code=code_str)
        
        # Step 2: Ask for promo type
        prompt_text = _(
            "admin_promo_step2_type",
            default="🎟 <b>Создание промокода</b>\n\n<b>Шаг 2:</b> Тип промокода\n\nКод: <b>{code}</b>\n\nВыберите тип промокода:",
            code=code_str
        )
        
        await message.answer(
            prompt_text,
            reply_markup=get_promo_type_selection_keyboard(i18n, current_lang),
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.waiting_for_promo_type)
        
    except Exception as e:
        logging.error(f"Error processing promo code: {e}")
        await message.answer(_("error_occurred_try_again"))


# Step 2: Process promo type selection
@router.callback_query(F.data.startswith("promo_type:"), StateFilter(AdminStates.waiting_for_promo_type))
async def process_promo_type_handler(callback: types.CallbackQuery,
                                    state: FSMContext,
                                    i18n_data: dict,
                                    settings: Settings,
                                    session: AsyncSession):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    promo_type = callback.data.split(":")[1]
    await state.update_data(promo_type=promo_type)
    
    data = await state.get_data()
    code = data.get("promo_code")

    # В зависимости от типа промокода, запрашиваем разные параметры
    if promo_type == "bonus_days":
        prompt_text = _(
            "admin_promo_step3_bonus_days",
            default="🎟 <b>Создание промокода</b>\n\n<b>Шаг 3:</b> Бонусные дни\n\nКод: <b>{code}</b>\nТип: <b>Бонусные дни</b>\n\nВведите количество бонусных дней (1-365):",
            code=code
        )
        next_state = AdminStates.waiting_for_promo_value
        
    elif promo_type == "percent":
        prompt_text = _(
            "admin_promo_step3_percent",
            default="🎟 <b>Создание промокода</b>\n\n<b>Шаг 3:</b> Процент скидки\n\nКод: <b>{code}</b>\nТип: <b>Процентная скидка</b>\n\nВведите процент скидки (1-99):",
            code=code
        )
        next_state = AdminStates.waiting_for_promo_value
        
    elif promo_type == "fixed_amount":
        prompt_text = _(
            "admin_promo_step3_fixed_amount",
            default="🎟 <b>Создание промокода</b>\n\n<b>Шаг 3:</b> Сумма скидки\n\nКод: <b>{code}</b>\nТип: <b>Фиксированная скидка</b>\n\nВведите сумму скидки в рублях (например: 100):",
            code=code
        )
        next_state = AdminStates.waiting_for_promo_value
        
    elif promo_type == "balance":
        prompt_text = _(
            "admin_promo_step3_balance",
            default="🎟 <b>Создание промокода</b>\n\n<b>Шаг 3:</b> Пополнение баланса\n\nКод: <b>{code}</b>\nТип: <b>Пополнение баланса</b>\n\nВведите сумму пополнения в рублях:",
            code=code
        )
        next_state = AdminStates.waiting_for_promo_value
    else:
        await callback.answer("Unknown type", show_alert=True)
        return

    try:
        await callback.message.edit_text(
            prompt_text,
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            prompt_text,
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
            parse_mode="HTML"
        )
    
    await callback.answer()
    await state.set_state(next_state)


# Step 3: Process promo value
@router.message(AdminStates.waiting_for_promo_value, F.text)
async def process_promo_value_handler(message: types.Message,
                                     state: FSMContext,
                                     i18n_data: dict,
                                     settings: Settings,
                                     session: AsyncSession):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    try:
        data = await state.get_data()
        promo_type = data.get("promo_type")
        value_str = message.text.strip()
        
        # Валидация в зависимости от типа
        if promo_type == "bonus_days":
            value = int(value_str)
            if not (1 <= value <= 365):
                await message.answer(_(
                    "admin_promo_invalid_bonus_days",
                    default="❌ Количество дней должно быть от 1 до 365"
                ))
                return
            await state.update_data(bonus_days=value, value=0)
            
        elif promo_type == "percent":
            value = float(value_str)
            if not (1 <= value <= 99):
                await message.answer(_(
                    "admin_promo_invalid_percent",
                    default="❌ Процент должен быть от 1 до 99"
                ))
                return
            await state.update_data(value=value, bonus_days=0)
            
        elif promo_type in ["fixed_amount", "balance"]:
            value = float(value_str)
            if value <= 0:
                await message.answer(_(
                    "admin_promo_invalid_amount",
                    default="❌ Сумма должна быть положительной"
                ))
                return
            await state.update_data(value=value, bonus_days=0)
        else:
            await message.answer(_("error_occurred_try_again"))
            return

        # Переходим к выбору применимости к тарифам
        active_tariffs = await tariff_dal.get_active_tariffs(session)
        
        code = data.get("promo_code")
        type_name = {
            "bonus_days": "Бонусные дни",
            "percent": "Процентная скидка", 
            "fixed_amount": "Фиксированная скидка",
            "balance": "Пополнение баланса"
        }.get(promo_type, promo_type)
        
        value_display = f"{value} дней" if promo_type == "bonus_days" else f"{value}%"  if promo_type == "percent" else f"{value} RUB"
        
        prompt_text = _(
            "admin_promo_step4_tariffs",
            default="🎟 <b>Создание промокода</b>\n\n<b>Шаг 4:</b> Применимость\n\n"
                    "Код: <b>{code}</b>\nТип: <b>{type_name}</b>\nЗначение: <b>{value}</b>\n\n"
                    "Выберите тарифы, для которых будет действовать промокод\n"
                    "(или \"Все тарифы\" / \"Пропустить\"):",
            code=code,
            type_name=type_name,
            value=value_display
        )
        
        await message.answer(
            prompt_text,
            reply_markup=get_promo_tariff_selection_keyboard(active_tariffs, i18n, current_lang, allow_all=True),
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.waiting_for_promo_tariff_selection)
        
    except ValueError:
        await message.answer(_(
            "admin_promo_invalid_number",
            default="❌ Введите корректное число"
        ))
    except Exception as e:
        logging.error(f"Error processing promo value: {e}")
        await message.answer(_("error_occurred_try_again"))


# Step 4: Process tariff selection
@router.callback_query(F.data.startswith("promo_tariffs:"), StateFilter(AdminStates.waiting_for_promo_tariff_selection))
async def process_promo_tariffs_handler(callback: types.CallbackQuery,
                                       state: FSMContext,
                                       i18n_data: dict,
                                       settings: Settings):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    action = callback.data.split(":")[1]
    
    if action == "all":
        await state.update_data(applicable_tariff_ids=None)
    elif action == "skip":
        await state.update_data(applicable_tariff_ids=None)
    elif action == "select":
        tariff_id = int(callback.data.split(":")[2])
        # В упрощенной версии выбираем один тариф
        await state.update_data(applicable_tariff_ids=[tariff_id])
    else:
        await callback.answer("Unknown action", show_alert=True)
        return

    # Переходим к минимальной сумме покупки
    data = await state.get_data()
    code = data.get("promo_code")
    promo_type = data.get("promo_type")
    
    type_name = {
        "bonus_days": "Бонусные дни",
        "percent": "Процентная скидка",
        "fixed_amount": "Фиксированная скидка",
        "balance": "Пополнение баланса"
    }.get(promo_type, promo_type)
    
    prompt_text = _(
        "admin_promo_step5_min_purchase",
        default="🎟 <b>Создание промокода</b>\n\n<b>Шаг 5:</b> Минимальная сумма\n\n"
                "Код: <b>{code}</b>\nТип: <b>{type_name}</b>\n\n"
                "Введите минимальную сумму покупки в рублях для применения промокода\n"
                "или \"0\" если ограничения нет:",
        code=code,
        type_name=type_name
    )
    
    try:
        await callback.message.edit_text(
            prompt_text,
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            prompt_text,
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
            parse_mode="HTML"
        )
    
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_promo_min_purchase)


# Step 5: Process min purchase amount
@router.message(AdminStates.waiting_for_promo_min_purchase, F.text)
async def process_promo_min_purchase_handler(message: types.Message,
                                            state: FSMContext,
                                            i18n_data: dict,
                                            settings: Settings):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    try:
        min_purchase = float(message.text.strip())
        if min_purchase < 0:
            await message.answer(_(
                "admin_promo_invalid_min_purchase",
                default="❌ Сумма не может быть отрицательной"
            ))
            return
        
        await state.update_data(min_purchase_amount=min_purchase if min_purchase > 0 else None)
        
        # Переходим к макс. активациям
        data = await state.get_data()
        code = data.get("promo_code")
        
        prompt_text = _(
            "admin_promo_step6_max_activations",
            default="🎟 <b>Создание промокода</b>\n\n<b>Шаг 6:</b> Лимит активаций\n\n"
                    "Код: <b>{code}</b>\n\nВведите максимальное количество активаций (1-10000):",
            code=code
        )
        
        await message.answer(
            prompt_text,
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.waiting_for_promo_max_activations)
        
    except ValueError:
        await message.answer(_(
            "admin_promo_invalid_number",
            default="❌ Введите корректное число"
        ))
    except Exception as e:
        logging.error(f"Error processing min purchase: {e}")
        await message.answer(_("error_occurred_try_again"))


# Step 6: Process max activations
@router.message(AdminStates.waiting_for_promo_max_activations, F.text)
async def process_promo_max_activations_handler(message: types.Message,
                                               state: FSMContext,
                                               i18n_data: dict,
                                               settings: Settings):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    try:
        max_activations = int(message.text.strip())
        if not (1 <= max_activations <= 10000):
            await message.answer(_(
                "admin_promo_invalid_max_activations",
                default="❌ Максимальное количество активаций должно быть от 1 до 10000"
            ))
            return
        
        await state.update_data(max_activations=max_activations)
        
        # Step 7: Ask for validity
        data = await state.get_data()
        prompt_text = _(
            "admin_promo_step7_validity",
            default="🎟 <b>Создание промокода</b>\n\n<b>Шаг 7:</b> Срок действия\n\n"
                    "Код: <b>{code}</b>\nМакс. активаций: <b>{max_activations}</b>\n\n"
                    "Выберите срок действия промокода:",
            code=data.get("promo_code"),
            max_activations=max_activations
        )
        
        # Create keyboard for validity options
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text=_("admin_promo_unlimited_validity", default="🔄 Без ограничений"),
                callback_data="promo_unlimited_validity"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=_("admin_promo_set_validity_days", default="📅 Указать дни"),
                callback_data="promo_set_validity"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=_("admin_back_to_panel", default="🔙 В админ панель"),
                callback_data="admin_action:main"
            )
        )
        
        await message.answer(
            prompt_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.waiting_for_promo_validity_days)
        
    except ValueError:
        await message.answer(_(
            "admin_promo_invalid_number",
            default="❌ Введите корректное число"
        ))
    except Exception as e:
        logging.error(f"Error processing promo max activations: {e}")
        await message.answer(_("error_occurred_try_again"))


# Step 7: Handle unlimited validity
@router.callback_query(F.data == "promo_unlimited_validity", StateFilter(AdminStates.waiting_for_promo_validity_days))
async def process_promo_unlimited_validity(callback: types.CallbackQuery,
                                          state: FSMContext,
                                          i18n_data: dict,
                                          settings: Settings,
                                          session: AsyncSession):
    await state.update_data(validity_days=None)
    await create_promo_code_final(callback, state, i18n_data, settings, session)


# Step 7: Handle set validity
@router.callback_query(F.data == "promo_set_validity", StateFilter(AdminStates.waiting_for_promo_validity_days))
async def process_promo_set_validity(callback: types.CallbackQuery,
                                    state: FSMContext,
                                    i18n_data: dict,
                                    settings: Settings):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error processing validity.", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    data = await state.get_data()
    prompt_text = _(
        "admin_promo_enter_validity_days",
        default="🎟 <b>Создание промокода</b>\n\n<b>Шаг 7:</b> Срок действия\n\n"
                "Код: <b>{code}</b>\n\nВведите количество дней действия промокода (1-365):",
        code=data.get("promo_code")
    )
    
    try:
        await callback.message.edit_text(
            prompt_text,
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            prompt_text,
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
            parse_mode="HTML"
        )
    await callback.answer()


# Step 7: Process validity days
@router.message(AdminStates.waiting_for_promo_validity_days, F.text)
async def process_promo_validity_days_handler(message: types.Message,
                                             state: FSMContext,
                                             i18n_data: dict,
                                             settings: Settings,
                                             session: AsyncSession):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    try:
        validity_days = int(message.text.strip())
        if not (1 <= validity_days <= 365):
            await message.answer(_(
                "admin_promo_invalid_validity_days",
                default="❌ Срок действия должен быть от 1 до 365 дней"
            ))
            return
        
        await state.update_data(validity_days=validity_days)
        await create_promo_code_final(message, state, i18n_data, settings, session)
        
    except ValueError:
        await message.answer(_(
            "admin_promo_invalid_number",
            default="❌ Введите корректное число"
        ))
    except Exception as e:
        logging.error(f"Error processing promo validity days: {e}")
        await message.answer(_("error_occurred_try_again"))


async def create_promo_code_final(callback_or_message,
                                 state: FSMContext,
                                 i18n_data: dict,
                                 settings: Settings,
                                 session: AsyncSession):
    """Final step - create the promo code in database"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    try:
        data = await state.get_data()
        
        # Prepare promo code data
        promo_data = {
            "code": data["promo_code"],
            "type": data.get("promo_type", "bonus_days"),
            "value": data.get("value", 0),
            "bonus_days": data.get("bonus_days", 0),
            "min_purchase_amount": data.get("min_purchase_amount"),
            "applicable_tariff_ids": data.get("applicable_tariff_ids"),
            "max_activations": data["max_activations"],
            "current_activations": 0,
            "is_active": True,
            "created_by_admin_id": callback_or_message.from_user.id,
            "created_at": datetime.now(timezone.utc)
        }
        
        # Set validity
        if data.get("validity_days"):
            promo_data["valid_until"] = datetime.now(timezone.utc) + timedelta(days=data["validity_days"])
        else:
            promo_data["valid_until"] = None
        
        # Create promo code
        created_promo = await promo_code_dal.create_promo_code(session, promo_data)
        await session.commit()
        
        # Log successful creation
        logging.info(f"Promo code '{data['promo_code']}' (type={promo_data['type']}) created with ID {created_promo.promo_code_id}")
        
        # Success message
        promo_type = data.get("promo_type", "bonus_days")
        type_name = {
            "bonus_days": "Бонусные дни",
            "percent": "Процентная скидка",
            "fixed_amount": "Фиксированная скидка",
            "balance": "Пополнение баланса"
        }.get(promo_type, promo_type)
        
        if promo_type == "bonus_days":
            value_display = f"{data.get('bonus_days')} дней"
        elif promo_type == "percent":
            value_display = f"{data.get('value')}%"
        else:
            value_display = f"{data.get('value')} RUB"
        
        valid_until_str = _("admin_promo_unlimited", default="Без ограничений") if not data.get("validity_days") else f"{data['validity_days']} дней"
        
        tariff_info = "Все тарифы" if not data.get("applicable_tariff_ids") else f"Тарифы: {data.get('applicable_tariff_ids')}"
        min_purchase_info = f"от {data.get('min_purchase_amount')} RUB" if data.get("min_purchase_amount") else "—"
        
        success_text = _(
            "admin_promo_created_success_extended",
            default="✅ <b>Промокод успешно создан!</b>\n\n"
                   "🎟 Код: <code>{code}</code>\n"
                   "📝 Тип: <b>{type_name}</b>\n"
                   "💎 Значение: <b>{value}</b>\n"
                   "📦 Применимость: <b>{tariffs}</b>\n"
                   "💰 Мин. сумма: <b>{min_purchase}</b>\n"
                   "📊 Макс. активаций: <b>{max_activations}</b>\n"
                   "⏰ Срок действия: <b>{valid_until_str}</b>",
            code=data["promo_code"],
            type_name=type_name,
            value=value_display,
            tariffs=tariff_info,
            min_purchase=min_purchase_info,
            max_activations=data["max_activations"],
            valid_until_str=valid_until_str
        )
        
        if hasattr(callback_or_message, 'message'):  # CallbackQuery
            try:
                await callback_or_message.message.edit_text(
                    success_text,
                    reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
                    parse_mode="HTML"
                )
            except Exception:
                await callback_or_message.message.answer(
                    success_text,
                    reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
                    parse_mode="HTML"
                )
            await callback_or_message.answer()
        else:  # Message
            await callback_or_message.answer(
                success_text,
                reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
                parse_mode="HTML"
            )
        
        await state.clear()
        
    except Exception as e:
        logging.error(f"Error creating promo code: {e}")
        error_text = _("error_occurred_try_again", default="❌ Произошла ошибка. Попробуйте снова.")
        
        if hasattr(callback_or_message, 'message'):  # CallbackQuery
            await callback_or_message.message.answer(error_text)
            await callback_or_message.answer()
        else:  # Message
            await callback_or_message.answer(error_text)
        
        await state.clear()


# Cancel promo creation
@router.callback_query(
    F.data == "admin_action:main",
    StateFilter(
        AdminStates.waiting_for_promo_code,
        AdminStates.waiting_for_promo_type,
        AdminStates.waiting_for_promo_value,
        AdminStates.waiting_for_promo_tariff_selection,
        AdminStates.waiting_for_promo_min_purchase,
        AdminStates.waiting_for_promo_max_activations,
        AdminStates.waiting_for_promo_validity_days,
    ),
)
async def cancel_promo_creation_state_to_menu(callback: types.CallbackQuery,
                                              state: FSMContext,
                                              settings: Settings,
                                              i18n_data: dict,
                                              session: AsyncSession):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error cancelling.", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    try:
        await callback.message.edit_text(
            _(key="admin_panel_title"),
            reply_markup=get_admin_panel_keyboard(i18n, current_lang, settings)
        )
    except Exception:
        await callback.message.answer(
            _(key="admin_panel_title"),
            reply_markup=get_admin_panel_keyboard(i18n, current_lang, settings)
        )
    
    await callback.answer(_("admin_promo_creation_cancelled", default="Создание промокода отменено"))
    await state.clear()