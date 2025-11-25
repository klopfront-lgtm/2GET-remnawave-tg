import logging
from typing import Dict

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import BaseStorage
from sqlalchemy.orm import sessionmaker

from config.settings import Settings
from bot.middlewares.db_session import DBSessionMiddleware
from bot.middlewares.i18n import I18nMiddleware, get_i18n_instance, JsonI18n
from bot.middlewares.ban_check_middleware import BanCheckMiddleware
from bot.middlewares.action_logger_middleware import ActionLoggerMiddleware
from bot.middlewares.profile_sync import ProfileSyncMiddleware
from bot.middlewares.channel_subscription import ChannelSubscriptionMiddleware
from bot.middlewares.rate_limit_middleware import RateLimitMiddleware, RateLimitConfig


async def create_storage(settings: Settings) -> BaseStorage:
    """
    Create FSM storage based on configuration.
    
    Returns MemoryStorage by default or RedisStorage if Redis is enabled.
    """
    if settings.REDIS_ENABLED:
        try:
            from bot.storage.redis_storage import create_redis_storage_from_settings
            
            storage = await create_redis_storage_from_settings(settings)
            logging.info("FSM Storage: Using RedisStorage (persistent state)")
            return storage
        except Exception as e:
            logging.error(
                f"FSM Storage: Failed to create RedisStorage, falling back to MemoryStorage: {e}",
                exc_info=True
            )
            storage = MemoryStorage()
            logging.warning("FSM Storage: Using MemoryStorage as fallback (state will be lost on restart)")
            return storage
    else:
        storage = MemoryStorage()
        logging.info("FSM Storage: Using MemoryStorage (state will be lost on restart)")
        return storage


def build_dispatcher(settings: Settings, async_session_factory: sessionmaker) -> tuple[Dispatcher, Bot, Dict]:
    # Storage creation moved to async initialization in main_bot.py
    storage = MemoryStorage()  # Temporary, will be replaced in main_bot.py
    default_props = DefaultBotProperties(parse_mode=ParseMode.HTML)
    bot = Bot(token=settings.BOT_TOKEN, default=default_props)

    dp = Dispatcher(storage=storage, settings=settings, bot_instance=bot)

    i18n_instance = get_i18n_instance(path="locales", default=settings.DEFAULT_LANGUAGE)

    dp["i18n_instance"] = i18n_instance
    dp["async_session_factory"] = async_session_factory

    # Rate limiting middleware (first to protect from spam)
    if settings.RATE_LIMIT_ENABLED:
        try:
            # Try to use Redis if available
            redis_client = None
            if settings.REDIS_ENABLED:
                from redis.asyncio import Redis
                redis_client = Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD,
                    db=settings.REDIS_CACHE_DB,  # Use cache DB for rate limiting
                    decode_responses=False,
                )
            
            rate_limit_config = RateLimitConfig(
                max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
                time_window=settings.RATE_LIMIT_TIME_WINDOW,
                ban_duration=settings.RATE_LIMIT_BAN_DURATION,
                admin_exempt=settings.RATE_LIMIT_ADMIN_EXEMPT,
            )
            
            dp.update.outer_middleware(
                RateLimitMiddleware(
                    config=rate_limit_config,
                    redis=redis_client,
                    admin_ids=settings.ADMIN_IDS,
                )
            )
            logging.info("Rate limiting middleware registered")
        except Exception as e:
            logging.error(f"Failed to initialize rate limiting: {e}", exc_info=True)
    
    dp.update.outer_middleware(DBSessionMiddleware(async_session_factory))
    dp.update.outer_middleware(I18nMiddleware(i18n=i18n_instance, settings=settings))
    dp.update.outer_middleware(ProfileSyncMiddleware())
    dp.update.outer_middleware(BanCheckMiddleware(settings=settings, i18n_instance=i18n_instance))
    dp.update.outer_middleware(ChannelSubscriptionMiddleware(settings=settings, i18n_instance=i18n_instance))
    dp.update.outer_middleware(ActionLoggerMiddleware(settings=settings))

    return dp, bot, {"i18n_instance": i18n_instance}

