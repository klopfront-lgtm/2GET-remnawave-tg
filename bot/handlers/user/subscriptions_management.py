import logging
from datetime import datetime, timezone
from typing import Optional

from aiogram import Router, F, types
from aiogram.utils.text_decorations import html_decoration as hd
from sqlalchemy.ext.asyncio import AsyncSession

from db.dal import subscription_dal
from bot.services.subscription_service import SubscriptionService
from bot.keyboards.inline.subscriptions_keyboards import (
    get_subscriptions_list_keyboard,
    get_subscription_details_keyboard,
    get_delete_confirmation_keyboard,
)
from bot.middlewares.i18n import JsonI18n
from config.settings import Settings

router = Router(name="subscriptions_management_router")


def format_date(dt: Optional[datetime]) -> str:
    """Форматирует дату в читаемый вид"""
    if not dt:
        return "N/A"
    return dt.strftime("%d.%m.%Y")


def format_traffic(bytes_value: Optional[int]) -> str:
    """Форматирует трафик в GB"""
    if bytes_value is None:
        return "N/A"
    gb = bytes_value / (1024**3)
    return f"{gb:.2f} GB"


def get_traffic_progress_bar(used: int, limit: Optional[int], width: int = 10) -> str:
    """Создает прогресс-бар для трафика"""
    if limit is None or limit == 0:
        return "Безлимит"
    
    percentage = min(100, (used / limit) * 100) if limit > 0 else 0
    filled = int((percentage / 100) * width)
    empty = width - filled
    
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {percentage:.0f}%"


