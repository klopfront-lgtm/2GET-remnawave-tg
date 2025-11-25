"""
Redis FSM Storage Configuration Module

Provides RedisStorage configuration for Aiogram FSM state management.
Benefits over MemoryStorage:
- Persistent state across bot restarts
- Shared state across multiple bot instances (horizontal scaling)
- Automatic TTL for expired states
- Better memory management for high-load scenarios

Author: Architecture Improvement Phase 1
Date: 2024-11-24
"""

import logging
from typing import Optional
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from redis.asyncio import Redis


class RedisStorageFactory:
    """Factory class for creating and managing Redis FSM Storage instances."""
    
    _instance: Optional[RedisStorage] = None
    _redis_client: Optional[Redis] = None
    
    @classmethod
    async def create_storage(
        cls,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
        state_ttl: int = 3600,
        data_ttl: int = 3600,
    ) -> RedisStorage:
        """
        Create or return existing RedisStorage instance.
        
        Args:
            redis_host: Redis server hostname
            redis_port: Redis server port
            redis_db: Redis database number
            redis_password: Redis password (optional)
            state_ttl: Time-to-live for FSM states in seconds (default: 1 hour)
            data_ttl: Time-to-live for FSM data in seconds (default: 1 hour)
            
        Returns:
            Configured RedisStorage instance
        """
        if cls._instance is not None:
            logging.info("RedisStorage: Returning existing instance")
            return cls._instance
        
        try:
            # Create Redis client
            cls._redis_client = Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=False,  # Aiogram handles encoding
                socket_connect_timeout=5,
                socket_keepalive=True,
                retry_on_timeout=True,
            )
            
            # Test connection
            await cls._redis_client.ping()
            logging.info(
                f"RedisStorage: Connected to Redis at {redis_host}:{redis_port}, DB={redis_db}"
            )
            
            # Create RedisStorage with custom key builder
            cls._instance = RedisStorage(
                redis=cls._redis_client,
                key_builder=DefaultKeyBuilder(with_destiny=True),
                state_ttl=state_ttl,
                data_ttl=data_ttl,
            )
            
            logging.info(
                f"RedisStorage: Created with state_ttl={state_ttl}s, data_ttl={data_ttl}s"
            )
            
            return cls._instance
            
        except Exception as e:
            logging.error(
                f"RedisStorage: Failed to create storage: {e}",
                exc_info=True
            )
            raise
    
    @classmethod
    async def close(cls):
        """Close Redis connection gracefully."""
        if cls._redis_client:
            try:
                await cls._redis_client.close()
                logging.info("RedisStorage: Redis client connection closed")
            except Exception as e:
                logging.error(f"RedisStorage: Error closing Redis client: {e}")
        
        cls._instance = None
        cls._redis_client = None
    
    @classmethod
    def is_connected(cls) -> bool:
        """Check if Redis storage is connected."""
        return cls._instance is not None and cls._redis_client is not None


async def create_redis_storage_from_settings(settings) -> RedisStorage:
    """
    Create RedisStorage from Settings configuration.
    
    Args:
        settings: Settings instance with Redis configuration
        
    Returns:
        Configured RedisStorage instance
    """
    return await RedisStorageFactory.create_storage(
        redis_host=settings.REDIS_HOST,
        redis_port=settings.REDIS_PORT,
        redis_db=settings.REDIS_FSM_DB,
        redis_password=settings.REDIS_PASSWORD,
        state_ttl=settings.REDIS_FSM_STATE_TTL,
        data_ttl=settings.REDIS_FSM_DATA_TTL,
    )