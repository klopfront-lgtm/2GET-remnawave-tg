import logging
from aiogram import Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import Settings
from db.dal import tariff_dal
from bot.states.admin_states import AdminStates
from bot.keyboards.inline.admin_keyboards import (
    get_tariff_management_keyboard,
    get_tariffs_list_admin_keyboard,
    get_tariff_actions_keyboard,
    get_back_to_admin_panel_keyboard
)
from bot.middlewares.i18n import JsonI18n

router = Router(name="tariff_management_router")


async def tariff_management_handler(
    callback: types.CallbackQuery,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Главное меню управления тарифами"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    text = _(
        "admin_tariff_management_title",
        default="<b>📋 Управление тарифами</b>\n\n"
                "Здесь вы можете создавать, редактировать и управлять тарифами."
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_tariff_management_keyboard(i18n, current_lang),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_tariff_management_keyboard(i18n, current_lang),
            parse_mode="HTML"
        )
    await callback.answer()


async def tariffs_list_handler(
    callback: types.CallbackQuery,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession,
    page: int = 0
):
    """Список всех тарифов с пагинацией"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    # Получаем все тарифы
    all_tariffs = await tariff_dal.get_all_tariffs(session)
    
    page_size = 10
    total_tariffs = len(all_tariffs)
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_tariffs = all_tariffs[start_idx:end_idx]

    if not all_tariffs:
        text = _(
            "admin_no_tariffs",
            default="<b>📋 Список тарифов</b>\n\nТарифов пока нет. Создайте первый тариф!"
        )
    else:
        text = _(
            "admin_tariffs_list_title",
            default="<b>📋 Список тарифов</b>\n\nВсего тарифов: {total}\nСтраница: {page} из {total_pages}",
            total=total_tariffs,
            page=page + 1,
            total_pages=((total_tariffs - 1) // page_size + 1) if total_tariffs > 0 else 1
        )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_tariffs_list_admin_keyboard(
                page_tariffs, page, total_tariffs, i18n, current_lang, page_size
            ),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_tariffs_list_admin_keyboard(
                page_tariffs, page, total_tariffs, i18n, current_lang, page_size
            ),
            parse_mode="HTML"
        )
    await callback.answer()


async def view_tariff_handler(
    callback: types.CallbackQuery,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession,
    tariff_id: int,
    back_page: int = 0
):
    """Просмотр детальной информации о тарифе"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    tariff = await tariff_dal.get_tariff_by_id(session, tariff_id)
    if not tariff:
        await callback.answer(_("admin_tariff_not_found", default="Тариф не найден"), show_alert=True)
        return

    # Форматирование данных
    traffic = "∞" if not tariff.traffic_limit_bytes else f"{tariff.traffic_limit_bytes / (1024**3):.0f} GB"
    devices = "∞" if not tariff.device_limit else str(tariff.device_limit)
    speed = "∞" if not tariff.speed_limit_mbps else f"{tariff.speed_limit_mbps} Mbps"
    
    status = "✅ Активен" if tariff.is_active else "❌ Неактивен"
    default_status = "⭐ Основной" if tariff.is_default else ""

    text = _(
        "admin_tariff_details",
        default="<b>📋 Информация о тарифе</b>\n\n"
                "<b>Название:</b> {name}\n"
                "<b>Описание:</b> {description}\n"
                "<b>Цена:</b> {price} {currency}\n"
                "<b>Длительность:</b> {duration} дней\n"
                "<b>Трафик:</b> {traffic}\n"
                "<b>Устройства:</b> {devices}\n"
                "<b>Скорость:</b> {speed}\n"
                "<b>Статус:</b> {status} {default_status}",
        name=tariff.name,
        description=tariff.description or "—",
        price=tariff.price,
        currency=tariff.currency,
        duration=tariff.duration_days,
        traffic=traffic,
        devices=devices,
        speed=speed,
        status=status,
        default_status=default_status
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_tariff_actions_keyboard(
                tariff_id, tariff.is_active, tariff.is_default, back_page, i18n, current_lang
            ),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_tariff_actions_keyboard(
                tariff_id, tariff.is_active, tariff.is_default, back_page, i18n, current_lang
            ),
            parse_mode="HTML"
        )
    await callback.answer()


