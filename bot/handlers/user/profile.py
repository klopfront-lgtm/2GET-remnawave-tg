import logging
from datetime import datetime, timezone
from typing import Optional, Union
from aiogram import Router, F, types
from aiogram.utils.text_decorations import html_decoration as hd
from sqlalchemy.ext.asyncio import AsyncSession

from db.dal import user_dal, balance_dal, discount_dal
from db.models import User
from bot.keyboards.inline.user_keyboards import (
    get_profile_keyboard,
    get_balance_history_keyboard,
)
from bot.services.subscription_service import SubscriptionService
from bot.middlewares.i18n import JsonI18n
from config.settings import Settings

router = Router(name="profile_router")


def format_currency(amount: float, currency: str = "RUB") -> str:
    """Форматирует сумму с валютой"""
    return f"{amount:.2f} {currency}"


def format_date(dt: Optional[datetime]) -> str:
    """Форматирует дату в читаемый вид"""
    if not dt:
        return "N/A"
    # Конвертируем в локальное время (UTC+3 для Москвы)
    return dt.strftime("%d.%m.%Y %H:%M")


def format_registration_date(dt: Optional[datetime]) -> str:
    """Форматирует дату регистрации"""
    if not dt:
        return "N/A"
    return dt.strftime("%d.%m.%Y")


async def build_profile_message(
    user: User,
    session: AsyncSession,
    subscription_service: SubscriptionService,
    i18n: JsonI18n,
    lang: str,
) -> str:
    """Строит текст сообщения профиля пользователя"""
    _ = lambda key, **kwargs: i18n.gettext(lang, key, **kwargs)
    
    # Основная информация
    user_display_name = hd.quote(user.first_name) if user.first_name else f"User {user.user_id}"
    username_display = f"@{hd.quote(user.username)}" if user.username else _("profile_no_username")
    
    lines = [
        f"👤 <b>{_('profile_title')}</b>\n",
        f"🆔 <b>ID:</b> <code>{user.user_id}</code>",
        f"👤 <b>{_('profile_name')}:</b> {user_display_name}",
        f"📱 <b>{_('profile_username')}:</b> {username_display}",
        f"📅 <b>{_('profile_registration_date')}:</b> {format_registration_date(user.registration_date)}",
        f"\n💰 <b>{_('profile_balance')}:</b> {format_currency(user.balance)}",
    ]
    
    # Информация о подписке
    lines.append(f"\n📋 <b>{_('profile_subscription_section')}:</b>")
    try:
        subscription_details = await subscription_service.get_active_subscription_details(
            session, user.user_id
        )
        
        if subscription_details and subscription_details.get("end_date"):
            end_date = subscription_details["end_date"]
            status = subscription_details.get("status_from_panel", "UNKNOWN")
            
            # Определяем статус
            now = datetime.now(timezone.utc)
            if end_date > now and status == "ACTIVE":
                status_emoji = "✅"
                status_text = _("profile_subscription_active")
            else:
                status_emoji = "❌"
                status_text = _("profile_subscription_inactive")
            
            days_left = max(0, (end_date - now).days)
            
            lines.append(f"{status_emoji} <b>{_('profile_subscription_status')}:</b> {status_text}")
            lines.append(f"📅 <b>{_('profile_subscription_end_date')}:</b> {format_date(end_date)}")
            lines.append(f"⏳ <b>{_('profile_subscription_days_left')}:</b> {days_left} {_('profile_days')}")
            
            # Информация о трафике
            traffic_used = subscription_details.get("traffic_used_bytes", 0) or 0
            traffic_limit = subscription_details.get("traffic_limit_bytes")
            
            if traffic_limit:
                traffic_used_gb = traffic_used / (1024**3)
                traffic_limit_gb = traffic_limit / (1024**3)
                traffic_percent = (traffic_used / traffic_limit * 100) if traffic_limit > 0 else 0
                lines.append(
                    f"📊 <b>{_('profile_traffic')}:</b> {traffic_used_gb:.2f} GB / {traffic_limit_gb:.2f} GB ({traffic_percent:.1f}%)"
                )
            else:
                traffic_used_gb = traffic_used / (1024**3)
                lines.append(f"📊 <b>{_('profile_traffic')}:</b> {traffic_used_gb:.2f} GB / {_('traffic_unlimited')}")
        else:
            lines.append(f"❌ {_('profile_no_active_subscription')}")
    except Exception as e:
        logging.error(f"Error getting subscription details for user {user.user_id}: {e}")
        lines.append(f"❌ {_('profile_subscription_error')}")
    
    # Информация о скидках
    try:
        discounts = await discount_dal.get_user_active_discounts(session, user.user_id)
        if discounts:
            lines.append(f"\n🎁 <b>{_('profile_discounts_section')}:</b>")
            for discount in discounts[:3]:  # Показываем максимум 3 скидки
                tariff_info = ""
                if discount.tariff_id:
                    tariff_info = f" ({_('profile_discount_for_tariff')} #{discount.tariff_id})"
                lines.append(f"  • {discount.discount_percentage}%{tariff_info}")
    except Exception as e:
        logging.error(f"Error getting discounts for user {user.user_id}: {e}")
    
    # История последних операций
    try:
        operations = await balance_dal.get_user_balance_history(session, user.user_id, limit=5)
        if operations:
            lines.append(f"\n💳 <b>{_('profile_recent_operations')}:</b>")
            for op in operations:
                op_emoji = "➕" if op.amount > 0 else "➖"
                op_type_str = _(f"profile_operation_{op.operation_type}", default=op.operation_type)
                amount_str = format_currency(abs(op.amount), op.currency)
                date_str = format_date(op.created_at)
                
                lines.append(f"{op_emoji} <b>{amount_str}</b> - {op_type_str}")
                if op.description:
                    lines.append(f"    <i>{hd.quote(op.description[:50])}</i>")
                lines.append(f"    <i>{date_str}</i>")
        else:
            lines.append(f"\n💳 <b>{_('profile_recent_operations')}:</b>")
            lines.append(f"  {_('profile_no_operations')}")
    except Exception as e:
        logging.error(f"Error getting balance history for user {user.user_id}: {e}")
        lines.append(f"\n💳 {_('profile_operations_error')}")
    
    return "\n".join(lines)


