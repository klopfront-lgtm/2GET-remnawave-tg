import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from config.settings import Settings
from db.dal import user_dal, subscription_dal
from bot.states.admin_states import AdminStates
from bot.services.subscription_service import SubscriptionService
from bot.middlewares.i18n import JsonI18n
from bot.filters.admin_filter import AdminFilter

router = Router(name="admin_subscription_limits_router")
router.callback_query.filter(AdminFilter())
router.message.filter(AdminFilter())


@router.callback_query(F.data.startswith("admin_user_set_sub_limit:"))
async def start_set_subscription_limit(
    callback: types.CallbackQuery,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings
):
    """Начало установки лимита подписок для пользователя"""
    try:
        user_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return
    
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await callback.answer("Language service error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    # Сохранить user_id в state
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.waiting_for_subscription_limit)
    
    prompt_text = _(
        "admin_set_subscription_limit_prompt",
        default="🔢 Установка лимита подписок для пользователя {user_id}\n\nВведите новый лимит подписок (1-100):",
        user_id=user_id
    )
    
    try:
        await callback.message.edit_text(prompt_text)
    except Exception:
        await callback.message.answer(prompt_text)
    
    await callback.answer()


@router.message(AdminStates.waiting_for_subscription_limit, F.text)
async def process_subscription_limit(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
    i18n_data: dict,
    settings: Settings
):
    """Обработка ввода лимита подписок"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        limit = int(message.text.strip())
        if not (1 <= limit <= 100):
            await message.answer(_(
                "admin_subscription_limit_invalid",
                default="❌ Лимит должен быть от 1 до 100"
            ))
            return
        
        state_data = await state.get_data()
        target_user_id = state_data.get("target_user_id")
        
        if not target_user_id:
            await message.answer("❌ Ошибка: пользователь не найден в state")
            await state.clear()
            return
        
        # Обновить лимит в БД
        user = await user_dal.get_user_by_id(session, target_user_id)
        
        if user:
            await user_dal.update_user(session, target_user_id, {"max_subscriptions_limit": limit})
            await session.commit()
            
            await message.answer(_(
                "admin_subscription_limit_set_success",
                default="✅ Лимит подписок для пользователя {user_id} установлен: {limit}",
                user_id=target_user_id,
                limit=limit
            ))
            
            logging.info(f"Admin {message.from_user.id} set subscription limit {limit} for user {target_user_id}")
        else:
            await message.answer(_(
                "admin_user_not_found",
                default="❌ Пользователь не найден"
            ))
            
    except ValueError:
        await message.answer(_(
            "admin_subscription_limit_invalid_format",
            default="❌ Введите целое число от 1 до 100"
        ))
        return
    except Exception as e:
        logging.error(f"Error setting subscription limit: {e}", exc_info=True)
        await session.rollback()
        await message.answer(_(
            "admin_subscription_limit_error",
            default="❌ Ошибка установки лимита подписок"
        ))
    finally:
        await state.clear()


@router.callback_query(F.data.startswith("admin_user_subscriptions:"))
async def show_user_subscriptions_admin(
    callback: types.CallbackQuery,
    session: AsyncSession,
    subscription_service: SubscriptionService,
    i18n_data: dict,
    settings: Settings
):
    """Просмотр всех подписок конкретного пользователя (админ)"""
    try:
        user_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return
    
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await callback.answer("Language service error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        # Получить все подписки пользователя
        subscriptions = await subscription_service.get_all_user_subscriptions_with_details(
            session, user_id
        )
        
        if not subscriptions:
            await callback.answer(_(
                "admin_user_no_subscriptions",
                default="📋 У пользователя нет активных подписок"
            ), show_alert=True)
            return
        
        # Форматирование списка подписок
        text_parts = [
            f"📊 <b>{_('admin_user_subscriptions_title', default='Подписки пользователя {user_id}', user_id=user_id)}</b>\n"
        ]
        
        for sub in subscriptions:
            status_emoji = "⭐" if sub.get('is_primary') else "📦"
            traffic_gb = sub.get('traffic_limit', 0) / (1024**3)
            traffic_used_gb = sub.get('traffic_used', 0) / (1024**3)
            
            sub_info = [
                f"{status_emoji} <b>{sub.get('name', 'N/A')}</b>",
                f"  • Тариф: {sub.get('tariff_name', 'N/A')}",
                f"  • Действует до: {sub.get('end_date').strftime('%Y-%m-%d %H:%M') if sub.get('end_date') else 'N/A'}",
                f"  • Трафик: {traffic_used_gb:.2f} / {traffic_gb:.2f} GB",
                f"  • Устройств: {sub.get('device_limit', 'N/A')}",
                f"  • Статус: {sub.get('panel_status', 'N/A')}",
            ]
            text_parts.append("\n".join(sub_info))
        
        subscriptions_text = "\n\n".join(text_parts)
        
        # Создать клавиатуру с подписками
        builder = InlineKeyboardBuilder()
        
        for sub in subscriptions:
            status_emoji = "⭐" if sub.get('is_primary') else "📦"
            builder.row(
                InlineKeyboardButton(
                    text=f"{status_emoji} {sub.get('name', 'N/A')}",
                    callback_data=f"admin_subscription_edit:{sub.get('subscription_id')}:{user_id}"
                )
            )
        
        # Кнопка назад
        builder.row(
            InlineKeyboardButton(
                text=_(key="admin_user_back_to_card_button", default="🔙 К карточке"),
                callback_data=f"user_action:refresh:{user_id}"
            )
        )
        
        try:
            await callback.message.edit_text(
                subscriptions_text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        except Exception:
            await callback.message.answer(
                subscriptions_text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error showing user subscriptions: {e}", exc_info=True)
        await callback.answer(_(
            "admin_user_subscriptions_error",
            default="❌ Ошибка загрузки подписок"
        ), show_alert=True)


@router.callback_query(F.data.startswith("admin_subscription_edit:"))
async def show_subscription_edit_menu(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n_data: dict,
    settings: Settings
):
    """Меню редактирования подписки"""
    try:
        parts = callback.data.split(":")
        subscription_id = int(parts[1])
        user_id = int(parts[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return
    
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await callback.answer("Language service error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        # Получить подписку
        subscription = await subscription_dal.get_subscription_by_id_for_user(
            session, subscription_id, user_id
        )
        
        if not subscription:
            await callback.answer(_(
                "admin_subscription_not_found",
                default="❌ Подписка не найдена"
            ), show_alert=True)
            return
        
        # Форматирование информации о подписке
        traffic_gb = subscription.get_effective_traffic_limit() / (1024**3)
        device_limit = subscription.get_effective_device_limit()
        
        text = _(
            "admin_subscription_edit_info",
            default="✏️ <b>Редактирование подписки</b>\n\n"
                    "📦 Название: {name}\n"
                    "📊 Тариф: {tariff}\n"
                    "📅 Действует до: {end_date}\n"
                    "💾 Лимит трафика: {traffic} GB\n"
                    "📱 Лимит устройств: {devices}\n"
                    "⭐ Главная: {is_primary}",
            name=subscription.subscription_name or "N/A",
            tariff=subscription.tariff.name if subscription.tariff else "N/A",
            end_date=subscription.end_date.strftime('%Y-%m-%d %H:%M') if subscription.end_date else "N/A",
            traffic=f"{traffic_gb:.2f}",
            devices=device_limit,
            is_primary="Да" if subscription.is_primary else "Нет"
        )
        
        # Получить клавиатуру редактирования
        from bot.keyboards.inline.admin_keyboards import get_subscription_edit_admin_keyboard
        keyboard = get_subscription_edit_admin_keyboard(subscription_id, user_id)
        
        try:
            await callback.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception:
            await callback.message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error showing subscription edit menu: {e}", exc_info=True)
        await callback.answer(_(
            "admin_subscription_edit_error",
            default="❌ Ошибка загрузки меню редактирования"
        ), show_alert=True)


@router.callback_query(F.data.startswith("admin_sub_set_traffic:"))
async def start_set_custom_traffic(
    callback: types.CallbackQuery,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings
):
    """Начало установки custom лимита трафика"""
    try:
        subscription_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return
    
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await callback.answer("Language service error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    await state.update_data(target_subscription_id=subscription_id)
    await state.set_state(AdminStates.waiting_for_traffic_limit)
    
    prompt_text = _(
        "admin_set_traffic_limit_prompt",
        default="📊 Установка лимита трафика\n\nВведите новый лимит трафика в GB (например: 100):"
    )
    
    try:
        await callback.message.edit_text(prompt_text)
    except Exception:
        await callback.message.answer(prompt_text)
    
    await callback.answer()


@router.message(AdminStates.waiting_for_traffic_limit, F.text)
async def process_custom_traffic_limit(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
    i18n_data: dict,
    settings: Settings
):
    """Обработка ввода лимита трафика"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        gb = float(message.text.strip())
        if gb <= 0 or gb > 10000:  # Max 10TB
            await message.answer(_(
                "admin_traffic_limit_invalid",
                default="❌ Лимит должен быть от 0 до 10000 GB"
            ))
            return
        
        bytes_limit = int(gb * 1024 * 1024 * 1024)
        
        state_data = await state.get_data()
        sub_id = state_data.get("target_subscription_id")
        
        if not sub_id:
            await message.answer("❌ Ошибка: подписка не найдена в state")
            await state.clear()
            return
        
        # Обновить через DAL
        await subscription_dal.update_subscription_params(
            session, sub_id, custom_traffic_limit=bytes_limit
        )
        await session.commit()
        
        await message.answer(_(
            "admin_traffic_limit_set_success",
            default="✅ Лимит трафика обновлен: {gb} GB",
            gb=gb
        ))
        
        logging.info(f"Admin {message.from_user.id} set traffic limit {gb}GB for subscription {sub_id}")
        
    except ValueError:
        await message.answer(_(
            "admin_traffic_limit_invalid_format",
            default="❌ Введите число (GB)"
        ))
        return
    except Exception as e:
        logging.error(f"Error setting traffic limit: {e}", exc_info=True)
        await session.rollback()
        await message.answer(_(
            "admin_traffic_limit_error",
            default="❌ Ошибка установки лимита трафика"
        ))
    finally:
        await state.clear()


