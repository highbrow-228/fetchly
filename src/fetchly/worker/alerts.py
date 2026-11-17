import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from redis.asyncio import Redis

from fetchly.links import Platform

log = structlog.stdlib.get_logger(__name__)

# Private posts need a login too, so one refusal proves nothing; a streak means dead cookies.
LOGIN_STREAK = 3


class LoginAlert:
    """Tells the owner in a private chat when a platform keeps asking to log in."""

    def __init__(self, bot: Bot, redis: Redis, owner_id: int) -> None:
        self._bot = bot
        self._redis = redis
        self._owner_id = owner_id

    async def refused(self, platform: Platform) -> None:
        streak = await self._redis.incr(_streak_key(platform))
        if streak != LOGIN_STREAK:
            return  # one message per streak, not one per refusal

        log.warning("login_streak", platform=platform.value, streak=streak)
        text = (
            f"⚠️ {platform.value}: {streak} завантаження поспіль просять вхід в акаунт. "
            f"Схоже, cookies протухли. Експортуй нові в cookies/{platform.value}.txt "
            "і зроби chmod 644, перезапуск не потрібен."
        )

        try:
            await self._bot.send_message(self._owner_id, text)
        except TelegramAPIError as error:
            # Usually the owner has never pressed Start in a private chat with the bot.
            log.warning("login_alert_not_sent", platform=platform.value, error=str(error))

    async def succeeded(self, platform: Platform) -> None:
        await self._redis.delete(_streak_key(platform))


def _streak_key(platform: Platform) -> str:
    return f"fetchly:login-streak:{platform.value}"
