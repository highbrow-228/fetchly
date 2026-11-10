"""Turns a message with links into queued download jobs."""

import contextlib

from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, ReactionTypeEmoji

from fetchly.gateway.entities import message_links
from fetchly.links import Link
from fetchly.queue import Job, JobQueue, MessageTracker
from fetchly.ratelimit import IntakeLimiter
from fetchly.telemetry import Metrics

ACCEPTED_REACTION = "👀"


class LinkIntake:
    def __init__(
        self,
        queue: JobQueue,
        tracker: MessageTracker,
        limiter: IntakeLimiter,
        metrics: Metrics,
        *,
        allowed_chats: frozenset[int],
        max_links: int,
    ) -> None:
        self._queue = queue
        self._tracker = tracker
        self._limiter = limiter
        self._metrics = metrics
        self._allowed_chats = allowed_chats
        self._max_links = max_links

    async def __call__(self, message: Message) -> None:
        chat_id = message.chat.id
        if self._allowed_chats and chat_id not in self._allowed_chats:
            return
        user_id = message.from_user.id if message.from_user else chat_id
        links = message_links(message, self._max_links)
        accepted = [link for link in links if await self._within_limits(user_id, chat_id)]
        if not accepted:
            return
        with contextlib.suppress(TelegramAPIError):
            await message.react([ReactionTypeEmoji(emoji=ACCEPTED_REACTION)])
        await self._enqueue(message, accepted)

    async def _within_limits(self, user_id: int, chat_id: int) -> bool:
        scope = await self._limiter.exceeded(user_id, chat_id)
        if scope is not None:
            self._metrics.rate_limited.labels(scope).inc()
        return scope is None

    async def _enqueue(self, message: Message, links: list[Link]) -> None:
        await self._tracker.begin(message.chat.id, message.message_id, len(links))
        for link in links:
            job = Job(
                chat_id=message.chat.id,
                chat_type=message.chat.type,
                message_id=message.message_id,
                platform=link.platform,
                url=link.url,
            )
            await self._queue.enqueue(job)
            self._metrics.enqueued.labels(link.platform.value).inc()
