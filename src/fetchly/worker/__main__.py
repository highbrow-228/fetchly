"""Worker entry point: wires dependencies and runs consumers until SIGTERM."""

import asyncio
import signal
import socket

from aiohttp import web

from fetchly.botapi import create_bot
from fetchly.cache import FileIdCache
from fetchly.config import Settings, load_settings
from fetchly.db import (
    ChatRepository,
    DownloadRepository,
    MediaRepository,
    create_engine,
    create_session_factory,
)
from fetchly.extractors import Workspace, build_registry
from fetchly.queue import JobQueue, MessageTracker
from fetchly.ratelimit import PlatformPauser, SendLimiter
from fetchly.redis_client import create_redis
from fetchly.telemetry import Metrics, setup_logging
from fetchly.telemetry.server import add_telemetry_routes, start_site
from fetchly.worker.consumer import Consumer
from fetchly.worker.maintenance import Maintenance
from fetchly.worker.processor import JobProcessor
from fetchly.worker.reporter import Reporter
from fetchly.worker.sender import MediaSender


async def run(settings: Settings) -> None:
    redis = create_redis(settings)
    engine = create_engine(settings)
    sessions = create_session_factory(engine)
    bot = create_bot(settings)
    metrics = Metrics()
    downloads = DownloadRepository(sessions)
    workspace = Workspace(settings.shared_dir, settings.cookies_dir)
    queue = JobQueue(
        redis,
        consumer=socket.gethostname(),
        claim_idle_ms=settings.job_claim_idle_seconds * 1000,
        block_ms=settings.queue_block_seconds * 1000,
    )
    processor = JobProcessor(
        redis=redis,
        cache=FileIdCache(redis, MediaRepository(sessions), settings.cache_ttl_seconds),
        pauser=PlatformPauser(redis, settings.pause_base_seconds, settings.pause_max_seconds),
        registry=build_registry(settings, workspace),
        workspace=workspace,
        sender=MediaSender(
            bot,
            SendLimiter(
                redis, settings.send_rate_per_chat_per_minute, settings.send_rate_global_per_second
            ),
        ),
        metrics=metrics,
        lock_ttl_seconds=settings.url_lock_ttl_seconds,
        lock_wait_seconds=settings.url_lock_wait_seconds,
    )
    reporter = Reporter(
        bot,
        MessageTracker(redis, settings.job_state_ttl_seconds),
        ChatRepository(sessions),
        downloads,
        metrics,
    )
    consumer = Consumer(
        queue,
        processor,
        reporter,
        max_attempts=settings.job_max_attempts,
        heartbeat_seconds=settings.job_heartbeat_seconds,
        idle_seconds=settings.queue_block_seconds,
    )
    maintenance = Maintenance(
        downloads,
        workspace,
        interval_seconds=settings.maintenance_interval_seconds,
        stale_seconds=settings.url_lock_ttl_seconds,
    )

    async def refresh_metrics() -> None:
        metrics.queue_length.set(await queue.length())
        metrics.dead_length.set(await queue.dead_length())

    telemetry = web.Application()
    add_telemetry_routes(telemetry, metrics, refresh_metrics)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)

    await queue.ensure_group()
    site = await start_site(telemetry, settings.worker_metrics_port)
    try:
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(maintenance.run(stop))
            for _ in range(settings.worker_concurrency):
                tasks.create_task(consumer.run(stop))
    finally:
        await site.cleanup()
        await bot.session.close()
        await redis.aclose()
        await engine.dispose()


def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
