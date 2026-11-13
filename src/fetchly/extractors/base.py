from enum import StrEnum
from pathlib import Path
from typing import ClassVar, Protocol

from pydantic import BaseModel, Field

from fetchly.links import Platform


class MediaKind(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
    ANIMATION = "animation"


class MediaItem(BaseModel, frozen=True):
    kind: MediaKind = Field(description="Type of the file: photo, video or animation")
    path: Path = Field(description="Where the downloaded file is on disk")
    width: int | None = Field(default=None, description="Width in pixels; None = unknown")
    height: int | None = Field(default=None, description="Height in pixels; None = unknown")
    duration: int | None = Field(
        default=None, description="Video length in seconds; None = unknown"
    )


class MediaResult(BaseModel, frozen=True):
    platform: Platform = Field(description="Platform the media came from")
    media_id: str = Field(description="Id of the post, unique within the platform")
    extractor: str = Field(description="Tool that downloaded the media: yt-dlp or gallery-dl")
    items: list[MediaItem] = Field(
        description="Downloaded files, in the order they appear in the post"
    )
    workdir: Path = Field(
        description="Temporary directory with the files; whoever gets this result must delete it"
    )
    caption: str | None = Field(
        default=None, description="Text sent under the media, as Telegram HTML; None = no caption"
    )

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

    def __init__(self, tool: str, returncode: int | None = None, detail: str | None = None) -> None:
        super().__init__(tool)
        self.tool = tool
        self.returncode = returncode
        # The tool's last error line, without URLs.
        self.detail = detail
        # Errors of every tool tried for the link, this one included; filled by the registry.
        self.attempts: list[ExtractionError] = []


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


class ExtractionFailedError(ExtractionError):
    """The tool gave up on this link (deleted post, unsupported page); retrying is pointless."""

    retryable = False


class LoginRequiredError(ExtractionError):
    """This post is only visible to a logged-in account (private, age-gated)."""

    result = "login_required"
    retryable = False


class PlatformBlockedError(ExtractionError):
    """The platform is throttling us (HTTP 429, bot check)."""

    result = "blocked"
    retryable = False


class PlatformPausedError(ExtractionError):
    """The platform is on pause after a recent block; nothing was attempted."""

    result = "paused"
    retryable = False
