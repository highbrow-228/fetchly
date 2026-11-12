from typing import Any

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from fetchly.queue.job import Job

STREAM = "fetchly:jobs"
DEAD_STREAM = "fetchly:jobs:dead"
GROUP = "workers"


class Delivery(BaseModel, frozen=True):
    id: str = Field(description="Id of the queue entry in the Redis stream")
    job: Job = Field(description="The job read from the queue")
    deliveries: int = Field(
        description="Times Redis gave this entry to a worker; above 1 = a worker died on it"
    )

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
        await self._redis.xadd(STREAM, job.to_fields())

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
        await self._move(delivery.id, STREAM, delivery.job.next_attempt().to_fields())

    async def bury(self, delivery: Delivery) -> None:
        await self._move(delivery.id, DEAD_STREAM, delivery.job.to_fields())

    async def length(self) -> int:
        return await self._redis.xlen(STREAM)

    async def dead_length(self) -> int:
        return await self._redis.xlen(DEAD_STREAM)

    async def _move(self, entry_id: str, stream: str, fields: dict[Any, Any]) -> None:
        """Add the fields to `stream` and remove the original entry, atomically."""
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.xadd(stream, fields)
            pipe.xack(STREAM, GROUP, entry_id)
            pipe.xdel(STREAM, entry_id)
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
        job = await self._parse(str(entry_id), fields)

        return Delivery(id=str(entry_id), job=job, deliveries=1) if job else None

    async def _claim_stale(self) -> Delivery | None:
        reply = await self._redis.xautoclaim(
            STREAM, GROUP, self._consumer, min_idle_time=self._claim_idle_ms, count=1
        )

        for entry_id, fields in reply[1]:
            if not fields:  # entries deleted from the stream come back empty
                continue

            if job := await self._parse(str(entry_id), fields):
                return Delivery(
                    id=str(entry_id), job=job, deliveries=await self._deliveries(str(entry_id))
                )

        return None

    async def _parse(self, entry_id: str, fields: dict[Any, Any]) -> Job | None:
        """Decode an entry; one that is not a job goes to the dead stream as is."""
        try:
            return Job.from_fields(fields)
        except (KeyError, ValueError):
            await self._move(entry_id, DEAD_STREAM, fields)
            return None

    async def _deliveries(self, entry_id: str) -> int:
        pending = await self._redis.xpending_range(
            STREAM, GROUP, min=entry_id, max=entry_id, count=1
        )
        return int(pending[0]["times_delivered"]) if pending else 1