@router.callback_query(F.data.startswith("admin_sub_set_devices:"))
async def start_set_custom_devices(
    callback: types.CallbackQuery,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings
):
    """Начало установки custom лимита устройств"""
    try:
        subscription_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return
    
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await callback.answer("Language service error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    await state.update_data(target_subscription_id=subscription_id)
    await state.set_state(AdminStates.waiting_for_device_limit)
    
    prompt_text = _(
        "admin_set_device_limit_prompt",
        default="📱 Установка лимита устройств\n\nВведите новый лимит устройств (1-10):"
    )
    
    try:
        await callback.message.edit_text(prompt_text)
    except Exception:
        await callback.message.answer(prompt_text)
    
    await callback.answer()


@router.message(AdminStates.waiting_for_device_limit, F.text)
async def process_custom_device_limit(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
    i18n_data: dict,
    settings: Settings
):
    """Обработка ввода лимита устройств"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        limit = int(message.text.strip())
        if not (1 <= limit <= 10):
            await message.answer(_(
                "admin_device_limit_invalid",
                default="❌ Лимит должен быть от 1 до 10"
            ))
            return
        
        state_data = await state.get_data()
        sub_id = state_data.get("target_subscription_id")
        
        if not sub_id:
            await message.answer("❌ Ошибка: подписка не найдена в state")
            await state.clear()
            return
        
        # Обновить через DAL
        await subscription_dal.update_subscription_params(
            session, sub_id, custom_device_limit=limit
        )
        await session.commit()
        
        await message.answer(_(
            "admin_device_limit_set_success",
            default="✅ Лимит устройств обновлен: {limit}",
            limit=limit
        ))
        
        logging.info(f"Admin {message.from_user.id} set device limit {limit} for subscription {sub_id}")
        
    except ValueError:
        await message.answer(_(
            "admin_device_limit_invalid_format",
            default="❌ Введите целое число от 1 до 10"
        ))
        return
    except Exception as e:
        logging.error(f"Error setting device limit: {e}", exc_info=True)
        await session.rollback()
        await message.answer(_(
            "admin_device_limit_error",
            default="❌ Ошибка установки лимита устройств"
        ))
    finally:
        await state.clear()


@router.callback_query(F.data.startswith("admin_sub_set_name:"))
async def start_set_subscription_name(
    callback: types.CallbackQuery,
    state: FSMContext,
    i18n_data: dict,
    settings: Settings
):
    """Начало установки названия подписки"""
    try:
        subscription_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return
    
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await callback.answer("Language service error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    await state.update_data(target_subscription_id=subscription_id)
    await state.set_state(AdminStates.waiting_for_subscription_name)
    
    prompt_text = _(
        "admin_set_subscription_name_prompt",
        default="✏️ Установка названия подписки\n\nВведите новое название (до 100 символов):"
    )
    
    try:
        await callback.message.edit_text(prompt_text)
    except Exception:
        await callback.message.answer(prompt_text)
    
    await callback.answer()


@router.message(AdminStates.waiting_for_subscription_name, F.text)
async def process_subscription_name(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
    i18n_data: dict,
    settings: Settings
):
    """Обработка ввода названия подписки"""
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await message.reply("Language service error")
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        name = message.text.strip()
        if not name or len(name) > 100:
            await message.answer(_(
                "admin_subscription_name_invalid",
                default="❌ Название должно быть от 1 до 100 символов"
            ))
            return
        
        state_data = await state.get_data()
        sub_id = state_data.get("target_subscription_id")
        
        if not sub_id:
            await message.answer("❌ Ошибка: подписка не найдена в state")
            await state.clear()
            return
        
        # Обновить через DAL
        await subscription_dal.update_subscription_params(
            session, sub_id, subscription_name=name
        )
        await session.commit()
        
        await message.answer(_(
            "admin_subscription_name_set_success",
            default="✅ Название подписки обновлено: {name}",
            name=name
        ))
        
        logging.info(f"Admin {message.from_user.id} set name '{name}' for subscription {sub_id}")
        
    except Exception as e:
        logging.error(f"Error setting subscription name: {e}", exc_info=True)
        await session.rollback()
        await message.answer(_(
            "admin_subscription_name_error",
            default="❌ Ошибка установки названия подписки"
        ))
    finally:
        await state.clear()


@router.callback_query(F.data.startswith("admin_sub_delete:"))
async def delete_subscription_admin(
    callback: types.CallbackQuery,
    session: AsyncSession,
    subscription_service: SubscriptionService,
    i18n_data: dict,
    settings: Settings
):
    """Принудительное удаление подписки (admin override)"""
    try:
        subscription_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return
    
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    if not i18n:
        await callback.answer("Language service error", show_alert=True)
        return
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        # Получить подписку для определения user_id
        subscription = await session.get(subscription_dal.Subscription, subscription_id)
        
        if not subscription:
            await callback.answer(_(
                "admin_subscription_not_found",
                default="❌ Подписка не найдена"
            ), show_alert=True)
            return
        
        user_id = subscription.user_id
        
        # Удалить с admin_override=True
        success, message_key = await subscription_service.delete_subscription(
            session, subscription_id, user_id, admin_override=True
        )
        
        if success:
            await session.commit()
            
            result_text = _(
                "admin_subscription_deleted_success",
                default="✅ Подписка {subscription_id} удалена администратором",
                subscription_id=subscription_id
            )
            
            await callback.answer(result_text, show_alert=True)
            
            logging.info(f"Admin {callback.from_user.id} deleted subscription {subscription_id} for user {user_id}")
            
            # Вернуться к списку подписок пользователя
            await show_user_subscriptions_admin(
                callback, session, subscription_service, i18n_data, settings
            )
        else:
            await callback.answer(_(
                f"admin_subscription_delete_{message_key}",
                default=f"❌ Ошибка: {message_key}"
            ), show_alert=True)
            
    except Exception as e:
        logging.error(f"Error deleting subscription: {e}", exc_info=True)
        await session.rollback()
        await callback.answer(_(
            "admin_subscription_delete_error",
            default="❌ Ошибка удаления подписки"
        ), show_alert=True)