@router.callback_query(F.data == "main_action:profile")
async def show_profile(
    callback: types.CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    i18n_data: dict,
    subscription_service: SubscriptionService,
):
    """Отображает профиль пользователя"""
    user_id = callback.from_user.id
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    try:
        # Получаем данные пользователя
        user = await user_dal.get_user_by_id(session, user_id)
        if not user:
            await callback.answer(_("error_user_not_found"), show_alert=True)
            return
        
        # Строим сообщение профиля
        profile_text = await build_profile_message(
            user, session, subscription_service, i18n, current_lang
        )
        
        # Отправляем сообщение с клавиатурой
        keyboard = get_profile_keyboard(current_lang, i18n, settings)
        
        if callback.message:
            try:
                await callback.message.edit_text(
                    profile_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.warning(f"Failed to edit profile message: {e}")
                await callback.message.answer(
                    profile_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error showing profile for user {user_id}: {e}", exc_info=True)
        await callback.answer(_("error_occurred_try_again"), show_alert=True)


# Обработчик top_up_balance перенесен в balance_topup.py


@router.callback_query(F.data.startswith("profile_action:balance_history"))
async def show_balance_history(
    callback: types.CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    i18n_data: dict,
):
    """Показывает полную историю операций с балансом"""
    user_id = callback.from_user.id
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    
    if not i18n:
        await callback.answer("Service error", show_alert=True)
        return
    
    _ = lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs)
    
    # Извлекаем номер страницы из callback_data
    page = 0
    if ":" in callback.data:
        try:
            page = int(callback.data.split(":")[-1])
        except (ValueError, IndexError):
            page = 0
    
    page = max(0, page)
    per_page = 10
    offset = page * per_page
    
    try:
        # Получаем историю операций
        operations = await balance_dal.get_user_balance_history(
            session, user_id, limit=per_page, offset=offset
        )
        total_count = await balance_dal.get_user_balance_count(session, user_id)
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        
        if not operations and page == 0:
            await callback.answer(_("profile_no_operations"), show_alert=True)
            return
        
        # Формируем текст истории
        lines = [
            f"💳 <b>{_('profile_balance_history_title')}</b>",
            f"\n📄 {_('profile_page')} {page + 1} / {total_pages}\n"
        ]
        
        for op in operations:
            op_emoji = "➕" if op.amount > 0 else "➖"
            op_type_str = _(f"profile_operation_{op.operation_type}", default=op.operation_type)
            amount_str = format_currency(abs(op.amount), op.currency)
            date_str = format_date(op.created_at)
            
            lines.append(f"{op_emoji} <b>{amount_str}</b> - {op_type_str}")
            if op.description:
                lines.append(f"   <i>{hd.quote(op.description[:100])}</i>")
            lines.append(f"   <i>{date_str}</i>")
            lines.append("")  # Пустая строка для разделения
        
        history_text = "\n".join(lines)
        
        # Клавиатура с пагинацией
        keyboard = get_balance_history_keyboard(current_lang, i18n, page, total_pages)
        
        if callback.message:
            try:
                await callback.message.edit_text(
                    history_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.warning(f"Failed to edit history message: {e}")
                await callback.message.answer(
                    history_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error showing balance history for user {user_id}: {e}", exc_info=True)
        await callback.answer(_("error_occurred_try_again"), show_alert=True)