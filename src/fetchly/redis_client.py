"""Redis client factory."""

from redis.asyncio import Redis

from fetchly.config import Settings


def create_redis(settings: Settings) -> Redis:
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        decode_responses=True,
    )
