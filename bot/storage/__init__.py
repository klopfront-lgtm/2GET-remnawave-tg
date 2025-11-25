"""
FSM Storage Configuration Module

Provides storage implementations for Aiogram FSM state management.
"""

from bot.storage.redis_storage import (
    RedisStorageFactory,
    create_redis_storage_from_settings,
)

__all__ = [
    "RedisStorageFactory",
    "create_redis_storage_from_settings",
]