"""One job from start to finish: cache, lock, download, send, remember."""

import contextlib
import hashlib
import time
from dataclasses import dataclass

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from fetchly.cache import CachedItem, FileIdCache
from fetchly.extractors import (
    ExtractorRegistry,
    MediaResult,
    PlatformBlockedError,
    PlatformPausedError,
    Workspace,
)
from fetchly.queue import Job
from fetchly.ratelimit import PlatformPauser
from fetchly.telemetry import Metrics
from fetchly.worker.sender import MediaSender, Outgoing

log = structlog.stdlib.get_logger(__name__)

RESULT_OK = "ok"


class LockTimeoutError(Exception):
    """Another worker held the link lock for too long."""


@dataclass(frozen=True, slots=True)
class Outcome:
    result: str
    from_cache: bool = False
    duration_ms: int = 0
    size_bytes: int = 0


class JobProcessor:
    def __init__(
        self,
        *,
        redis: Redis,
        cache: FileIdCache,
        pauser: PlatformPauser,
        registry: ExtractorRegistry,
        workspace: Workspace,
        sender: MediaSender,
        metrics: Metrics,
        lock_ttl_seconds: int,
        lock_wait_seconds: int,
    ) -> None:
        self._redis = redis
        self._cache = cache
        self._pauser = pauser
        self._registry = registry
        self._workspace = workspace
        self._sender = sender
        self._metrics = metrics
        self._lock_ttl = lock_ttl_seconds
        self._lock_wait = lock_wait_seconds

    async def process(self, job: Job) -> Outcome:
        if await self._send_cached(job):
            return Outcome(RESULT_OK, from_cache=True)
        lock = self._redis.lock(
            _lock_name(job.url), timeout=self._lock_ttl, blocking_timeout=self._lock_wait
        )
        if not await lock.acquire():
            raise LockTimeoutError
        try:
            # Whoever held the lock before us has probably filled the cache.
            if await self._send_cached(job):
                return Outcome(RESULT_OK, from_cache=True)
            return await self._download_and_send(job)
        finally:
            with contextlib.suppress(RedisError):  # the job is done either way; the lock expires
                await lock.release()

    async def _send_cached(self, job: Job) -> bool:
        cached = await self._cache.get(job.url)
        if cached is None:
            return False
        await self._sender.send(job, [Outgoing.from_cache(item) for item in cached])
        return True

    async def _download_and_send(self, job: Job) -> Outcome:
        started = time.monotonic()
        media = await self._download(job)
        elapsed = time.monotonic() - started
        self._metrics.download_seconds.labels(job.platform.value, media.extractor).observe(elapsed)
        try:
            size = media.size_bytes
            sent = await self._sender.send(job, [Outgoing.from_file(item) for item in media.items])
        finally:
            await self._workspace.discard(media.workdir)
        await self._remember(job, media, sent)
        return Outcome(RESULT_OK, duration_ms=round(elapsed * 1000), size_bytes=size)

    async def _download(self, job: Job) -> MediaResult:
        if await self._pauser.is_paused(job.platform):
            raise PlatformPausedError(job.platform.value)
        try:
            media = await self._registry.extract(job.platform, job.url)
        except PlatformBlockedError:
            seconds = await self._pauser.block(job.platform)
            self._metrics.blocks.labels(job.platform.value).inc()
            log.warning("platform_paused", platform=job.platform.value, seconds=seconds)
            raise
        await self._pauser.succeeded(job.platform)
        return media

    async def _remember(self, job: Job, media: MediaResult, sent: list[CachedItem]) -> None:
        # The media is already in the chat: a cache failure must not trigger a resend.
        try:
            await self._cache.put(job.url, job.platform, media.media_id, sent)
        except Exception:
            log.exception("cache_write_failed", platform=job.platform.value)


def _lock_name(url: str) -> str:
    return "fetchly:lock:" + hashlib.sha256(url.encode()).hexdigest()
