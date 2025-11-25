from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup
from typing import Dict, List


def get_subscriptions_list_keyboard(
    subscriptions: List[Dict],
    lang: str,
    i18n
) -> InlineKeyboardMarkup:
    """Клавиатура со списком подписок"""
    _ = lambda key, **kwargs: i18n.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()
    
    for sub in subscriptions:
        icon = "⭐" if sub['is_primary'] else "📦"
        name = sub['name']
        end_date_str = sub['end_date'].strftime('%d.%m.%Y') if sub['end_date'] else 'N/A'
        
        text = f"{icon} {name} - до {end_date_str}"
        
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"subscription_details:{sub['subscription_id']}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text=_("back_to_profile_button", default="◀️ К профилю"),
            callback_data="main_action:profile"
        )
    )
    
    return builder.as_markup()


def get_subscription_details_keyboard(
    subscription_id: int,
    is_primary: bool,
    can_be_deleted: bool,
    lang: str,
    i18n
) -> InlineKeyboardMarkup:
    """Клавиатура деталей подписки с действиями"""
    _ = lambda key, **kwargs: i18n.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()
    
    # Кнопка "Сделать главной" только если подписка не главная
    if not is_primary:
        builder.row(
            InlineKeyboardButton(
                text=_("set_as_primary_button", default="⭐ Сделать главной"),
                callback_data=f"subscription_set_primary:{subscription_id}"
            )
        )
    
    # Кнопка удаления только если подписку можно удалить
    if can_be_deleted:
        builder.row(
            InlineKeyboardButton(
                text=_("delete_subscription_button", default="🗑 Удалить подписку"),
                callback_data=f"subscription_delete_confirm:{subscription_id}"
            )
        )
    
    # Кнопка возврата к списку
    builder.row(
        InlineKeyboardButton(
            text=_("back_button", default="◀️ Назад"),
            callback_data="profile_action:my_subscriptions"
        )
    )
    
    return builder.as_markup()


def get_delete_confirmation_keyboard(
    subscription_id: int,
    lang: str,
    i18n
) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления подписки"""
    _ = lambda key, **kwargs: i18n.gettext(lang, key, **kwargs)
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=_("yes_delete_button", default="✅ Да, удалить"),
            callback_data=f"subscription_delete_confirmed:{subscription_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("cancel_button", default="❌ Отмена"),
            callback_data=f"subscription_details:{subscription_id}"
        )
    )
    
    return builder.as_markup()