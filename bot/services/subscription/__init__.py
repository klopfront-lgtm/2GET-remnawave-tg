"""
Subscription Services Module

Декомпозированные subscription сервисы для лучшей организации и поддержки кода.

Рефакторинг от God Object SubscriptionService (1256 строк) к 
специализированным сервисам по принципу Single Responsibility.

Author: Architecture Improvement Phase 2
Date: 2024-11-24
"""

from bot.services.subscription.helpers import (
    PanelUserHelper,
    SubscriptionActivationHelper,
)
from bot.services.subscription.core import SubscriptionCoreService

# В будущем будут добавлены:
# from bot.services.subscription.billing import SubscriptionBillingService
# from bot.services.subscription.notifications import SubscriptionNotificationService

__all__ = [
    "PanelUserHelper",
    "SubscriptionActivationHelper",
    "SubscriptionCoreService",
]