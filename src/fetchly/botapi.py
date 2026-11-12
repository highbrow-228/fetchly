import asyncio

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.session.middlewares.base import (
    BaseRequestMiddleware,
    NextRequestMiddlewareType,
)
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import TelegramRetryAfter
from aiogram.methods import Response, TelegramMethod
from aiogram.methods.base import TelegramType

from fetchly.config import Settings


class RetryAfterMiddleware(BaseRequestMiddleware):
    """On HTTP 429 wait for `retry_after` and repeat the request."""

    def __init__(self, attempts: int) -> None:
        self._attempts = attempts

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ) -> Response[TelegramType]:
        for _ in range(self._attempts - 1):
            try:
                return await make_request(bot, method)
            except TelegramRetryAfter as error:
                await asyncio.sleep(error.retry_after)

        return await make_request(bot, method)


def create_bot(settings: Settings) -> Bot:
    session = AiohttpSession(
        api=TelegramAPIServer.from_base(settings.bot_api_url, is_local=True),
        timeout=settings.telegram_request_timeout_seconds,
    )

    session.middleware(RetryAfterMiddleware(settings.telegram_retry_attempts))

    return Bot(settings.bot_token, session=session)
