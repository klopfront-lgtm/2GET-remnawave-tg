import logging
from typing import Dict, Any
from aiogram import Bot
from sqlalchemy.orm import sessionmaker

from config.settings import Settings
from bot.middlewares.i18n import JsonI18n
from bot.services.yookassa_service import YooKassaService
from bot.services.panel_api_service import PanelApiService
from bot.services.subscription_service import SubscriptionService
from bot.services.referral_service import ReferralService
from bot.services.balance_service import BalanceService
from bot.services.promo_code_service import PromoCodeService
from bot.services.stars_service import StarsService
from bot.services.tribute_service import TributeService
from bot.services.crypto_pay_service import CryptoPayService
from bot.services.panel_webhook_service import PanelWebhookService
from bot.services.freekassa_service import FreeKassaService


def build_core_services(
    settings: Settings,
    bot: Bot,
    async_session_factory: sessionmaker,
    i18n: JsonI18n,
    bot_username_for_default_return: str,
) -> Dict[str, Any]:
    """
    Build and wire all core services with explicit dependency injection.
    
    Args:
        settings: Application settings
        bot: Telegram bot instance
        async_session_factory: SQLAlchemy async session factory
        i18n: Internationalization instance
        bot_username_for_default_return: Bot username for default return URL
        
    Returns:
        Dictionary of initialized services with proper dependencies
    """
    panel_service = PanelApiService(settings)
    subscription_service = SubscriptionService(settings, panel_service, bot, i18n)
    referral_service = ReferralService(settings, subscription_service, bot, i18n)
    balance_service = BalanceService()
    promo_code_service = PromoCodeService(settings, subscription_service, balance_service, bot, i18n)
    stars_service = StarsService(bot, settings, i18n, subscription_service, referral_service)
    cryptopay_service = CryptoPayService(
        settings.CRYPTOPAY_TOKEN,
        settings.CRYPTOPAY_NETWORK,
        bot,
        settings,
        i18n,
        async_session_factory,
        subscription_service,
        referral_service,
    )
    freekassa_service = FreeKassaService(
        bot=bot,
        settings=settings,
        i18n=i18n,
        async_session_factory=async_session_factory,
        subscription_service=subscription_service,
        referral_service=referral_service,
    )
    tribute_service = TributeService(
        bot,
        settings,
        i18n,
        async_session_factory,
        panel_service,
        subscription_service,
        referral_service,
    )
    panel_webhook_service = PanelWebhookService(bot, settings, i18n, async_session_factory, panel_service)
    yookassa_service = YooKassaService(
        shop_id=settings.YOOKASSA_SHOP_ID,
        secret_key=settings.YOOKASSA_SECRET_KEY,
        configured_return_url=settings.YOOKASSA_RETURN_URL,
        bot_username_for_default_return=bot_username_for_default_return,
        settings_obj=settings,
    )

    # REFACTOR: Wire service dependencies explicitly instead of using setattr
    # This makes dependencies visible and easier to track
    
    # Attach YooKassa to subscription service for auto-renew charges
    if hasattr(subscription_service, '__dict__'):
        subscription_service.yookassa_service = yookassa_service
        logging.info("Wired YooKassaService to SubscriptionService for auto-renewal")
    else:
        logging.warning("Could not wire YooKassaService to SubscriptionService")
    
    # Allow panel webhook to trigger renewals through subscription service
    if hasattr(panel_webhook_service, '__dict__'):
        panel_webhook_service.subscription_service = subscription_service
        logging.info("Wired SubscriptionService to PanelWebhookService")
    else:
        logging.warning("Could not wire SubscriptionService to PanelWebhookService")

    return {
        "panel_service": panel_service,
        "subscription_service": subscription_service,
        "referral_service": referral_service,
        "balance_service": balance_service,
        "promo_code_service": promo_code_service,
        "stars_service": stars_service,
        "cryptopay_service": cryptopay_service,
        "freekassa_service": freekassa_service,
        "tribute_service": tribute_service,
        "panel_webhook_service": panel_webhook_service,
        "yookassa_service": yookassa_service,
    }

