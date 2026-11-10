"""Intake limits: downloads per minute for a user and for a chat."""

import time

from redis.asyncio import Redis

WINDOW_SECONDS = 60


class IntakeLimiter:
    def __init__(self, redis: Redis, user_per_minute: int, chat_per_minute: int) -> None:
        self._redis = redis
        self._limits = {"user": user_per_minute, "chat": chat_per_minute}

    async def exceeded(self, user_id: int, chat_id: int) -> str | None:
        """Count one download. Returns the scope that hit its limit, if any."""
        window = int(time.time()) // WINDOW_SECONDS
        for scope, subject in (("user", user_id), ("chat", chat_id)):
            key = f"fetchly:rl:{scope}:{subject}:{window}"
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, WINDOW_SECONDS)
                count, _ = await pipe.execute()
            if int(count) > self._limits[scope]:
                return scope
        return None
