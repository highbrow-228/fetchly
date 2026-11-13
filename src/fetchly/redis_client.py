from redis.asyncio import Redis

from fetchly.config import Settings

# The blocking queue read must end on the server before the client gives up on the socket.
SOCKET_TIMEOUT_MARGIN_SECONDS = 5


def create_redis(settings: Settings) -> Redis:
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        socket_timeout=settings.queue_block_seconds + SOCKET_TIMEOUT_MARGIN_SECONDS,
        decode_responses=True,
    )
