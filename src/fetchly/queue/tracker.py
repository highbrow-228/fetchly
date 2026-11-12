from redis.asyncio import Redis


class MessageTracker:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def begin(self, chat_id: int, message_id: int, jobs: int) -> None:
        key = _key(chat_id, message_id)

        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.hset(key, mapping={"pending": jobs, "failed": 0})
            pipe.expire(key, self._ttl)
            await pipe.execute()

    async def finish(self, chat_id: int, message_id: int, *, failed: bool) -> bool | None:
        """Record one finished job.

        Returns None while other jobs of the message are still running, otherwise
        True if any job of the message failed.
        """
        key = _key(chat_id, message_id)

        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.hincrby(key, "pending", -1)
            pipe.hincrby(key, "failed", int(failed))
            pending, failures = await pipe.execute()

        if int(pending) > 0:
            return None

        await self._redis.delete(key)

        return int(failures) > 0


def _key(chat_id: int, message_id: int) -> str:
    return f"fetchly:msg:{chat_id}:{message_id}"
