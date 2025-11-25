"""
Rate Limiting Middleware

Защита от спама и DDoS атак путем ограничения количества запросов от пользователя.
Поддерживает как Redis (для distributed rate limiting), так и in-memory storage.

Author: Architecture Improvement Phase 1
Date: 2024-11-24
"""

import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional
from collections import defaultdict, deque

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery

try:
    from redis.asyncio import Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RateLimitConfig:
    """Configuration for rate limiting."""
    
    def __init__(
        self,
        max_requests: int = 20,
        time_window: int = 60,
        ban_duration: int = 300,
        admin_exempt: bool = True,
    ):
        """
        Initialize rate limit configuration.
        
        Args:
            max_requests: Maximum number of requests per time window
            time_window: Time window in seconds
            ban_duration: Duration of temporary ban in seconds (0 = no ban)
            admin_exempt: Whether admins are exempt from rate limiting
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.ban_duration = ban_duration
        self.admin_exempt = admin_exempt


class InMemoryRateLimiter:
    """In-memory rate limiter (fallback when Redis is unavailable)."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._requests: Dict[int, deque] = defaultdict(deque)
        self._banned: Dict[int, float] = {}
        
    async def check_limit(self, user_id: int) -> tuple[bool, Optional[int]]:
        """
        Check if user has exceeded rate limit.
        
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        current_time = time.time()
        
        # Check if user is temporarily banned
        if user_id in self._banned:
            ban_until = self._banned[user_id]
            if current_time < ban_until:
                retry_after = int(ban_until - current_time)
                return False, retry_after
            else:
                # Ban expired, remove from banned list
                del self._banned[user_id]
        
        # Get user's request history
        requests = self._requests[user_id]
        
        # Remove old requests outside time window
        cutoff_time = current_time - self.config.time_window
        while requests and requests[0] < cutoff_time:
            requests.popleft()
        
        # Check if limit exceeded
        if len(requests) >= self.config.max_requests:
            # Temporarily ban user if ban_duration is set
            if self.config.ban_duration > 0:
                self._banned[user_id] = current_time + self.config.ban_duration
                logging.warning(
                    f"Rate limit: User {user_id} temporarily banned for {self.config.ban_duration}s. "
                    f"Requests: {len(requests)} in {self.config.time_window}s window"
                )
                return False, self.config.ban_duration
            else:
                retry_after = int(self.config.time_window - (current_time - requests[0]))
                return False, retry_after
        
        # Add current request
        requests.append(current_time)
        return True, None
    
    async def reset_user(self, user_id: int):
        """Reset rate limit for user (admin action)."""
        if user_id in self._requests:
            del self._requests[user_id]
        if user_id in self._banned:
            del self._banned[user_id]
        logging.info(f"Rate limit: Reset for user {user_id}")


class RedisRateLimiter:
    """Redis-based rate limiter for distributed rate limiting."""
    
    def __init__(self, redis: Redis, config: RateLimitConfig):
        self.redis = redis
        self.config = config
        
    def _get_key(self, user_id: int, suffix: str = "") -> str:
        """Get Redis key for user."""
        return f"rate_limit:{user_id}{':' + suffix if suffix else ''}"
    
    async def check_limit(self, user_id: int) -> tuple[bool, Optional[int]]:
        """
        Check if user has exceeded rate limit using Redis.
        
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        current_time = time.time()
        
        # Check if user is temporarily banned
        ban_key = self._get_key(user_id, "banned")
        ban_until = await self.redis.get(ban_key)
        if ban_until:
            ban_until_time = float(ban_until)
            if current_time < ban_until_time:
                retry_after = int(ban_until_time - current_time)
                return False, retry_after
        
        # Use Redis sorted set to track requests
        requests_key = self._get_key(user_id, "requests")
        
        # Remove old requests outside time window
        cutoff_time = current_time - self.config.time_window
        await self.redis.zremrangebyscore(requests_key, 0, cutoff_time)
        
        # Count current requests in window
        request_count = await self.redis.zcard(requests_key)
        
        # Check if limit exceeded
        if request_count >= self.config.max_requests:
            # Temporarily ban user if ban_duration is set
            if self.config.ban_duration > 0:
                ban_until_time = current_time + self.config.ban_duration
                await self.redis.setex(
                    ban_key,
                    self.config.ban_duration,
                    str(ban_until_time)
                )
                logging.warning(
                    f"Rate limit (Redis): User {user_id} temporarily banned for {self.config.ban_duration}s. "
                    f"Requests: {request_count} in {self.config.time_window}s window"
                )
                return False, self.config.ban_duration
            else:
                # Calculate retry_after based on oldest request
                oldest_request = await self.redis.zrange(requests_key, 0, 0, withscores=True)
                if oldest_request:
                    retry_after = int(self.config.time_window - (current_time - oldest_request[0][1]))
                else:
                    retry_after = self.config.time_window
                return False, retry_after
        
        # Add current request to sorted set
        await self.redis.zadd(requests_key, {str(current_time): current_time})
        
        # Set expiry on requests key
        await self.redis.expire(requests_key, self.config.time_window + 60)
        
        return True, None
    
    async def reset_user(self, user_id: int):
        """Reset rate limit for user (admin action)."""
        requests_key = self._get_key(user_id, "requests")
        ban_key = self._get_key(user_id, "banned")
        await self.redis.delete(requests_key, ban_key)
        logging.info(f"Rate limit (Redis): Reset for user {user_id}")


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты запросов (rate limiting).
    
    Защищает бота от спама и DDoS атак путем ограничения количества
    запросов от одного пользователя в единицу времени.
    """
    
    def __init__(
        self,
        config: Optional[RateLimitConfig] = None,
        redis: Optional[Redis] = None,
        admin_ids: Optional[list[int]] = None,
    ):
        """
        Initialize rate limit middleware.
        
        Args:
            config: Rate limit configuration (uses defaults if None)
            redis: Redis client for distributed rate limiting (optional)
            admin_ids: List of admin user IDs to exempt from rate limiting
        """
        super().__init__()
        self.config = config or RateLimitConfig()
        self.admin_ids = admin_ids or []
        
        # Choose rate limiter based on Redis availability
        if redis and REDIS_AVAILABLE:
            self.limiter = RedisRateLimiter(redis, self.config)
            logging.info("Rate limiting: Using Redis-based distributed rate limiter")
        else:
            self.limiter = InMemoryRateLimiter(self.config)
            logging.info("Rate limiting: Using in-memory rate limiter (single instance only)")
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Process update with rate limiting."""
        
        # Extract user_id from event
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, Update):
            if event.message and event.message.from_user:
                user_id = event.message.from_user.id
            elif event.callback_query and event.callback_query.from_user:
                user_id = event.callback_query.from_user.id
        
        # Skip rate limiting if no user_id found
        if user_id is None:
            return await handler(event, data)
        
        # Exempt admins from rate limiting if configured
        if self.config.admin_exempt and user_id in self.admin_ids:
            return await handler(event, data)
        
        # Check rate limit
        is_allowed, retry_after = await self.limiter.check_limit(user_id)
        
        if not is_allowed:
            # Rate limit exceeded - send warning message
            logging.warning(
                f"Rate limit exceeded for user {user_id}. Retry after: {retry_after}s"
            )
            
            # Try to respond to user
            if isinstance(event, Message):
                try:
                    await event.answer(
                        f"⚠️ Превышен лимит запросов. Попробуйте снова через {retry_after} секунд.",
                        show_alert=False
                    )
                except Exception:
                    pass
            elif isinstance(event, CallbackQuery):
                try:
                    await event.answer(
                        f"⚠️ Превышен лимит запросов. Попробуйте снова через {retry_after} секунд.",
                        show_alert=True
                    )
                except Exception:
                    pass
            
            # Don't call next handler - request blocked
            return None
        
        # Request allowed - call next handler
        return await handler(event, data)
    
    async def reset_user_limit(self, user_id: int):
        """Reset rate limit for specific user (for admin command)."""
        await self.limiter.reset_user(user_id)