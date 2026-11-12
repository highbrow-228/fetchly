import asyncio
import time

from redis.asyncio import Redis

CHAT_WINDOW_SECONDS = 60
GLOBAL_WINDOW_SECONDS = 1


class SendLimiter:
    def __init__(self, redis: Redis, chat_per_minute: int, global_per_second: int) -> None:
        self._redis = redis
        self._chat_limit = chat_per_minute
        self._global_limit = global_per_second

    async def acquire(self, chat_id: int, messages: int) -> None:
        """Wait until `messages` more messages fit into both limits."""
        await self._wait(
            f"fetchly:send:chat:{chat_id}", CHAT_WINDOW_SECONDS, self._chat_limit, messages
        )
        await self._wait("fetchly:send:global", GLOBAL_WINDOW_SECONDS, self._global_limit, messages)

    async def _wait(self, prefix: str, window: int, limit: int, cost: int) -> None:
        while True:
            now = time.time()
            slot = int(now) // window
            key = f"{prefix}:{slot}"

            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incrby(key, cost)
                pipe.expire(key, window * 2)
                used, _ = await pipe.execute()

            if int(used) <= limit:
                return

            await self._redis.decrby(key, cost)
            await asyncio.sleep((slot + 1) * window - now)
