import contextlib

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ReactionTypeEmoji, ReactionTypeUnion, ReplyParameters

from fetchly.db import ChatRepository, DownloadRepository
from fetchly.extractors import (
    LoginRequiredError,
    MediaTooLargeError,
    MediaTooLongError,
    PlatformBlockedError,
    PlatformPausedError,
)
from fetchly.queue import Job, MessageTracker
from fetchly.telemetry import Metrics
from fetchly.worker.processor import RESULT_OK, Outcome

log = structlog.stdlib.get_logger(__name__)

FAILURE_REACTION = "🤷"
_BLOCKED_TEXT = "Не вийшло: платформа тимчасово блокує завантаження. Спробуйте пізніше."
# Failures the user can do something about get a reply; the rest only the reaction.
FAILURE_TEXTS = {
    LoginRequiredError.result: "Не вийшло: цей допис видно лише після входу в акаунт.",
    MediaTooLargeError.result: "Не вийшло: файл завеликий.",
    MediaTooLongError.result: "Не вийшло: відео задовге.",
    PlatformBlockedError.result: _BLOCKED_TEXT,
    PlatformPausedError.result: _BLOCKED_TEXT,
}


class Reporter:
    def __init__(
        self,
        bot: Bot,
        tracker: MessageTracker,
        chats: ChatRepository,
        downloads: DownloadRepository,
        metrics: Metrics,
    ) -> None:
        self._bot = bot
        self._tracker = tracker
        self._chats = chats
        self._downloads = downloads
        self._metrics = metrics

    async def report(self, job: Job, outcome: Outcome) -> None:
        platform = job.platform.value
        cached = str(outcome.from_cache).lower()
        self._metrics.downloads.labels(platform, outcome.result, cached).inc()
        log.info("job_finished", chat_id=job.chat_id, platform=platform, result=outcome.result)
        await self._react(job, failed=outcome.result != RESULT_OK)
        await self._explain(job, outcome)
        await self._persist(job, outcome)

    async def _react(self, job: Job, *, failed: bool) -> None:
        any_failed = await self._tracker.finish(job.chat_id, job.message_id, failed=failed)
        if any_failed is None:
            return  # other links of the same message are still in progress

        reaction: list[ReactionTypeUnion] = []

        if any_failed:
            reaction.append(ReactionTypeEmoji(emoji=FAILURE_REACTION))

        with contextlib.suppress(TelegramAPIError):
            await self._bot.set_message_reaction(job.chat_id, job.message_id, reaction=reaction)

    async def _explain(self, job: Job, outcome: Outcome) -> None:
        text = FAILURE_TEXTS.get(outcome.result)
        if text is None:
            return

        with contextlib.suppress(TelegramAPIError):
            await self._bot.send_message(
                job.chat_id,
                text,
                reply_parameters=ReplyParameters(
                    message_id=job.message_id, allow_sending_without_reply=True
                ),
            )

    async def _persist(self, job: Job, outcome: Outcome) -> None:
        try:
            await self._chats.ensure(job.chat_id, job.chat_type)

            await self._downloads.record(
                chat_id=job.chat_id,
                platform=job.platform.value,
                result=outcome.result,
                duration_ms=outcome.duration_ms,
                size_bytes=outcome.size_bytes,
                from_cache=outcome.from_cache,
            )
        except Exception:
            log.exception("download_record_failed", chat_id=job.chat_id)
