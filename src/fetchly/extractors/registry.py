"""Extractor chains: which backends to try for each platform, and in what order."""

from collections.abc import Mapping, Sequence

from fetchly.config import Settings
from fetchly.extractors.base import (
    ExtractionError,
    Extractor,
    MediaResult,
    MediaTooLargeError,
    MediaTooLongError,
    NoMediaError,
    PlatformBlockedError,
)
from fetchly.extractors.gallerydl import GalleryDlExtractor
from fetchly.extractors.options import ExtractorOptions
from fetchly.extractors.workspace import Workspace
from fetchly.extractors.ytdlp import YtDlpExtractor
from fetchly.links import Platform


class ExtractorRegistry:
    def __init__(self, chains: Mapping[Platform, Sequence[Extractor]]) -> None:
        self._chains = chains

    async def extract(self, platform: Platform, url: str) -> MediaResult:
        """Try the platform's extractors in order; the first success wins."""
        errors: list[ExtractionError] = []
        for extractor in self._chains.get(platform, ()):
            if not extractor.supports(url):
                continue
            try:
                return await extractor.extract(url)
            except (MediaTooLargeError, MediaTooLongError):
                raise  # another backend would hit the same limit
            except ExtractionError as error:
                errors.append(error)
        raise _most_relevant(errors)


def _most_relevant(errors: list[ExtractionError]) -> ExtractionError:
    if not errors:
        return NoMediaError("no extractor")
    blocked = [error for error in errors if isinstance(error, PlatformBlockedError)]
    return blocked[0] if blocked else errors[-1]


def build_registry(settings: Settings, workspace: Workspace) -> ExtractorRegistry:
    """Default order: yt-dlp first, gallery-dl as the fallback for photo posts.

    To plug in another backend, implement `Extractor` and add it to the chains here.
    """
    options = ExtractorOptions(
        timeout_seconds=settings.download_timeout_seconds,
        max_bytes=settings.max_file_size_bytes,
        max_duration_seconds=settings.max_duration_seconds,
        max_height=settings.max_video_height,
        max_items=settings.max_album_items,
        proxies=settings.proxies,
    )
    ytdlp = YtDlpExtractor(options, workspace)
    gallerydl = GalleryDlExtractor(options, workspace)
    return ExtractorRegistry(dict.fromkeys(Platform, (ytdlp, gallerydl)))