@router.callback_query(F.data == "profile_action:my_subscriptions")
async def show_subscriptions_list(
    callback: types.CallbackQuery,
    session: AsyncSession,
    subscription_service: SubscriptionService,
    i18n_data: dict,
    settings: Settings,
):
    """Показать список всех активных подписок пользователя"""
    user_id = callback.from_user.id
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        # Получаем все подписки пользователя
        subscriptions = await subscription_service.get_all_user_subscriptions_with_details(
            session, user_id
        )
        
        if not subscriptions:
            await callback.answer(
                _("no_active_subscriptions"),
                show_alert=True
            )
            return
        
        # Получить лимит подписок пользователя
        from db.dal import user_dal
        user = await user_dal.get_user_by_id(session, user_id)
        limit = user.max_subscriptions_limit if user else 3
        
        # Формируем сообщение
        title = _("my_subscriptions_title", count=len(subscriptions), limit=limit)
        lines = [
            f"{title}\n"
        ]
        
        for sub in subscriptions:
            icon = "⭐" if sub['is_primary'] else "📦"
            name = hd.quote(sub['name'])
            tariff = hd.quote(sub['tariff_name'])
            end_date = format_date(sub['end_date'])
            
            # Расчет оставшихся дней
            now = datetime.now(timezone.utc)
            if sub['end_date'] and sub['end_date'] > now:
                days_left = (sub['end_date'] - now).days
            else:
                days_left = 0
            
            lines.append(f"\n{icon} <b>{name}</b>")
            lines.append(f"▪️ Тариф: {tariff}")
            lines.append(f"▪️ Активна до: {end_date}")
            lines.append(f"▪️ Осталось: {days_left} дн.")
            
            # Трафик
            traffic_used = sub.get('traffic_used', 0) or 0
            traffic_limit = sub.get('traffic_limit')
            
            if traffic_limit:
                used_gb = format_traffic(traffic_used)
                limit_gb = format_traffic(traffic_limit)
                progress = get_traffic_progress_bar(traffic_used, traffic_limit)
                lines.append(f"▪️ Трафик: {used_gb} / {limit_gb} {progress}")
            else:
                used_gb = format_traffic(traffic_used)
                lines.append(f"▪️ Трафик: {used_gb} / Безлимит")
        
        message_text = "\n".join(lines)
        
        # Клавиатура со списком подписок
        keyboard = get_subscriptions_list_keyboard(
            subscriptions, current_lang, i18n
        )
        
        if callback.message:
            try:
                await callback.message.edit_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.warning(f"Failed to edit subscriptions list message: {e}")
                await callback.message.answer(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error showing subscriptions list for user {user_id}: {e}", exc_info=True)
        await callback.answer("Ошибка при загрузке списка подписок", show_alert=True)


@router.callback_query(F.data.startswith("subscription_details:"))
async def show_subscription_details(
    callback: types.CallbackQuery,
    session: AsyncSession,
    subscription_service: SubscriptionService,
    i18n_data: dict,
    settings: Settings,
):
    """Показать детальную информацию о конкретной подписке"""
    user_id = callback.from_user.id
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        subscription_id = int(callback.data.split(":")[1])
        
        # Получить подписку
        subscription = await subscription_dal.get_subscription_by_id_for_user(
            session, subscription_id, user_id
        )
        
        if not subscription:
            await callback.answer(_("subscription_not_found"), show_alert=True)
            return
        
        # Получить данные с панели для обновления трафика
        panel_data = {}
        try:
            panel_user = await subscription_service.panel_service.get_user_by_uuid(
                subscription.panel_user_uuid
            )
            if panel_user:
                panel_data = {
                    'traffic_used': panel_user.get('usedTrafficBytes', 0),
                    'config_link': panel_user.get('subscriptionUrl', 'N/A'),
                }
        except Exception as e:
            logging.error(f"Failed to get panel data for subscription {subscription_id}: {e}")
        
        # Формирование сообщения
        icon = "⭐" if subscription.is_primary else "📦"
        name = hd.quote(subscription.subscription_name or f"Подписка #{subscription_id}")
        tariff_name = hd.quote(subscription.tariff.name if subscription.tariff else "Unknown")
        
        start_date = format_date(subscription.start_date)
        end_date = format_date(subscription.end_date)
        
        # Расчет оставшихся дней
        now = datetime.now(timezone.utc)
        if subscription.end_date and subscription.end_date > now:
            days_left = (subscription.end_date - now).days
        else:
            days_left = 0
        
        lines = [
            f"{icon} <b>{name}</b>\n",
            f"▪️ Тариф: {tariff_name}",
            f"▪️ Активна с: {start_date}",
            f"▪️ Активна до: {end_date}",
            f"▪️ Осталось: {days_left} дн.\n",
            f"📊 <b>Использование:</b>",
        ]
        
        # Трафик
        traffic_used = panel_data.get('traffic_used', 0) or 0
        traffic_limit = subscription.get_effective_traffic_limit()
        
        if traffic_limit:
            used_gb = format_traffic(traffic_used)
            limit_gb = format_traffic(traffic_limit)
            percentage = min(100, (traffic_used / traffic_limit) * 100) if traffic_limit > 0 else 0
            lines.append(f"▪️ Трафик: {used_gb} / {limit_gb} ({percentage:.0f}%)")
        else:
            used_gb = format_traffic(traffic_used)
            lines.append(f"▪️ Трафик: {used_gb} / Безлимит")
        
        # Устройства
        device_limit = subscription.get_effective_device_limit()
        if device_limit:
            lines.append(f"▪️ Устройства: 1 / {device_limit}")
        else:
            lines.append(f"▪️ Устройства: Безлимит")
        
        # Ключ подключения
        config_link = panel_data.get('config_link', 'N/A')
        if config_link and config_link != 'N/A':
            lines.append(f"\n🔗 <b>Ключ подключения:</b>")
            lines.append(f"<code>{config_link}</code>")
        
        message_text = "\n".join(lines)
        
        # Клавиатура с действиями
        keyboard = get_subscription_details_keyboard(
            subscription_id=subscription_id,
            is_primary=subscription.is_primary,
            can_be_deleted=subscription.can_be_deleted,
            lang=current_lang,
            i18n=i18n
        )
        
        if callback.message:
            try:
                await callback.message.edit_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.warning(f"Failed to edit subscription details message: {e}")
                await callback.message.answer(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error showing subscription details for user {user_id}: {e}", exc_info=True)
        await callback.answer("Ошибка при загрузке деталей подписки", show_alert=True)


@router.callback_query(F.data.startswith("subscription_set_primary:"))
async def set_primary_subscription(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n_data: dict,
    settings: Settings,
):
    """Установить подписку как главную"""
    user_id = callback.from_user.id
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        subscription_id = int(callback.data.split(":")[1])
        
        success = await subscription_dal.set_primary_subscription(
            session, subscription_id, user_id
        )
        
        if success:
            await session.commit()
            await callback.answer("✅ Подписка установлена как главная")
            
            # Обновить отображение деталей
            await show_subscription_details(callback, session, 
                                          callback.bot.get("subscription_service"),
                                          i18n_data, settings)
        else:
            await callback.answer(_("subscription_set_as_primary_error"), show_alert=True)
        
    except Exception as e:
        logging.error(f"Error setting primary subscription for user {user_id}: {e}", exc_info=True)
        await session.rollback()
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("subscription_delete_confirm:"))
async def confirm_subscription_deletion(
    callback: types.CallbackQuery,
    session: AsyncSession,
    subscription_service: SubscriptionService,
    i18n_data: dict,
    settings: Settings,
):
    """Подтверждение удаления подписки"""
    user_id = callback.from_user.id
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        subscription_id = int(callback.data.split(":")[1])
        
        # Получить подписку
        subscription = await subscription_dal.get_subscription_by_id_for_user(
            session, subscription_id, user_id
        )
        
        if not subscription:
            await callback.answer(_("subscription_not_found"), show_alert=True)
            return
        
        if not subscription.can_be_deleted:
            await callback.answer(
                _("subscription_cannot_be_deleted"),
                show_alert=True
            )
            return
        
        # Формирование сообщения
        name = hd.quote(subscription.subscription_name or f"Подписка #{subscription_id}")
        
        lines = [
            f"⚠️ <b>Подтверждение удаления</b>\n",
            f"Вы действительно хотите удалить подписку:",
            f"<b>{name}</b>\n",
            f"ℹ️ Возврат средств не предусмотрен.\n",
            f"⚠️ <b>Это действие необратимо!</b>",
        ]
        
        message_text = "\n".join(lines)
        
        # Клавиатура подтверждения
        keyboard = get_delete_confirmation_keyboard(
            subscription_id, current_lang, i18n
        )
        
        if callback.message:
            try:
                await callback.message.edit_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.warning(f"Failed to edit delete confirmation message: {e}")
                await callback.message.answer(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error confirming subscription deletion for user {user_id}: {e}", exc_info=True)
        await callback.answer("Ошибка при подтверждении удаления", show_alert=True)


@router.callback_query(F.data.startswith("subscription_delete_confirmed:"))
async def delete_subscription_confirmed(
    callback: types.CallbackQuery,
    session: AsyncSession,
    subscription_service: SubscriptionService,
    i18n_data: dict,
    settings: Settings,
):
    """Фактическое удаление после подтверждения"""
    user_id = callback.from_user.id
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        subscription_id = int(callback.data.split(":")[1])
        
        success, message_key = await subscription_service.delete_subscription(
            session, subscription_id, user_id
        )
        
        if success:
            await session.commit()
            
            # Формирование сообщения об успехе
            lines = [
                "✅ <b>Подписка успешно удалена</b>\n",
                "\nВы можете приобрести новую подписку в любое время.",
            ]
            
            message_text = "\n".join(lines)
            
            # Вернуться к списку подписок
            await callback.answer(_("subscription_deleted_success"))
            
            if callback.message:
                try:
                    await callback.message.edit_text(
                        message_text,
                        parse_mode="HTML"
                    )
                except Exception:
                    await callback.message.answer(
                        message_text,
                        parse_mode="HTML"
                    )
            
            # Показать обновленный список
            await show_subscriptions_list(
                callback, session, subscription_service, i18n_data, settings
            )
        else:
            # Обработка ошибок через локализацию
            error_message = _(message_key, default="❌ Ошибка при удалении подписки")
            await callback.answer(error_message, show_alert=True)
        
    except ValueError as e:
        logging.error(f"Validation error deleting subscription for user {user_id}: {e}")
        await session.rollback()
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logging.error(f"Error deleting subscription for user {user_id}: {e}", exc_info=True)
        await session.rollback()
        await callback.answer("❌ Ошибка при удалении подписки", show_alert=True)