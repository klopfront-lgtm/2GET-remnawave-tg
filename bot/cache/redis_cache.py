"""
Redis Cache Service

Сервис для кэширования часто запрашиваемых данных в Redis.
Снижает нагрузку на PostgreSQL и ускоряет ответы бота.

Кэшируемые данные:
- User profiles
- Tariff plans
- Panel API responses
- Subscription details

Author: Architecture Improvement Phase 3
Date: 2024-11-24
"""

import logging
import json
import pickle
from typing import Optional, Any, Callable, Dict
from datetime import timedelta
from functools import wraps

try:
    from redis.asyncio import Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("Redis not available, caching will be disabled")

from config.settings import Settings


class CacheConfig:
    """Configuration for cache TTLs and settings."""
    
    # Default TTLs in seconds
    USER_PROFILE_TTL = 300  # 5 minutes
    TARIFF_PLAN_TTL = 600  # 10 minutes
    PANEL_USER_TTL = 120  # 2 minutes
    SUBSCRIPTION_TTL = 60  # 1 minute
    STATISTICS_TTL = 180  # 3 minutes


class RedisCache:
    """
    Redis-based cache service for high-performance data caching.
    
    Features:
    - Automatic serialization/deserialization
    - Configurable TTLs per data type
    - Cache invalidation
    - Decorator for easy caching
    - Fallback when Redis unavailable
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize RedisCache.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.redis: Optional[Redis] = None
        self._enabled = False
        
        if settings.REDIS_ENABLED and REDIS_AVAILABLE:
            try:
                self.redis = Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD,
                    db=settings.REDIS_CACHE_DB,
                    decode_responses=False,  # Handle encoding ourselves
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                )
                self._enabled = True
                logging.info(
                    f"RedisCache initialized at {settings.REDIS_HOST}:{settings.REDIS_PORT}, "
                    f"DB={settings.REDIS_CACHE_DB}"
                )
            except Exception as e:
                logging.error(f"Failed to initialize RedisCache: {e}")
                self._enabled = False
        else:
            logging.info("RedisCache disabled (Redis not enabled or unavailable)")
    
    def is_enabled(self) -> bool:
        """Check if cache is enabled and available."""
        return self._enabled and self.redis is not None
    
    # ==================== Basic Cache Operations ====================
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        if not self.is_enabled():
            return None
        
        try:
            value = await self.redis.get(key)
            if value is None:
                return None
            
            # Deserialize
            return pickle.loads(value)
            
        except Exception as e:
            logging.error(f"Cache GET error for key '{key}': {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache (will be pickled)
            ttl: Time-to-live in seconds (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled():
            return False
        
        try:
            # Serialize value
            serialized = pickle.dumps(value)
            
            if ttl:
                await self.redis.setex(key, ttl, serialized)
            else:
                await self.redis.set(key, serialized)
            
            logging.debug(f"Cache SET: key='{key}', ttl={ttl}s")
            return True
            
        except Exception as e:
            logging.error(f"Cache SET error for key '{key}': {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if deleted, False otherwise
        """
        if not self.is_enabled():
            return False
        
        try:
            result = await self.redis.delete(key)
            logging.debug(f"Cache DELETE: key='{key}', deleted={result}")
            return result > 0
        except Exception as e:
            logging.error(f"Cache DELETE error for key '{key}': {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if exists, False otherwise
        """
        if not self.is_enabled():
            return False
        
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logging.error(f"Cache EXISTS error for key '{key}': {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.
        
        Args:
            pattern: Redis key pattern (e.g., "user:*")
            
        Returns:
            Number of keys deleted
        """
        if not self.is_enabled():
            return 0
        
        try:
            deleted = 0
            async for key in self.redis.scan_iter(match=pattern):
                await self.redis.delete(key)
                deleted += 1
            
            logging.info(f"Cache cleared {deleted} keys matching pattern '{pattern}'")
            return deleted
            
        except Exception as e:
            logging.error(f"Cache CLEAR_PATTERN error for pattern '{pattern}': {e}")
            return 0
    
    # ==================== Domain-Specific Cache Methods ====================
    
    async def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get cached user profile."""
        return await self.get(f"user:profile:{user_id}")
    
    async def set_user_profile(
        self,
        user_id: int,
        profile: Dict[str, Any],
        ttl: int = CacheConfig.USER_PROFILE_TTL
    ) -> bool:
        """Cache user profile."""
        return await self.set(f"user:profile:{user_id}", profile, ttl)
    
    async def invalidate_user_profile(self, user_id: int) -> bool:
        """Invalidate cached user profile."""
        return await self.delete(f"user:profile:{user_id}")
    
    async def get_tariff_plan(self, tariff_id: int) -> Optional[Dict[str, Any]]:
        """Get cached tariff plan."""
        return await self.get(f"tariff:{tariff_id}")
    
    async def set_tariff_plan(
        self,
        tariff_id: int,
        tariff: Dict[str, Any],
        ttl: int = CacheConfig.TARIFF_PLAN_TTL
    ) -> bool:
        """Cache tariff plan."""
        return await self.set(f"tariff:{tariff_id}", tariff, ttl)
    
    async def invalidate_all_tariffs(self) -> int:
        """Invalidate all cached tariffs."""
        return await self.clear_pattern("tariff:*")
    
    async def get_panel_user(self, panel_uuid: str) -> Optional[Dict[str, Any]]:
        """Get cached panel user data."""
        return await self.get(f"panel:user:{panel_uuid}")
    
    async def set_panel_user(
        self,
        panel_uuid: str,
        user_data: Dict[str, Any],
        ttl: int = CacheConfig.PANEL_USER_TTL
    ) -> bool:
        """Cache panel user data."""
        return await self.set(f"panel:user:{panel_uuid}", user_data, ttl)
    
    async def invalidate_panel_user(self, panel_uuid: str) -> bool:
        """Invalidate cached panel user."""
        return await self.delete(f"panel:user:{panel_uuid}")
    
    async def get_subscription(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get cached subscription details."""
        return await self.get(f"subscription:{user_id}")
    
    async def set_subscription(
        self,
        user_id: int,
        subscription: Dict[str, Any],
        ttl: int = CacheConfig.SUBSCRIPTION_TTL
    ) -> bool:
        """Cache subscription details."""
        return await self.set(f"subscription:{user_id}", subscription, ttl)
    
    async def invalidate_subscription(self, user_id: int) -> bool:
        """Invalidate cached subscription."""
        return await self.delete(f"subscription:{user_id}")
    
    # ==================== Utility Methods ====================
    
    async def close(self):
        """Close Redis connection."""
        if self.redis:
            try:
                await self.redis.close()
                logging.info("RedisCache connection closed")
            except Exception as e:
                logging.error(f"Error closing RedisCache: {e}")


def cached(
    key_prefix: str,
    ttl: int = 300,
    key_builder: Optional[Callable] = None
):
    """
    Decorator for automatic caching of function results.
    
    Args:
        key_prefix: Prefix for cache key
        ttl: Time-to-live in seconds
        key_builder: Custom function to build cache key from args
        
    Example:
        @cached("user:profile", ttl=300)
        async def get_user_profile(user_id: int):
            # Expensive DB query
            return await db.query(...)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Try to extract cache instance from args/kwargs
            cache = None
            for arg in args:
                if isinstance(arg, RedisCache):
                    cache = arg
                    break
            
            # If no cache, execute function normally
            if not cache or not cache.is_enabled():
                return await func(*args, **kwargs)
            
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default: use function args as key
                cache_key = f"{key_prefix}:{':'.join(str(a) for a in args[1:])}"
            
            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logging.debug(f"Cache HIT: {cache_key}")
                return cached_value
            
            # Cache miss - execute function
            logging.debug(f"Cache MISS: {cache_key}")
            result = await func(*args, **kwargs)
            
            # Cache result
            if result is not None:
                await cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


# Global instance
_global_cache: Optional[RedisCache] = None


def get_redis_cache(settings: Settings) -> RedisCache:
    """
    Get or create global Redis cache instance.
    
    Args:
        settings: Application settings
        
    Returns:
        RedisCache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = RedisCache(settings)
        logging.info("Global RedisCache instance created")
    return _global_cache