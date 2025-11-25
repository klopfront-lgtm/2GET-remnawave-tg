import logging
import json
from typing import Optional

from aiogram import Bot
from aiohttp import web
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from aiocryptopay import AioCryptoPay, Networks
from aiocryptopay.models.update import Update

from config.settings import Settings
from bot.middlewares.i18n import JsonI18n
from bot.services.subscription_service import SubscriptionService
from bot.services.referral_service import ReferralService
from bot.keyboards.inline.user_keyboards import get_connect_and_main_keyboard
from bot.services.notification_service import NotificationService
from bot.services.balance_service import BalanceService
from db.dal import payment_dal, user_dal
from bot.utils.text_sanitizer import sanitize_display_name, username_for_display


class CryptoPayService:
    def __init__(
        self,
        token: Optional[str],
        network: str,
        bot: Bot,
        settings: Settings,
        i18n: JsonI18n,
        async_session_factory: sessionmaker,
        subscription_service: SubscriptionService,
        referral_service: ReferralService,
    ):
        self.bot = bot
        self.settings = settings
        self.i18n = i18n
        self.async_session_factory = async_session_factory
        self.subscription_service = subscription_service
        self.referral_service = referral_service
        if token:
            net = Networks.TEST_NET if str(network).lower() == "testnet" else Networks.MAIN_NET
            self.client = AioCryptoPay(token=token, network=net)
            self.client.register_pay_handler(self._invoice_paid_handler)
            self.configured = True
        else:
            logging.warning("CryptoPay token not provided. CryptoPay disabled")
            self.client = None
            self.configured = False

    async def close(self):
        """Close underlying AioCryptoPay session if initialized."""
        if self.client:
            try:
                await self.client.close()
                logging.info("CryptoPay client session closed.")
            except Exception as e:
                logging.warning(f"Failed to close CryptoPay client: {e}")

    async def create_invoice(
        self,
        session: AsyncSession,
        user_id: int,
        months: int,
        amount: float,
        description: str,
        payment_type: str = "subscription",
    ) -> Optional[str]:
        """
        Создать инвойс CryptoPay.
        
        Args:
            session: Сессия БД
            user_id: ID пользователя
            months: Количество месяцев (для subscription)
            amount: Сумма платежа
            description: Описание
            payment_type: Тип платежа ("subscription" или "balance")
            
        Returns:
            URL инвойса или None при ошибке
        """
        if not self.configured or not self.client:
            logging.error("CryptoPayService not configured")
            return None

        # Create pending payment in DB and commit to persist
        try:
            payment_record = await payment_dal.create_payment_record(
                session,
                {
                    "user_id": user_id,
                    "amount": float(amount),
                    "currency": self.settings.CRYPTOPAY_ASSET,
                    "status": "pending_cryptopay",
                    "description": description,
                    "subscription_duration_months": months if payment_type == "subscription" else 0,
                    "provider": "cryptopay",
                },
            )
            await session.commit()
        except Exception as e_db_create:
            await session.rollback()
            logging.error(
                f"Failed to create cryptopay payment record for user {user_id}: {e_db_create}",
                exc_info=True,
            )
            return None
        payload = json.dumps({
            "user_id": str(user_id),
            "subscription_months": str(months),
            "payment_db_id": str(payment_record.payment_id),
            "payment_type": payment_type,
        })
        
        logging.info(f"Creating CryptoPay invoice with type: {payment_type}")
        try:
            invoice = await self.client.create_invoice(
                amount=amount,
                currency_type=self.settings.CRYPTOPAY_CURRENCY_TYPE,
                fiat=self.settings.CRYPTOPAY_ASSET if self.settings.CRYPTOPAY_CURRENCY_TYPE == "fiat" else None,
                asset=self.settings.CRYPTOPAY_ASSET if self.settings.CRYPTOPAY_CURRENCY_TYPE == "crypto" else None,
                description=description,
                payload=payload,
            )
            try:
                await payment_dal.update_provider_payment_and_status(
                    session,
                    payment_record.payment_id,
                    str(invoice.invoice_id),
                    str(invoice.status),
                )
                await session.commit()
            except Exception as e_db_update:
                await session.rollback()
                logging.error(
                    f"Failed to update cryptopay payment record {payment_record.payment_id}: {e_db_update}",
                    exc_info=True,
                )
                return None
            return invoice.bot_invoice_url
        except Exception as e:
            logging.error(f"CryptoPay invoice creation failed: {e}", exc_info=True)
            return None

    async def _invoice_paid_handler(self, update: Update, app: web.Application):
        """
        Handle CryptoPay webhook for invoice payment.
        
        SECURITY NOTE: CryptoPay library (aiocryptopay) handles signature verification internally.
        Additional security measures:
        - Rate limiting should be implemented at reverse proxy level (nginx/caddy)
        - Consider IP whitelist for CryptoPay webhook endpoints if their IPs are known
        - All webhook data is validated before processing
        """
        invoice = update.payload
        if not invoice.payload:
            logging.warning("CryptoPay webhook without payload - possible malformed request")
            return
        
        # SECURITY: Validate and parse payload with comprehensive error handling
        try:
            meta = json.loads(invoice.payload)
            user_id = int(meta["user_id"])
            payment_type = meta.get("payment_type", "subscription")
            months = int(meta["subscription_months"])
            payment_db_id = int(meta["payment_db_id"])
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logging.error(f"SECURITY: Invalid CryptoPay payload structure: {e}", exc_info=True)
            return
        except Exception as e:
            logging.error(f"SECURITY: Unexpected error parsing CryptoPay payload: {e}", exc_info=True)
            return
        
        logging.info(f"Processing CryptoPay payment type: {payment_type} for user {user_id}")

        async_session_factory: sessionmaker = app["async_session_factory"]
        bot: Bot = app["bot"]
        settings: Settings = app["settings"]
        i18n: JsonI18n = app["i18n"]
        subscription_service: SubscriptionService = app["subscription_service"]
        referral_service: ReferralService = app["referral_service"]

        async with async_session_factory() as session:
            try:
                await payment_dal.update_provider_payment_and_status(
                    session,
                    payment_db_id,
                    str(invoice.invoice_id),
                    "succeeded",
                )
                
                # Обработка пополнения баланса
                if payment_type == "balance":
                    balance_service = BalanceService()
                    await balance_service.deposit(
                        session=session,
                        user_id=user_id,
                        amount=float(invoice.amount),
                        description="Пополнение баланса через CryptoPay",
                        currency=invoice.asset or settings.CRYPTOPAY_ASSET
                    )
                    await session.commit()
                    
                    db_user = await user_dal.get_user_by_id(session, user_id)
                    lang = db_user.language_code if db_user and db_user.language_code else settings.DEFAULT_LANGUAGE
                    _ = lambda k, **kw: i18n.gettext(lang, k, **kw)
                    
                    new_balance = await balance_service.get_balance(session, user_id)
                    text = _(
                        "balance_deposit_success",
                        default=f"✅ Баланс успешно пополнен на {invoice.amount} {invoice.asset}!\n\n"
                               f"Текущий баланс: {new_balance} {invoice.asset}"
                    )
                    
                    try:
                        await bot.send_message(user_id, text, parse_mode="HTML")
                    except Exception as e:
                        logging.error(f"Failed to send CryptoPay balance deposit message: {e}")
                    
                    logging.info(f"CryptoPay balance deposit successful for user {user_id}: +{invoice.amount}")
                    return
                
                # Обработка подписки (старая логика)
                activation = await subscription_service.activate_subscription(
                    session,
                    user_id,
                    months,
                    float(invoice.amount),
                    payment_db_id,
                    provider="cryptopay",
                )
                referral_bonus = await referral_service.apply_referral_bonuses_for_payment(
                    session,
                    user_id,
                    months,
                    current_payment_db_id=payment_db_id,
                    skip_if_active_before_payment=False,
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                logging.error(f"Failed to process CryptoPay invoice: {e}", exc_info=True)
                return

            db_user = await user_dal.get_user_by_id(session, user_id)
            # Use DB language for user-facing messages
            lang = db_user.language_code if db_user and db_user.language_code else settings.DEFAULT_LANGUAGE
            _ = lambda k, **kw: i18n.gettext(lang, k, **kw)

            config_link = activation.get("subscription_url") or _("config_link_not_available")
            final_end = activation.get("end_date")
            applied_days = 0
            if referral_bonus and referral_bonus.get("referee_new_end_date"):
                final_end = referral_bonus["referee_new_end_date"]
                applied_days = referral_bonus.get("referee_bonus_applied_days", 0)

            if applied_days:
                inviter_name_display = _("friend_placeholder")
                if db_user and db_user.referred_by_id:
                    inviter = await user_dal.get_user_by_id(session, db_user.referred_by_id)
                    if inviter:
                        safe_name = sanitize_display_name(inviter.first_name) if inviter.first_name else None
                        if safe_name:
                            inviter_name_display = safe_name
                        elif inviter.username:
                            inviter_name_display = username_for_display(inviter.username, with_at=False)
                text = _("payment_successful_with_referral_bonus_full",
                         months=months,
                         base_end_date=activation["end_date"].strftime('%Y-%m-%d'),
                         bonus_days=applied_days,
                         final_end_date=final_end.strftime('%Y-%m-%d'),
                         inviter_name=inviter_name_display,
                         config_link=config_link)
            else:
                text = _("payment_successful_full",
                         months=months,
                         end_date=final_end.strftime('%Y-%m-%d'),
                         config_link=config_link)

            markup = get_connect_and_main_keyboard(
                lang, i18n, settings, config_link, preserve_message=True
            )
            try:
                await bot.send_message(
                    user_id,
                    text,
                    reply_markup=markup,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except Exception as e:
                logging.error(f"Failed to send CryptoPay success message: {e}")

            # Send notification about payment
            try:
                notification_service = NotificationService(bot, settings, i18n)
                user = await user_dal.get_user_by_id(session, user_id)
                await notification_service.notify_payment_received(
                    user_id=user_id,
                    amount=float(invoice.amount),
                    currency=invoice.asset or settings.DEFAULT_CURRENCY_SYMBOL,
                    months=months,
                    payment_provider="crypto_pay",
                    username=user.username if user else None
                )
            except Exception as e:
                logging.error(f"Failed to send crypto_pay payment notification: {e}")

    async def webhook_route(self, request: web.Request) -> web.Response:
        """
        Handle CryptoPay webhook route.
        
        SECURITY NOTE:
        - CryptoPay library performs signature verification automatically
        - Consider implementing rate limiting at reverse proxy level
        - Monitor for unusual patterns in webhook calls
        """
        if not self.configured or not self.client:
            logging.warning("SECURITY: CryptoPay webhook called but service not configured")
            return web.Response(status=503, text="cryptopay_disabled")
        
        try:
            return await self.client.get_updates(request)
        except Exception as e:
            logging.error(f"SECURITY: Error processing CryptoPay webhook: {e}", exc_info=True)
            return web.Response(status=500, text="internal_error")


async def cryptopay_webhook_route(request: web.Request) -> web.Response:
    """
    AIOHTTP route handler for CryptoPay webhooks.
    
    SECURITY CONSIDERATIONS:
    - Signature verification is handled by aiocryptopay library
    - Implement rate limiting at reverse proxy (nginx/caddy)
    - Consider IP whitelist if CryptoPay provides their webhook IPs
    """
    service: CryptoPayService = request.app["cryptopay_service"]
    return await service.webhook_route(request)
