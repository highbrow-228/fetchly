from itertools import batched
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import (
    InputMediaPhoto,
    InputMediaVideo,
    MediaUnion,
    Message,
    ReplyParameters,
)
from pydantic import BaseModel, Field

from fetchly.cache import CachedItem
from fetchly.extractors import MediaItem, MediaKind
from fetchly.queue import Job
from fetchly.ratelimit import SendLimiter

TELEGRAM_ALBUM_SIZE = 10


class SendError(Exception):
    """Telegram accepted the request but returned no usable media."""


class Outgoing(BaseModel, frozen=True):
    kind: MediaKind = Field(description="Type of the file: photo, video or animation")
    media: str = Field(
        description="A Telegram file_id, or a file:// path the local Bot API server can read"
    )
    width: int | None = Field(default=None, description="Video width in pixels; None = unknown")
    height: int | None = Field(default=None, description="Video height in pixels; None = unknown")
    duration: int | None = Field(
        default=None, description="Video length in seconds; None = unknown"
    )

    @classmethod
    def from_file(cls, item: MediaItem) -> "Outgoing":
        return cls(
            kind=item.kind,
            media=item.path.as_uri(),
            width=item.width,
            height=item.height,
            duration=item.duration,
        )

    @classmethod
    def from_cache(cls, item: CachedItem) -> "Outgoing":
        return cls(kind=item.kind, media=item.file_id)


class MediaSender:
    def __init__(self, bot: Bot, limiter: SendLimiter) -> None:
        self._bot = bot
        self._limiter = limiter

    async def send(
        self, job: Job, items: list[Outgoing], caption: str | None = None
    ) -> list[CachedItem]:
        sent: list[CachedItem] = []

        for chunk in batched(items, TELEGRAM_ALBUM_SIZE):
            await self._limiter.acquire(job.chat_id, len(chunk))

            if len(chunk) == 1:
                sent.append(await self._send_single(job, chunk[0], caption))
            else:
                sent.extend(await self._send_album(job, chunk, caption))

            caption = None  # only the first message of a long album carries it

        return sent

    async def _send_single(self, job: Job, item: Outgoing, caption: str | None) -> CachedItem:
        common: dict[str, Any] = {
            "caption": caption,
            "parse_mode": ParseMode.HTML,
            "reply_parameters": _reply_to(job),
        }

        match item.kind:
            case MediaKind.PHOTO:
                message = await self._bot.send_photo(job.chat_id, item.media, **common)
            case MediaKind.ANIMATION:
                message = await self._bot.send_animation(job.chat_id, item.media, **common)
            case MediaKind.VIDEO:
                message = await self._bot.send_video(
                    job.chat_id,
                    item.media,
                    width=item.width,
                    height=item.height,
                    duration=item.duration,
                    supports_streaming=True,
                    **common,
                )

        return _sent_item(message)

    async def _send_album(
        self, job: Job, items: tuple[Outgoing, ...], caption: str | None
    ) -> list[CachedItem]:
        media: list[MediaUnion] = [_input_media(item) for item in items]

        if caption:  # Telegram shows the first item's caption under the whole album
            media[0] = media[0].model_copy(
                update={"caption": caption, "parse_mode": ParseMode.HTML}
            )

        messages = await self._bot.send_media_group(
            job.chat_id, media, reply_parameters=_reply_to(job)
        )

        return [_sent_item(message) for message in messages]


def _reply_to(job: Job) -> ReplyParameters:
    return ReplyParameters(message_id=job.message_id, allow_sending_without_reply=True)


def _input_media(item: Outgoing) -> InputMediaPhoto | InputMediaVideo:
    if item.kind is MediaKind.PHOTO:
        return InputMediaPhoto(media=item.media)

    return InputMediaVideo(
        media=item.media,
        width=item.width,
        height=item.height,
        duration=item.duration,
        supports_streaming=True,
    )


def _sent_item(message: Message) -> CachedItem:
    if message.photo:
        return CachedItem(kind=MediaKind.PHOTO, file_id=message.photo[-1].file_id)

    if message.video:
        return CachedItem(kind=MediaKind.VIDEO, file_id=message.video.file_id)

    if message.animation:  # Telegram turns silent videos into animations
        return CachedItem(kind=MediaKind.ANIMATION, file_id=message.animation.file_id)

    raise SendError("no media in sent message")