# Обработчик просмотра тарифа из списка
@router.callback_query(F.data.startswith("admin_tariff:view:"))
async def view_tariff_callback(
    callback: types.CallbackQuery,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Обработка callback'а просмотра тарифа"""
    parts = callback.data.split(":")
    tariff_id = int(parts[2])
    back_page = int(parts[3])
    await view_tariff_handler(callback, i18n_data, settings, session, tariff_id, back_page)



# Создание тарифа - шаг 1: имя
async def create_tariff_start(
    callback: types.CallbackQuery,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings
):
    """Начало создания тарифа"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    text = _(
        "admin_create_tariff_step1_name",
        default="<b>➕ Создание тарифа</b>\n\n<b>Шаг 1 из 7:</b> Название тарифа\n\nВведите название тарифа (3-50 символов):"
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
    await state.set_state(AdminStates.waiting_for_tariff_name)


@router.message(AdminStates.waiting_for_tariff_name, F.text)
async def process_tariff_name(
    message: types.Message,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings
):
    """Обработка имени тарифа"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    name = message.text.strip()
    if not (3 <= len(name) <= 50):
        await message.answer(_(
            "admin_tariff_invalid_name",
            default="❌ Название должно содержать от 3 до 50 символов"
        ))
        return

    await state.update_data(tariff_name=name)

    text = _(
        "admin_create_tariff_step2_description",
        default="<b>➕ Создание тарифа</b>\n\n<b>Шаг 2 из 7:</b> Описание\n\n"
                "Название: <b>{name}</b>\n\nВведите описание тарифа или отправьте \"-\" чтобы пропустить:",
        name=name
    )

    await message.answer(
        text,
        reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_tariff_description)


@router.message(AdminStates.waiting_for_tariff_description, F.text)
async def process_tariff_description(
    message: types.Message,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings
):
    """Обработка описания тарифа"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    description = message.text.strip() if message.text.strip() != "-" else None
    await state.update_data(tariff_description=description)

    data = await state.get_data()
    text = _(
        "admin_create_tariff_step3_price",
        default="<b>➕ Создание тарифа</b>\n\n<b>Шаг 3 из 7:</b> Цена\n\n"
                "Название: <b>{name}</b>\nОписание: <b>{description}</b>\n\n"
                "Введите цену тарифа в рублях (например: 299 или 299.99):",
        name=data.get("tariff_name"),
        description=description or "—"
    )

    await message.answer(
        text,
        reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_tariff_price)


@router.message(AdminStates.waiting_for_tariff_price, F.text)
async def process_tariff_price(
    message: types.Message,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings
):
    """Обработка цены тарифа"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError("Price must be positive")
    except ValueError:
        await message.answer(_(
            "admin_tariff_invalid_price",
            default="❌ Введите корректную цену (положительное число)"
        ))
        return

    await state.update_data(tariff_price=price)

    data = await state.get_data()
    text = _(
        "admin_create_tariff_step4_duration",
        default="<b>➕ Создание тарифа</b>\n\n<b>Шаг 4 из 7:</b> Длительность\n\n"
                "Название: <b>{name}</b>\nЦена: <b>{price} RUB</b>\n\n"
                "Введите длительность подписки в днях (1-365):",
        name=data.get("tariff_name"),
        price=price
    )

    await message.answer(
        text,
        reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_tariff_duration)


@router.message(AdminStates.waiting_for_tariff_duration, F.text)
async def process_tariff_duration(
    message: types.Message,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings
):
    """Обработка длительности тарифа"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    try:
        duration = int(message.text.strip())
        if not (1 <= duration <= 365):
            raise ValueError("Duration out of range")
    except ValueError:
        await message.answer(_(
            "admin_tariff_invalid_duration",
            default="❌ Введите корректное количество дней (1-365)"
        ))
        return

    await state.update_data(tariff_duration=duration)

    data = await state.get_data()
    text = _(
        "admin_create_tariff_step5_traffic",
        default="<b>➕ Создание тарифа</b>\n\n<b>Шаг 5 из 7:</b> Лимит трафика\n\n"
                "Название: <b>{name}</b>\nЦена: <b>{price} RUB</b>\nДлительность: <b>{duration} дней</b>\n\n"
                "Введите лимит трафика в GB (например: 100) или \"-\" для безлимитного:",
        name=data.get("tariff_name"),
        price=data.get("tariff_price"),
        duration=duration
    )

    await message.answer(
        text,
        reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_tariff_traffic_limit)


@router.message(AdminStates.waiting_for_tariff_traffic_limit, F.text)
async def process_tariff_traffic(
    message: types.Message,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings
):
    """Обработка лимита трафика"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    traffic_text = message.text.strip()
    if traffic_text == "-":
        traffic_bytes = None
    else:
        try:
            traffic_gb = float(traffic_text)
            if traffic_gb <= 0:
                raise ValueError("Traffic must be positive")
            traffic_bytes = int(traffic_gb * 1024 * 1024 * 1024)
        except ValueError:
            await message.answer(_(
                "admin_tariff_invalid_traffic",
                default="❌ Введите корректное значение в GB или \"-\" для безлимитного"
            ))
            return

    await state.update_data(tariff_traffic=traffic_bytes)

    data = await state.get_data()
    traffic_display = "∞" if traffic_bytes is None else f"{traffic_bytes / (1024**3):.0f} GB"
    
    text = _(
        "admin_create_tariff_step6_devices",
        default="<b>➕ Создание тарифа</b>\n\n<b>Шаг 6 из 7:</b> Лимит устройств\n\n"
                "Название: <b>{name}</b>\nЦена: <b>{price} RUB</b>\nДлительность: <b>{duration} дней</b>\n"
                "Трафик: <b>{traffic}</b>\n\n"
                "Введите лимит устройств (например: 5) или \"-\" для безлимитного:",
        name=data.get("tariff_name"),
        price=data.get("tariff_price"),
        duration=data.get("tariff_duration"),
        traffic=traffic_display
    )

    await message.answer(
        text,
        reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_tariff_device_limit)


@router.message(AdminStates.waiting_for_tariff_device_limit, F.text)
async def process_tariff_devices(
    message: types.Message,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings
):
    """Обработка лимита устройств"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    devices_text = message.text.strip()
    if devices_text == "-":
        devices = None
    else:
        try:
            devices = int(devices_text)
            if devices <= 0:
                raise ValueError("Devices must be positive")
        except ValueError:
            await message.answer(_(
                "admin_tariff_invalid_devices",
                default="❌ Введите корректное число устройств или \"-\" для безлимитного"
            ))
            return

    await state.update_data(tariff_devices=devices)

    data = await state.get_data()
    traffic_display = "∞" if data.get("tariff_traffic") is None else f"{data.get('tariff_traffic') / (1024**3):.0f} GB"
    devices_display = "∞" if devices is None else str(devices)
    
    text = _(
        "admin_create_tariff_step7_speed",
        default="<b>➕ Создание тарифа</b>\n\n<b>Шаг 7 из 7:</b> Лимит скорости\n\n"
                "Название: <b>{name}</b>\nЦена: <b>{price} RUB</b>\nДлительность: <b>{duration} дней</b>\n"
                "Трафик: <b>{traffic}</b>\nУстройства: <b>{devices}</b>\n\n"
                "Введите лимит скорости в Mbps (например: 100) или \"-\" для без ограничений:",
        name=data.get("tariff_name"),
        price=data.get("tariff_price"),
        duration=data.get("tariff_duration"),
        traffic=traffic_display,
        devices=devices_display
    )

    await message.answer(
        text,
        reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_tariff_speed_limit)


@router.message(AdminStates.waiting_for_tariff_speed_limit, F.text)
async def process_tariff_speed(
    message: types.Message,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Обработка лимита скорости и создание тарифа"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error.")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    speed_text = message.text.strip()
    if speed_text == "-":
        speed = None
    else:
        try:
            speed = float(speed_text)
            if speed <= 0:
                raise ValueError("Speed must be positive")
        except ValueError:
            await message.answer(_(
                "admin_tariff_invalid_speed",
                default="❌ Введите корректное значение скорости в Mbps или \"-\" для без ограничений"
            ))
            return

    # Получаем все сохраненные данные
    data = await state.get_data()

    # Создаем тариф
    try:
        tariff_data = {
            "name": data["tariff_name"],
            "description": data.get("tariff_description"),
            "price": data["tariff_price"],
            "currency": "RUB",
            "duration_days": data["tariff_duration"],
            "traffic_limit_bytes": data.get("tariff_traffic"),
            "device_limit": data.get("tariff_devices"),
            "speed_limit_mbps": speed,
            "is_active": True,
            "is_default": False
        }

        new_tariff = await tariff_dal.create_tariff(session, tariff_data)
        await session.commit()

        logging.info(f"Created tariff '{new_tariff.name}' with ID {new_tariff.id}")

        # Форматирование для вывода
        traffic_display = "∞" if new_tariff.traffic_limit_bytes is None else f"{new_tariff.traffic_limit_bytes / (1024**3):.0f} GB"
        devices_display = "∞" if new_tariff.device_limit is None else str(new_tariff.device_limit)
        speed_display = "∞" if new_tariff.speed_limit_mbps is None else f"{new_tariff.speed_limit_mbps} Mbps"

        success_text = _(
            "admin_tariff_created_success",
            default="✅ <b>Тариф успешно создан!</b>\n\n"
                    "<b>Название:</b> {name}\n"
                    "<b>Описание:</b> {description}\n"
                    "<b>Цена:</b> {price} {currency}\n"
                    "<b>Длительность:</b> {duration} дней\n"
                    "<b>Трафик:</b> {traffic}\n"
                    "<b>Устройства:</b> {devices}\n"
                    "<b>Скорость:</b> {speed}",
            name=new_tariff.name,
            description=new_tariff.description or "—",
            price=new_tariff.price,
            currency=new_tariff.currency,
            duration=new_tariff.duration_days,
            traffic=traffic_display,
            devices=devices_display,
            speed=speed_display
        )

        await message.answer(
            success_text,
            reply_markup=get_tariff_management_keyboard(i18n, current_lang),
            parse_mode="HTML"
        )

        await state.clear()

    except Exception as e:
        logging.error(f"Error creating tariff: {e}")
        await message.answer(
            _("error_occurred_try_again", default="❌ Произошла ошибка. Попробуйте снова."),
            reply_markup=get_back_to_admin_panel_keyboard(current_lang, i18n)
        )
        await state.clear()


# Активация/деактивация тарифа
@router.callback_query(F.data.startswith("admin_tariff:activate:") | F.data.startswith("admin_tariff:deactivate:"))
async def toggle_tariff_status(
    callback: types.CallbackQuery,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Активация или деактивация тарифа"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    parts = callback.data.split(":")
    action = parts[1]  # activate or deactivate
    tariff_id = int(parts[2])
    back_page = int(parts[3])

    tariff = await tariff_dal.get_tariff_by_id(session, tariff_id)
    if not tariff:
        await callback.answer(_("admin_tariff_not_found", default="Тариф не найден"), show_alert=True)
        return

    # Меняем статус
    new_status = (action == "activate")
    await tariff_dal.update_tariff(session, tariff_id, {"is_active": new_status})
    await session.commit()

    logging.info(f"Tariff {tariff_id} {'activated' if new_status else 'deactivated'} by admin {callback.from_user.id}")

    await callback.answer(
        _("admin_tariff_status_changed", default="✅ Статус тарифа изменен"),
        show_alert=False
    )

    # Перезагружаем информацию о тарифе
    await view_tariff_handler(callback, i18n_data, settings, session, tariff_id, back_page)


# Установка дефолтного тарифа
@router.callback_query(F.data.startswith("admin_tariff:set_default:"))
async def set_default_tariff(
    callback: types.CallbackQuery,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Установка тарифа как основного"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    parts = callback.data.split(":")
    tariff_id = int(parts[2])
    back_page = int(parts[3])

    # Снимаем флаг default со всех тарифов
    all_tariffs = await tariff_dal.get_all_tariffs(session)
    for t in all_tariffs:
        if t.is_default:
            await tariff_dal.update_tariff(session, t.id, {"is_default": False})

    # Устанавливаем новый дефолтный
    await tariff_dal.update_tariff(session, tariff_id, {"is_default": True})
    await session.commit()

    logging.info(f"Tariff {tariff_id} set as default by admin {callback.from_user.id}")

    await callback.answer(
        _("admin_tariff_set_default_success", default="✅ Тариф установлен как основной"),
        show_alert=False
    )

    # Перезагружаем информацию о тарифе
    await view_tariff_handler(callback, i18n_data, settings, session, tariff_id, back_page)


# Подтверждение удаления тарифа
@router.callback_query(F.data.startswith("admin_tariff:delete_confirm:"))
async def confirm_delete_tariff(
    callback: types.CallbackQuery,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Подтверждение удаления тарифа"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    parts = callback.data.split(":")
    tariff_id = int(parts[2])
    back_page = int(parts[3])

    tariff = await tariff_dal.get_tariff_by_id(session, tariff_id)
    if not tariff:
        await callback.answer(_("admin_tariff_not_found", default="Тариф не найден"), show_alert=True)
        return

    text = _(
        "admin_tariff_delete_confirm",
        default="<b>⚠️ Подтверждение удаления</b>\n\n"
                "Вы действительно хотите удалить тариф <b>{name}</b>?\n\n"
                "Это действие необратимо!",
        name=tariff.name
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("yes_delete_button", default="✅ Да, удалить"),
            callback_data=f"admin_tariff:delete:{tariff_id}:{back_page}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("no_cancel_button", default="❌ Отмена"),
            callback_data=f"admin_tariff:view:{tariff_id}:{back_page}"
        )
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    await callback.answer()


# Удаление тарифа
@router.callback_query(F.data.startswith("admin_tariff:delete:"))
async def delete_tariff(
    callback: types.CallbackQuery,
    i18n_data: dict,
    settings: Settings,
    session: AsyncSession
):
    """Удаление тарифа"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n or not callback.message:
        await callback.answer("Error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)

    parts = callback.data.split(":")
    tariff_id = int(parts[2])
    back_page = int(parts[3])

    try:
        success = await tariff_dal.delete_tariff(session, tariff_id)
        if success:
            await session.commit()
            logging.info(f"Tariff {tariff_id} deleted by admin {callback.from_user.id}")
            await callback.answer(
                _("admin_tariff_deleted_success", default="✅ Тариф успешно удален"),
                show_alert=True
            )
            # Возвращаемся к списку тарифов
            await tariffs_list_handler(callback, i18n_data, settings, session, back_page)
        else:
            await callback.answer(
                _("admin_tariff_not_found", default="Тариф не найден"),
                show_alert=True
            )
    except Exception as e:
        logging.error(f"Error deleting tariff {tariff_id}: {e}")
        await callback.answer(
            _("error_occurred_try_again", default="❌ Произошла ошибка"),
            show_alert=True
        )