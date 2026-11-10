"""Queue consumer: takes jobs, keeps them alive, decides between retry and failure."""

import asyncio

import structlog
from redis.exceptions import RedisError

from fetchly.extractors import ExtractionError
from fetchly.queue import Delivery, JobQueue
from fetchly.worker.processor import JobProcessor, Outcome
from fetchly.worker.reporter import Reporter

log = structlog.stdlib.get_logger(__name__)

RESULT_ERROR = "error"


class Consumer:
    def __init__(
        self,
        queue: JobQueue,
        processor: JobProcessor,
        reporter: Reporter,
        *,
        max_attempts: int,
        heartbeat_seconds: int,
        idle_seconds: int,
    ) -> None:
        self._queue = queue
        self._processor = processor
        self._reporter = reporter
        self._max_attempts = max_attempts
        self._heartbeat_seconds = heartbeat_seconds
        self._idle_seconds = idle_seconds

    async def run(self, stop: asyncio.Event) -> None:
        """Process jobs one at a time until asked to stop; the current job is finished."""
        while not stop.is_set():
            try:
                delivery = await self._queue.next()
                if delivery is not None:
                    await self._handle(delivery)
            except RedisError:
                log.exception("queue_unavailable")
                await asyncio.sleep(self._idle_seconds)

    async def _handle(self, delivery: Delivery) -> None:
        if delivery.attempt > self._max_attempts:  # keeps crashing its workers
            await self._queue.bury(delivery)
            await self._reporter.report(delivery.job, Outcome(RESULT_ERROR))
            return
        heartbeat = asyncio.create_task(self._beat(delivery))
        try:
            outcome, retryable = await self._attempt(delivery)
        finally:
            heartbeat.cancel()
        if retryable and delivery.attempt < self._max_attempts:
            await self._queue.retry(delivery)
            return
        if retryable:
            await self._queue.bury(delivery)
        else:
            await self._queue.ack(delivery)
        await self._reporter.report(delivery.job, outcome)

    async def _attempt(self, delivery: Delivery) -> tuple[Outcome, bool]:
        """Run the job. Returns its outcome and whether a failure is worth retrying."""
        job = delivery.job
        try:
            return await self._processor.process(job), False
        except ExtractionError as error:
            return Outcome(error.result), error.retryable
        except Exception as error:
            # Only the error type: messages may contain the link.
            log.warning(
                "job_error",
                chat_id=job.chat_id,
                platform=job.platform.value,
                error=type(error).__name__,
            )
            return Outcome(RESULT_ERROR), True

    async def _beat(self, delivery: Delivery) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_seconds)
            try:
                await self._queue.heartbeat(delivery)
            except RedisError:
                log.warning("heartbeat_failed")
