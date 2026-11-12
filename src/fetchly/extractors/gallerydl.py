"""gallery-dl backend: photos, carousels, slideshows."""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from fetchly.extractors.base import (
    ExtractionError,
    MediaItem,
    MediaKind,
    MediaResult,
    MediaTooLongError,
    NoMediaError,
    PlatformBlockedError,
)
from fetchly.extractors.caption import build_caption, from_gallery_dl
from fetchly.extractors.options import (
    PHOTO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    ExtractorOptions,
    is_blocked,
)
from fetchly.extractors.probe import probe_video
from fetchly.extractors.process import ProcessOutput, run_process
from fetchly.extractors.workspace import Workspace
from fetchly.links import Platform, detect_platform

# gallery-dl exit status is a bit mask; 16 = authentication/authorization error.
_EXIT_AUTH = 16


class GalleryDlExtractor:
    name = "gallery-dl"

    def __init__(self, options: ExtractorOptions, workspace: Workspace) -> None:
        self._options = options
        self._workspace = workspace

    def supports(self, url: str) -> bool:
        return detect_platform(url) not in (None, Platform.YOUTUBE)

    async def extract(self, url: str) -> MediaResult:
        platform = detect_platform(url)
        if platform is None:
            raise NoMediaError(self.name)
        workdir = await self._workspace.create()
        try:
            command = await self._command(url, platform, workdir)
            output = await run_process(command, self._options.timeout_seconds)
            paths = _downloaded(output)
            items = [item for path in paths if (item := await self._item(path))]
            if not items:
                self._fail(output)
            caption = build_caption(platform, from_gallery_dl(platform, _metadata(paths[0])))
            # gallery-dl has no uniform media id; the link itself identifies the post.
            media_id = hashlib.sha256(url.encode()).hexdigest()[:32]
            return MediaResult(platform, media_id, self.name, items, workdir, caption)
        except BaseException:
            await self._workspace.discard(workdir)
            raise

    async def _command(self, url: str, platform: Platform, workdir: Path) -> list[str]:
        options = self._options
        command = [
            sys.executable, "-m", "gallery_dl",
            "--config-ignore",
            "--directory", str(workdir),
            "--range", f"1-{options.max_items}",
            "--filesize-max", str(options.max_bytes),
            "--write-metadata",
        ]  # fmt: skip
        if proxy := options.proxies.get(platform):
            command += ["--proxy", proxy]
        if cookies := await self._workspace.cookies(platform, workdir):
            command += ["--cookies", str(cookies)]
        return [*command, url]

    async def _item(self, path: Path) -> MediaItem | None:
        suffix = path.suffix.lower()
        if suffix in PHOTO_EXTENSIONS:
            return MediaItem(MediaKind.PHOTO, path)
        if suffix not in VIDEO_EXTENSIONS:
            return None  # e.g. the audio track of a slideshow
        info = await probe_video(path, self._options.timeout_seconds)
        if info.duration is not None and info.duration > self._options.max_duration_seconds:
            raise MediaTooLongError(self.name)
        return MediaItem(MediaKind.VIDEO, path, info.width, info.height, info.duration)

    def _fail(self, output: ProcessOutput) -> None:
        if output.returncode & _EXIT_AUTH or is_blocked(output.text):
            raise PlatformBlockedError(self.name)
        if output.returncode == 0:
            raise NoMediaError(self.name)
        raise ExtractionError(f"{self.name} exit {output.returncode}")


def _downloaded(output: ProcessOutput) -> list[Path]:
    """gallery-dl prints one file path per line, in post order."""
    paths = (Path(line.removeprefix("# ").strip()) for line in output.stdout.splitlines())
    return [path for path in paths if path.is_absolute() and path.is_file()]


def _metadata(path: Path) -> dict[str, Any]:
    """--write-metadata puts `<file>.json` next to every downloaded file."""
    sidecar = path.with_name(path.name + ".json")
    if not sidecar.is_file():
        return {}
    data = json.loads(sidecar.read_text())
    return data if isinstance(data, dict) else {}
