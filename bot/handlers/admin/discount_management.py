import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import Settings
from db.dal import discount_dal, tariff_dal, user_dal
from bot.states.admin_states import AdminStates
from bot.keyboards.inline.admin_keyboards import (
    get_discount_management_keyboard,
    get_discount_tariff_selection_keyboard,
    get_user_discounts_keyboard,
    get_discount_actions_keyboard,
    get_back_to_admin_panel_keyboard
)
from bot.middlewares.i18n import JsonI18n

router = Router(name="discount_management_router")


async def discount_management_handler(
    callback: types.CallbackQuery,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Главное меню управления скидками"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    text = _(
        "admin_discount_management_title",
        default="<b>🎁 Управление персональными скидками</b>\n\n"
                "Здесь вы можете устанавливать и управлять персональными скидками для пользователей."
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_discount_management_keyboard(i18n, current_lang),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_discount_management_keyboard(i18n, current_lang),
            parse_mode="HTML"
        )
    await callback.answer()


# Установка скидки - шаг 1: User ID
async def set_discount_start(
    callback: types.CallbackQuery,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings
):
    """Начало установки скидки"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    text = _(
        "admin_set_discount_step1_user_id",
        default="<b>➕ Установка скидки</b>\n\n<b>Шаг 1 из 3:</b> ID пользователя\n\n"
                "Введите Telegram ID пользователя, которому хотите установить скидку:"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
            parse_mode="HTML"
        )
    
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_discount_user_id)


@router.message(AdminStates.waiting_for_discount_user_id, F.text)
async def process_discount_user_id(
    message: types.Message,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Обработка User ID для скидки"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    try:
        user_id = int(message.text.strip())
        if user_id <= 0:
            raise ValueError("Invalid user ID")
    except ValueError:
        await message.answer(_(
            "admin_invalid_user_id",
            default="❌ Введите корректный Telegram ID пользователя"
        ))
        return

    # Проверяем существование пользователя
    user = await user_dal.get_user_by_id(session, user_id)
    if not user:
        await message.answer(_(
            "admin_user_not_found",
            default="❌ Пользователь с таким ID не найден в базе"
        ))
        return

    await state.update_data(discount_user_id=user_id, discount_user=user)

    # Показываем информацию о пользователе
    user_info = f"@{user.username}" if user.username else f"ID: {user_id}"
    if user.first_name:
        user_info += f" ({user.first_name})"

    text = _(
        "admin_set_discount_step2_percentage",
        default="<b>➕ Установка скидки</b>\n\n<b>Шаг 2 из 3:</b> Процент скидки\n\n"
                "Пользователь: <b>{user_info}</b>\n\n"
                "Введите процент скидки (1-99):",
        user_info=user_info
    )

    await message.answer(
        text,
        reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_discount_percentage)


@router.message(AdminStates.waiting_for_discount_percentage, F.text)
async def process_discount_percentage(
    message: types.Message,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Обработка процента скидки"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    try:
        percentage = float(message.text.strip())
        if not (1 <= percentage <= 99):
            raise ValueError("Percentage out of range")
    except ValueError:
        await message.answer(_(
            "admin_invalid_discount_percentage",
            default="❌ Введите корректный процент скидки (1-99)"
        ))
        return

    await state.update_data(discount_percentage=percentage)

    # Получаем активные тарифы для выбора
    active_tariffs = await tariff_dal.get_active_tariffs(session)

    data = await state.get_data()
    user = data.get("discount_user")
    user_info = f"@{user.username}" if user.username else f"ID: {data.get('discount_user_id')}"
    if user.first_name:
        user_info += f" ({user.first_name})"

    text = _(
        "admin_set_discount_step3_tariff",
        default="<b>➕ Установка скидки</b>\n\n<b>Шаг 3 из 3:</b> Выбор тарифа\n\n"
                "Пользователь: <b>{user_info}</b>\nСкидка: <b>{percentage}%</b>\n\n"
                "Выберите тариф, для которого будет действовать скидка, или выберите \"Все тарифы\":",
        user_info=user_info,
        percentage=percentage
    )

    await message.answer(
        text,
        reply_markup=get_discount_tariff_selection_keyboard(active_tariffs, i18n, current_lang),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_discount_tariff_selection)


@router.callback_query(F.data.startswith("admin_discount:tariff:"), AdminStates.waiting_for_discount_tariff_selection)
async def process_discount_tariff_selection(
    callback: types.CallbackQuery,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Обработка выбора тарифа и создание скидки"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    parts = callback.data.split(":")
    tariff_selection = parts[2]  # 'all' or tariff_id

    tariff_id = None if tariff_selection == "all" else int(tariff_selection)

    data = await state.get_data()
    user_id = data.get("discount_user_id")
    percentage = data.get("discount_percentage")
    user = data.get("discount_user")

    try:
        # Создаем скидку
        discount = await discount_dal.create_user_discount(
            session,
            user_id=user_id,
            discount_percentage=percentage,
            tariff_id=tariff_id
        )
        await session.commit()

        logging.info(
            f"Created discount {discount.id} for user {user_id}: {percentage}% "
            f"for tariff_id={tariff_id or 'all'} by admin {callback.from_user.id}"
        )

        # Формируем сообщение об успехе
        user_info = f"@{user.username}" if user.username else f"ID: {user_id}"
        if user.first_name:
            user_info += f" ({user.first_name})"

        tariff_info = "Все тарифы"
        if tariff_id:
            tariff = await tariff_dal.get_tariff_by_id(session, tariff_id)
            if tariff:
                tariff_info = f"{tariff.name} ({tariff.price} {tariff.currency})"

        success_text = _(
            "admin_discount_created_success",
            default="✅ <b>Скидка успешно установлена!</b>\n\n"
                    "<b>Пользователь:</b> {user_info}\n"
                    "<b>Скидка:</b> {percentage}%\n"
                    "<b>Применяется:</b> {tariff_info}",
            user_info=user_info,
            percentage=percentage,
            tariff_info=tariff_info
        )

        try:
            await callback.message.edit_text(
                success_text,
                reply_markup=get_discount_management_keyboard(i18n, current_lang),
                parse_mode="HTML"
            )
        except Exception:
            await callback.message.answer(
                success_text,
                reply_markup=get_discount_management_keyboard(i18n, current_lang),
                parse_mode="HTML"
            )

        await callback.answer()
        await state.clear()

    except Exception as e:
        logging.error(f"Error creating discount: {e}")
        await callback.message.answer(
            _("error_occurred_try_again", default="❌ Произошла ошибка. Попробуйте снова."),
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n)
        )
        await callback.answer()
        await state.clear()


# Просмотр скидок пользователя
async def view_discounts_start(
    callback: types.CallbackQuery,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings
):
    """Запрос User ID для просмотра скидок"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    text = _(
        "admin_view_discounts_prompt",
        default="<b>👁 Просмотр скидок пользователя</b>\n\n"
                "Введите Telegram ID пользователя для просмотра его скидок:"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
            parse_mode="HTML"
        )
    
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_discount_view_user_id)


