"""Gateway entry point: wires dependencies and serves the webhook until SIGTERM."""

import asyncio
import signal
import socket

from aiohttp import web

from fetchly.botapi import create_bot
from fetchly.config import Settings, load_settings
from fetchly.db import ChatRepository, DownloadRepository, create_engine, create_session_factory
from fetchly.gateway.app import build_dispatcher, build_webhook_app
from fetchly.gateway.bootstrap import leave_cloud_api, register_webhook
from fetchly.gateway.commands import StatsCommand
from fetchly.gateway.intake import LinkIntake
from fetchly.gateway.membership import MembershipTracker
from fetchly.queue import JobQueue, MessageTracker
from fetchly.ratelimit import IntakeLimiter
from fetchly.redis_client import create_redis
from fetchly.telemetry import Metrics, setup_logging
from fetchly.telemetry.server import add_telemetry_routes, start_site


async def run(settings: Settings) -> None:
    redis = create_redis(settings)
    engine = create_engine(settings)
    sessions = create_session_factory(engine)
    bot = create_bot(settings)
    metrics = Metrics()
    queue = JobQueue(
        redis,
        consumer=socket.gethostname(),
        claim_idle_ms=settings.job_claim_idle_seconds * 1000,
        block_ms=settings.queue_block_seconds * 1000,
    )
    intake = LinkIntake(
        queue,
        MessageTracker(redis, settings.job_state_ttl_seconds),
        IntakeLimiter(redis, settings.user_rate_per_minute, settings.chat_rate_per_minute),
        metrics,
        allowed_chats=settings.allowed_chats,
        max_links=settings.max_links_per_message,
    )
    dispatcher = build_dispatcher(
        intake,
        StatsCommand(DownloadRepository(sessions), queue),
        MembershipTracker(ChatRepository(sessions)),
        settings.owner_id,
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
    webhook_site = await start_site(
        build_webhook_app(dispatcher, bot, settings.webhook_secret), settings.gateway_port
    )
    telemetry_site = await start_site(telemetry, settings.gateway_metrics_port)
    try:
        await leave_cloud_api(settings.bot_token, redis)
        await register_webhook(
            bot,
            settings.webhook_url,
            settings.webhook_secret,
            dispatcher.resolve_used_update_types(),
        )
        await stop.wait()
    finally:
        await webhook_site.cleanup()
        await telemetry_site.cleanup()
        await bot.session.close()
        await redis.aclose()
        await engine.dispose()


def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
