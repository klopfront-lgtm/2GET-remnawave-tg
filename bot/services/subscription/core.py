"""
Subscription Core Service

Основной сервис для управления жизненным циклом подписок.
Извлечен из SubscriptionService для следования принципу Single Responsibility.

Ответственность:
- Активация trial и платных подписок
- Продление подписок
- Управление подписками (получение деталей, удаление)
- Синхронизация с panel

Author: Architecture Improvement Phase 2
Date: 2024-11-24
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot

from config.settings import Settings
from bot.services.panel_api_service import PanelApiService
from bot.middlewares.i18n import JsonI18n
from bot.services.subscription.helpers import PanelUserHelper, SubscriptionActivationHelper
from db.models import User, Subscription, Tariff
from db.dal import (
    user_dal, 
    subscription_dal, 
    promo_code_dal, 
    payment_dal, 
    user_billing_dal, 
    tariff_dal
)


class SubscriptionCoreService:
    """
    Core service for subscription lifecycle management.
    
    Handles:
    - Trial subscription activation
    - Paid subscription activation
    - Subscription extension
    - Subscription deletion
    - Fetching subscription details
    - Panel synchronization
    
    Refactored from SubscriptionService to follow Single Responsibility Principle.
    """
    
    def __init__(
        self,
        settings: Settings,
        panel_service: PanelApiService,
        bot: Optional[Bot] = None,
        i18n: Optional[JsonI18n] = None,
    ):
        """
        Initialize SubscriptionCoreService.
        
        Args:
            settings: Application settings
            panel_service: Panel API service for panel interactions
            bot: Telegram bot instance (optional)
            i18n: I18n instance for localization (optional)
        """
        self.settings = settings
        self.panel_service = panel_service
        self.bot = bot
        self.i18n = i18n
        
        # Initialize helper classes
        self.panel_helper = PanelUserHelper(panel_service, settings)
        self.activation_helper = SubscriptionActivationHelper()
        
        logging.info("SubscriptionCoreService initialized")
    
    # ==================== Public API Methods ====================
    
    async def activate_trial_subscription(
        self,
        session: AsyncSession,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Activate trial subscription for new user.
        
        NOTE: Full implementation to be migrated from SubscriptionService.
        This is a placeholder showing the intended API.
        
        Args:
            session: Database session
            user_id: Telegram user ID
            
        Returns:
            Dict with trial activation details or error info:
            {
                "eligible": bool,
                "activated": bool,
                "end_date": datetime,
                "days": int,
                "traffic_gb": float,
                "panel_user_uuid": str,
                "panel_short_uuid": str,
                "subscription_url": str,
                "message_key": str  # for error messages
            }
        """
        logging.info(f"Trial activation requested for user {user_id}")
        
        # TODO: Migrate implementation from SubscriptionService.activate_trial_subscription()
        # Steps:
        # 1. Check if trial is enabled
        # 2. Verify user eligibility (no previous subscriptions)
        # 3. Get or create panel user
        # 4. Create trial subscription in DB
        # 5. Update panel with trial expiry
        # 6. Return activation details
        
        raise NotImplementedError(
            "activate_trial_subscription: Migration from SubscriptionService in progress. "
            "See docs/SUBSCRIPTION_SERVICE_REFACTORING.md for details."
        )
    
    async def activate_subscription(
        self,
        session: AsyncSession,
        user_id: int,
        months: int,
        payment_amount: float,
        payment_db_id: int,
        promo_code_id_from_payment: Optional[int] = None,
        provider: str = "yookassa",
        tariff_id: Optional[int] = None,
        keep_other_active: bool = True,
        subscription_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Activate paid subscription for user.
        
        NOTE: Full implementation to be migrated from SubscriptionService.
        This is a placeholder showing the intended API.
        
        Args:
            session: Database session
            user_id: Telegram user ID
            months: Number of months (if not using tariff)
            payment_amount: Payment amount
            payment_db_id: Payment record ID
            promo_code_id_from_payment: Promo code ID if used
            provider: Payment provider name
            tariff_id: Tariff ID (optional, for tariff-based subscriptions)
            keep_other_active: Whether to keep other active subscriptions
            subscription_name: Custom subscription name
            
        Returns:
            Dict with subscription details or None on failure:
            {
                "subscription_id": int,
                "end_date": datetime,
                "is_active": bool,
                "panel_user_uuid": str,
                "panel_short_uuid": str,
                "subscription_url": str,
                "applied_promo_bonus_days": int
            }
        """
        logging.info(
            f"Subscription activation requested for user {user_id}, "
            f"months={months}, tariff_id={tariff_id}"
        )
        
        # TODO: Migrate implementation from SubscriptionService.activate_subscription()
        # Steps:
        # 1. Validate user and tariff
        # 2. Check subscription limits
        # 3. Get or create panel user
        # 4. Calculate duration (from tariff or months)
        # 5. Apply promo code bonus if applicable
        # 6. Create subscription in DB
        # 7. Update panel
        # 8. Return subscription details
        
        raise NotImplementedError(
            "activate_subscription: Migration from SubscriptionService in progress. "
            "See docs/SUBSCRIPTION_SERVICE_REFACTORING.md for details."
        )
    
    async def extend_active_subscription_days(
        self,
        session: AsyncSession,
        user_id: int,
        bonus_days: int,
        reason: str = "bonus",
    ) -> Optional[datetime]:
        """
        Extend active subscription by specified number of days.
        
        NOTE: Full implementation to be migrated from SubscriptionService.
        This is a placeholder showing the intended API.
        
        Args:
            session: Database session
            user_id: Telegram user ID
            bonus_days: Number of days to add
            reason: Reason for extension (affects traffic limit)
            
        Returns:
            New end date or None on failure
        """
        logging.info(f"Subscription extension requested for user {user_id}: +{bonus_days} days ({reason})")
        
        # TODO: Migrate implementation from SubscriptionService.extend_active_subscription_days()
        
        raise NotImplementedError(
            "extend_active_subscription_days: Migration from SubscriptionService in progress. "
            "See docs/SUBSCRIPTION_SERVICE_REFACTORING.md for details."
        )
    
    async def get_active_subscription_details(
        self,
        session: AsyncSession,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about user's active subscription.
        
        Synchronizes with panel data and returns comprehensive subscription info.
        
        NOTE: Full implementation to be migrated from SubscriptionService.
        This is a placeholder showing the intended API.
        
        Args:
            session: Database session
            user_id: Telegram user ID
            
        Returns:
            Dict with subscription details or None:
            {
                "user_id": str,
                "end_date": datetime,
                "status_from_panel": str,
                "config_link": str,
                "traffic_limit_bytes": int,
                "traffic_used_bytes": int,
                "user_bot_username": str,
                "is_panel_data": bool,
                "max_devices": int
            }
        """
        logging.info(f"Fetching subscription details for user {user_id}")
        
        # TODO: Migrate implementation from SubscriptionService.get_active_subscription_details()
        
        raise NotImplementedError(
            "get_active_subscription_details: Migration from SubscriptionService in progress. "
            "See docs/SUBSCRIPTION_SERVICE_REFACTORING.md for details."
        )
    
    async def get_all_user_subscriptions_with_details(
        self,
        session: AsyncSession,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all active subscriptions for user with detailed information.
        
        NOTE: Full implementation to be migrated from SubscriptionService.
        This is a placeholder showing the intended API.
        
        Args:
            session: Database session
            user_id: Telegram user ID
            
        Returns:
            List of dicts with subscription details
        """
        logging.info(f"Fetching all subscriptions for user {user_id}")
        
        # TODO: Migrate implementation from SubscriptionService.get_all_user_subscriptions_with_details()
        
        raise NotImplementedError(
            "get_all_user_subscriptions_with_details: Migration from SubscriptionService in progress. "
            "See docs/SUBSCRIPTION_SERVICE_REFACTORING.md for details."
        )
    
    async def delete_subscription(
        self,
        session: AsyncSession,
        subscription_id: int,
        user_id: int,
        admin_override: bool = False
    ) -> Tuple[bool, str]:
        """
        Delete subscription without refund.
        
        NOTE: Full implementation to be migrated from SubscriptionService.
        This is a placeholder showing the intended API.
        
        Args:
            session: Database session
            subscription_id: Subscription ID to delete
            user_id: User ID (for permission check)
            admin_override: Admin override (ignores can_be_deleted flag)
            
        Returns:
            Tuple of (success, message_key)
        """
        logging.info(f"Subscription deletion requested: {subscription_id} for user {user_id}")
        
        # TODO: Migrate implementation from SubscriptionService.delete_subscription()
        
        raise NotImplementedError(
            "delete_subscription: Migration from SubscriptionService in progress. "
            "See docs/SUBSCRIPTION_SERVICE_REFACTORING.md for details."
        )
    
    # ==================== Utility Methods ====================
    
    async def has_active_subscription(
        self,
        session: AsyncSession,
        user_id: int
    ) -> bool:
        """
        Check if user currently has an active subscription.
        
        Returns True only if subscription is active and end_date is in the future.
        
        Args:
            session: Database session
            user_id: Telegram user ID
            
        Returns:
            True if user has active subscription, False otherwise
        """
        try:
            user_record = await user_dal.get_user_by_id(session, user_id)
            if not user_record or not user_record.panel_user_uuid:
                return False
                
            active_sub = await subscription_dal.get_active_subscription_by_user_id(
                session, user_id, user_record.panel_user_uuid
            )
            
            if not active_sub or not active_sub.end_date:
                return False
                
            return active_sub.is_active and active_sub.end_date > datetime.now(timezone.utc)
        except Exception as e:
            logging.error(f"Error checking active subscription for user {user_id}: {e}")
            return False
    
    async def has_had_any_subscription(
        self,
        session: AsyncSession,
        user_id: int
    ) -> bool:
        """
        Check if user has ever had any subscription (active or inactive).
        
        Args:
            session: Database session
            user_id: Telegram user ID
            
        Returns:
            True if user has had any subscription
        """
        return await subscription_dal.has_any_subscription_for_user(session, user_id)
    
    async def get_user_language(
        self,
        session: AsyncSession,
        user_id: int
    ) -> str:
        """
        Get user's preferred language or fallback to default.
        
        Args:
            session: Database session
            user_id: Telegram user ID
            
        Returns:
            Language code (e.g., 'ru', 'en')
        """
        user_record = await user_dal.get_user_by_id(session, user_id)
        return (
            user_record.language_code
            if user_record and user_record.language_code
            else self.settings.DEFAULT_LANGUAGE
        )


# NOTE: This is Phase 1 of SubscriptionService refactoring.
# Next steps:
# 1. Migrate all methods from SubscriptionService to SubscriptionCoreService
# 2. Create SubscriptionBillingService for billing operations
# 3. Create SubscriptionNotificationService for notifications
# 4. Update SubscriptionService to be a facade that delegates to specialized services
# 5. Update all handlers and factories to use new services
#
# See docs/SUBSCRIPTION_SERVICE_REFACTORING.md for full refactoring plan