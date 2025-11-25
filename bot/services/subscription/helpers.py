"""
Subscription Helper Classes

Helper классы для subscription операций, извлеченные из SubscriptionService
для улучшения организации кода и следования принципу Single Responsibility.

Author: Architecture Improvement Phase 2
Date: 2024-11-24
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from config.settings import Settings
from bot.services.panel_api_service import PanelApiService
from bot.utils.date_utils import add_months
from db.models import Tariff


class PanelUserHelper:
    """
    Helper class for panel user management operations.
    
    Extracted from SubscriptionService to improve code organization.
    Handles creation and management of panel users.
    """
    
    def __init__(self, panel_service: PanelApiService, settings: Settings):
        """
        Initialize PanelUserHelper.
        
        Args:
            panel_service: PanelApiService instance for API interactions
            settings: Settings instance with configuration
        """
        self.panel_service = panel_service
        self.settings = settings
    
    async def create_panel_user(
        self,
        username_on_panel: str,
        telegram_id: int,
        description: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new user on the panel with standard configuration.
        
        Args:
            username_on_panel: Username for the panel user
            telegram_id: Telegram user ID
            description: User description (typically Telegram profile info)
            
        Returns:
            Panel user data dict or None on failure
        """
        creation_response = await self.panel_service.create_panel_user(
            username_on_panel=username_on_panel,
            telegram_id=telegram_id,
            description=description,
            specific_squad_uuids=self.settings.parsed_user_squad_uuids,
            external_squad_uuid=self.settings.parsed_user_external_squad_uuid,
            default_traffic_limit_bytes=self.settings.user_traffic_limit_bytes,
            default_traffic_limit_strategy=self.settings.USER_TRAFFIC_STRATEGY,
        )
        
        if (
            creation_response
            and not creation_response.get("error")
            and creation_response.get("response")
        ):
            return creation_response.get("response")
        
        logging.error(
            f"Panel user creation failed for telegram_id {telegram_id}: {creation_response}"
        )
        return None


class SubscriptionActivationHelper:
    """
    Helper class for subscription activation logic.
    
    Extracted from SubscriptionService to simplify main class.
    Contains utility methods for subscription calculations and validations.
    """
    
    @staticmethod
    def calculate_duration_days(
        tariff: Optional[Tariff],
        months: int,
        start_date: datetime,
    ) -> int:
        """
        Calculate total subscription duration in days.
        
        Args:
            tariff: Tariff model (if using tariff-based subscription)
            months: Number of months (if using month-based subscription)
            start_date: Subscription start date
            
        Returns:
            Total duration in days
        """
        if tariff:
            # Use tariff duration
            return tariff.duration_days
        else:
            # Calculate from months
            end_after_months = add_months(start_date, months)
            return (end_after_months - start_date).days
    
    @staticmethod
    def should_apply_main_traffic_limit(reason: str) -> bool:
        """
        Determine if main traffic limit should be applied based on reason.
        
        For admin bonuses, promo codes, and referrals - use main traffic limit.
        Otherwise (e.g., trial) - use trial traffic limit.
        
        Args:
            reason: Reason for subscription activation/extension
            
        Returns:
            True if main traffic limit should be applied
        """
        reason_lower = (reason or "").lower()
        return any(
            keyword in reason_lower
            for keyword in ("admin", "promo code", "referral", "bonus")
        )
    
    @staticmethod
    def calculate_promo_bonus_days(
        promo_model,
        base_duration_days: int
    ) -> int:
        """
        Calculate bonus days from promo code.
        
        Args:
            promo_model: Promo code model
            base_duration_days: Base subscription duration
            
        Returns:
            Bonus days to add
        """
        if not promo_model or not promo_model.is_active:
            return 0
        
        if promo_model.current_activations >= promo_model.max_activations:
            logging.warning(
                f"Promo code {promo_model.promo_code_id} has reached max activations"
            )
            return 0
        
        return promo_model.bonus_days
    
    @staticmethod
    def build_panel_update_payload(
        settings: Settings,
        *,
        panel_user_uuid: Optional[str] = None,
        expire_at: Optional[datetime] = None,
        status: Optional[str] = None,
        traffic_limit_bytes: Optional[int] = None,
        device_limit: Optional[int] = None,
        include_uuid: bool = True,
    ) -> Dict[str, Any]:
        """
        Build panel update payload with standard fields.
        
        Args:
            settings: Settings instance
            panel_user_uuid: Panel user UUID (optional)
            expire_at: Expiration datetime (optional)
            status: Status string (optional)
            traffic_limit_bytes: Traffic limit in bytes (optional)
            device_limit: Device limit (optional)
            include_uuid: Whether to include UUID in payload
            
        Returns:
            Dictionary with panel update payload
        """
        payload: Dict[str, Any] = {}
        
        if include_uuid and panel_user_uuid:
            payload["uuid"] = panel_user_uuid
            
        if expire_at is not None:
            # Format datetime for panel API
            payload["expireAt"] = expire_at.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            )
            
        if status is not None:
            payload["status"] = status
            
        if traffic_limit_bytes is not None:
            payload["trafficLimitBytes"] = traffic_limit_bytes
            payload["trafficLimitStrategy"] = settings.USER_TRAFFIC_STRATEGY
            
        if device_limit is not None:
            payload["hwidDeviceLimit"] = device_limit
            logging.info(f"Setting device limit in panel payload: {device_limit}")
            
        # Add default squad configurations
        if settings.parsed_user_squad_uuids:
            payload["activeInternalSquads"] = settings.parsed_user_squad_uuids
            
        if settings.parsed_user_external_squad_uuid:
            payload["externalSquadUuid"] = settings.parsed_user_external_squad_uuid
            
        return payload