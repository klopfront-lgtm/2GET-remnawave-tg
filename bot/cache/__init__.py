"""
Cache Module

Модуль кэширования для улучшения производительности бота.

Author: Architecture Improvement Phase 3
Date: 2024-11-24
"""

from bot.cache.redis_cache import (
    RedisCache,
    CacheConfig,
    get_redis_cache,
    cached,
)

__all__ = [
    "RedisCache",
    "CacheConfig",
    "get_redis_cache",
    "cached",
]