"""Job queue on Redis Streams with a consumer group.

Delivery is at-least-once: a job stays pending until acked. A worker keeps its
in-flight jobs fresh with heartbeats; jobs whose owner died go idle and are
claimed by another worker.
"""

from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from fetchly.queue.job import Job

STREAM = "fetchly:jobs"
DEAD_STREAM = "fetchly:jobs:dead"
GROUP = "workers"


@dataclass(frozen=True, slots=True)
class Delivery:
    id: str
    job: Job
    deliveries: int  # how many times Redis handed this entry to a consumer

    @property
    def attempt(self) -> int:
        """Total attempts so far: explicit retries plus crash redeliveries."""
        return self.job.attempt + self.deliveries - 1


class JobQueue:
    def __init__(self, redis: Redis, consumer: str, claim_idle_ms: int, block_ms: int) -> None:
        self._redis = redis
        self._consumer = consumer
        self._claim_idle_ms = claim_idle_ms
        self._block_ms = block_ms

    async def ensure_group(self) -> None:
        try:
            await self._redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def enqueue(self, job: Job) -> None:
        await self._redis.xadd(STREAM, _encode(job))

    async def next(self) -> Delivery | None:
        """Take an abandoned job if there is one, otherwise wait for a new one."""
        return await self._claim_stale() or await self._read_new()

    async def heartbeat(self, delivery: Delivery) -> None:
        """Reset the idle timer so other workers do not claim a job in progress."""
        await self._redis.xclaim(STREAM, GROUP, self._consumer, 0, [delivery.id], justid=True)

    async def ack(self, delivery: Delivery) -> None:
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.xack(STREAM, GROUP, delivery.id)
            pipe.xdel(STREAM, delivery.id)
            await pipe.execute()

    async def retry(self, delivery: Delivery) -> None:
        await self._move(delivery, STREAM, delivery.job.next_attempt())

    async def bury(self, delivery: Delivery) -> None:
        await self._move(delivery, DEAD_STREAM, delivery.job)

    async def length(self) -> int:
        return await self._redis.xlen(STREAM)

    async def dead_length(self) -> int:
        return await self._redis.xlen(DEAD_STREAM)

    async def _move(self, delivery: Delivery, stream: str, job: Job) -> None:
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.xadd(stream, _encode(job))
            pipe.xack(STREAM, GROUP, delivery.id)
            pipe.xdel(STREAM, delivery.id)
            await pipe.execute()

    async def _read_new(self) -> Delivery | None:
        reply: Any = await self._redis.xreadgroup(
            GROUP, self._consumer, {STREAM: ">"}, count=1, block=self._block_ms
        )
        if not reply:
            return None
        # RESP2 returns [[stream, entries]], RESP3 returns {stream: entries}.
        entries = next(iter(reply.values())) if isinstance(reply, dict) else reply[0][1]
        entry_id, fields = entries[0]
        return Delivery(str(entry_id), Job.from_fields(fields), deliveries=1)

    async def _claim_stale(self) -> Delivery | None:
        reply = await self._redis.xautoclaim(
            STREAM, GROUP, self._consumer, min_idle_time=self._claim_idle_ms, count=1
        )
        for entry_id, fields in reply[1]:
            if fields:  # entries deleted from the stream come back empty
                job = Job.from_fields(fields)
                return Delivery(str(entry_id), job, await self._deliveries(str(entry_id)))
        return None

    async def _deliveries(self, entry_id: str) -> int:
        pending = await self._redis.xpending_range(
            STREAM, GROUP, min=entry_id, max=entry_id, count=1
        )
        return int(pending[0]["times_delivered"]) if pending else 1


def _encode(job: Job) -> dict[Any, Any]:
    return dict(job.to_fields())
