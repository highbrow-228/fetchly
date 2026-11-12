import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
from redis.asyncio import Redis

log = structlog.stdlib.get_logger(__name__)

_LOGOUT_MARKER = "fetchly:cloud-logout-done"


async def leave_cloud_api(token: str, redis: Redis) -> None:
    """Call logOut on the cloud Bot API once; later starts skip it."""
    if not await redis.set(_LOGOUT_MARKER, "1", nx=True):
        return

    cloud = Bot(token)

    try:
        await cloud.log_out()
        log.info("cloud_api_logged_out")
    except TelegramNetworkError:
        await redis.delete(_LOGOUT_MARKER)  # could not reach Telegram: try again next start
        raise
    except TelegramAPIError as error:
        # The cloud refuses a bot that is already logged out; nothing left to do.
        log.info("cloud_api_logout_skipped", error=type(error).__name__)
    finally:
        await cloud.session.close()


async def register_webhook(bot: Bot, url: str, secret: str, updates: list[str]) -> None:
    await bot.set_webhook(url, secret_token=secret, allowed_updates=updates)
    log.info("webhook_registered")