@router.message(AdminStates.waiting_for_discount_view_user_id, F.text)
async def process_view_discounts_user_id(
    message: types.Message,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Обработка User ID и отображение скидок"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    try:
        user_id = int(message.text.strip())
        if user_id <= 0:
            raise ValueError("Invalid user ID")
    except ValueError:
        await message.answer(_(
            "admin_invalid_user_id",
            default="❌ Введите корректный Telegram ID пользователя"
        ))
        return

    # Проверяем существование пользователя
    user = await user_dal.get_user_by_id(session, user_id)
    if not user:
        await message.answer(_(
            "admin_user_not_found",
            default="❌ Пользователь с таким ID не найден в базе"
        ))
        return

    # Получаем все скидки пользователя
    discounts = await discount_dal.get_all_user_discounts(session, user_id)

    user_info = f"@{user.username}" if user.username else f"ID: {user_id}"
    if user.first_name:
        user_info += f" ({user.first_name})"

    if not discounts:
        text = _(
            "admin_no_discounts_for_user",
            default="<b>👁 Скидки пользователя</b>\n\n"
                    "Пользователь: <b>{user_info}</b>\n\n"
                    "У этого пользователя нет персональных скидок.",
            user_info=user_info
        )
        await message.answer(
            text,
            reply_markup=get_discount_management_keyboard(i18n, current_lang),
            parse_mode="HTML"
        )
        await state.clear()
        return

    # Формируем детальное описание скидок
    discounts_text = []
    for idx, discount in enumerate(discounts, 1):
        status = "✅ Активна" if discount.is_active else "❌ Неактивна"
        
        if discount.tariff_id:
            tariff = await tariff_dal.get_tariff_by_id(session, discount.tariff_id)
            tariff_info = f"Тариф: {tariff.name}" if tariff else f"Тариф ID: {discount.tariff_id}"
        else:
            tariff_info = "Все тарифы"
        
        discounts_text.append(
            f"{idx}. <b>{discount.discount_percentage}%</b> - {tariff_info}\n"
            f"   Статус: {status}\n"
            f"   Создана: {discount.created_at.strftime('%d.%m.%Y %H:%M')}"
        )

    text = _(
        "admin_user_discounts_list",
        default="<b>👁 Скидки пользователя</b>\n\n"
                "Пользователь: <b>{user_info}</b>\n\n"
                "Всего скидок: <b>{total}</b>\n\n{discounts_list}",
        user_info=user_info,
        total=len(discounts),
        discounts_list="\n\n".join(discounts_text)
    )

    await message.answer(
        text,
        reply_markup=get_user_discounts_keyboard(discounts, user_id, i18n, current_lang),
        parse_mode="HTML"
    )
    await state.clear()


# Просмотр деталей скидки
@router.callback_query(F.data.startswith("admin_discount:details:"))
async def view_discount_details(
    callback: types.CallbackQuery,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Просмотр детальной информации о скидке"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    parts = callback.data.split(":")
    discount_id = int(parts[2])

    discount = await session.get(discount_dal.UserDiscount, discount_id)
    if not discount:
        await callback.answer(_("admin_discount_not_found", default="Скидка не найдена"), show_alert=True)
        return

    # Получаем информацию о пользователе
    user = await user_dal.get_user_by_id(session, discount.user_id)
    user_info = f"@{user.username}" if user and user.username else f"ID: {discount.user_id}"
    if user and user.first_name:
        user_info += f" ({user.first_name})"

    # Получаем информацию о тарифе
    if discount.tariff_id:
        tariff = await tariff_dal.get_tariff_by_id(session, discount.tariff_id)
        tariff_info = f"{tariff.name} ({tariff.price} {tariff.currency})" if tariff else f"Тариф ID: {discount.tariff_id}"
    else:
        tariff_info = "Все тарифы"

    status = "✅ Активна" if discount.is_active else "❌ Неактивна"

    text = _(
        "admin_discount_details",
        default="<b>🎁 Информация о скидке</b>\n\n"
                "<b>Пользователь:</b> {user_info}\n"
                "<b>Скидка:</b> {percentage}%\n"
                "<b>Применяется:</b> {tariff_info}\n"
                "<b>Статус:</b> {status}\n"
                "<b>Создана:</b> {created_at}",
        user_info=user_info,
        percentage=discount.discount_percentage,
        tariff_info=tariff_info,
        status=status,
        created_at=discount.created_at.strftime('%d.%m.%Y %H:%M')
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_discount_actions_keyboard(discount_id, discount.is_active, i18n, current_lang),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_discount_actions_keyboard(discount_id, discount.is_active, i18n, current_lang),
            parse_mode="HTML"
        )
    await callback.answer()


# Деактивация скидки
@router.callback_query(F.data.startswith("admin_discount:deactivate:"))
async def deactivate_discount(
    callback: types.CallbackQuery,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Деактивация скидки"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    parts = callback.data.split(":")
    discount_id = int(parts[2])

    try:
        discount = await discount_dal.deactivate_user_discount(session, discount_id)
        if discount:
            await session.commit()
            logging.info(f"Discount {discount_id} deactivated by admin {callback.from_user.id}")
            
            await callback.answer(
                _("admin_discount_deactivated_success", default="✅ Скидка деактивирована"),
                show_alert=True
            )
            
            # Вернуться к управлению скидками
            await discount_management_handler(callback, i18n_data, settings, session)
        else:
            await callback.answer(
                _("admin_discount_not_found", default="Скидка не найдена"),
                show_alert=True
            )
    except Exception as e:
        logging.error(f"Error deactivating discount {discount_id}: {e}")
        await callback.answer(
            _("error_occurred_try_again", default="❌ Произошла ошибка"),
            show_alert=True
        )