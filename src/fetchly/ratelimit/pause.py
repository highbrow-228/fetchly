from redis.asyncio import Redis

from fetchly.links import Platform


class PlatformPauser:
    def __init__(self, redis: Redis, base_seconds: int, max_seconds: int) -> None:
        self._redis = redis
        self._base = base_seconds
        self._max = max_seconds

    async def is_paused(self, platform: Platform) -> bool:
        return bool(await self._redis.exists(_pause_key(platform)))

    async def block(self, platform: Platform) -> int:
        """Pause the platform; every consecutive block doubles the pause. Returns seconds."""
        if not await self._redis.set(_pause_key(platform), "1", nx=True, ex=self._base):
            # Already paused: failures of jobs that were in flight are the same block.
            return max(await self._redis.ttl(_pause_key(platform)), 0)

        level = await self._redis.incr(_level_key(platform))
        seconds: int = min(self._base * 2 ** (level - 1), self._max)

        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(_pause_key(platform), "1", ex=seconds)
            pipe.expire(_level_key(platform), self._max * 2)
            await pipe.execute()

        return seconds

    async def succeeded(self, platform: Platform) -> None:
        await self._redis.delete(_level_key(platform))


def _pause_key(platform: Platform) -> str:
    return f"fetchly:pause:{platform.value}"


def _level_key(platform: Platform) -> str:
    return f"fetchly:pause-level:{platform.value}"
