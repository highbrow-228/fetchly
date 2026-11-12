"""Extractor contract: what every download backend provides."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import ClassVar, Protocol

from fetchly.links import Platform


class MediaKind(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
    ANIMATION = "animation"


@dataclass(frozen=True, slots=True)
class MediaItem:
    kind: MediaKind
    path: Path
    width: int | None = None
    height: int | None = None
    duration: int | None = None


@dataclass(frozen=True, slots=True)
class MediaResult:
    platform: Platform
    media_id: str
    extractor: str
    items: list[MediaItem]
    workdir: Path  # owned by the caller once returned; remove after sending
    caption: str | None = None  # Telegram HTML

    @property
    def size_bytes(self) -> int:
        return sum(item.path.stat().st_size for item in self.items)


class Extractor(Protocol):
    name: str

    def supports(self, url: str) -> bool: ...

    async def extract(self, url: str) -> MediaResult: ...


class ExtractionError(Exception):
    """Download failed. `result` is the outcome label for logs, metrics and the DB."""

    result: ClassVar[str] = "failed"
    retryable: ClassVar[bool] = True


class ExtractionTimeoutError(ExtractionError):
    result = "timeout"


class NoMediaError(ExtractionError):
    result = "no_media"
    retryable = False


class MediaTooLargeError(ExtractionError):
    result = "too_large"
    retryable = False


class MediaTooLongError(ExtractionError):
    result = "too_long"
    retryable = False


class PlatformBlockedError(ExtractionError):
    """The platform answered with HTTP 429 or demanded a login."""

    result = "blocked"
    retryable = False


class PlatformPausedError(ExtractionError):
    """The platform is on pause after a recent block; nothing was attempted."""

    result = "paused"
    retryable = False
