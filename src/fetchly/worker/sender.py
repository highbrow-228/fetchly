"""Sends media as a reply and collects the resulting file_ids."""

from dataclasses import dataclass
from itertools import batched

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import (
    InputMediaPhoto,
    InputMediaVideo,
    MediaUnion,
    Message,
    ReplyParameters,
)

from fetchly.cache import CachedItem
from fetchly.extractors import MediaItem, MediaKind
from fetchly.queue import Job
from fetchly.ratelimit import SendLimiter

TELEGRAM_ALBUM_SIZE = 10


class SendError(Exception):
    """Telegram accepted the request but returned no usable media."""


@dataclass(frozen=True, slots=True)
class Outgoing:
    kind: MediaKind
    media: str  # file_id or file:// URI readable by the local Bot API server
    width: int | None = None
    height: int | None = None
    duration: int | None = None

    @classmethod
    def from_file(cls, item: MediaItem) -> "Outgoing":
        return cls(item.kind, item.path.as_uri(), item.width, item.height, item.duration)

    @classmethod
    def from_cache(cls, item: CachedItem) -> "Outgoing":
        return cls(item.kind, item.file_id)


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
        reply = _reply_to(job)
        if item.kind is MediaKind.PHOTO:
            message = await self._bot.send_photo(
                job.chat_id,
                item.media,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_parameters=reply,
            )
        elif item.kind is MediaKind.ANIMATION:
            message = await self._bot.send_animation(
                job.chat_id,
                item.media,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_parameters=reply,
            )
        else:
            message = await self._bot.send_video(
                job.chat_id,
                item.media,
                width=item.width,
                height=item.height,
                duration=item.duration,
                supports_streaming=True,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_parameters=reply,
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
        return CachedItem(MediaKind.PHOTO, message.photo[-1].file_id)
    if message.video:
        return CachedItem(MediaKind.VIDEO, message.video.file_id)
    if message.animation:  # Telegram turns silent videos into animations
        return CachedItem(MediaKind.ANIMATION, message.animation.file_id)
    raise SendError("no media in sent message")
